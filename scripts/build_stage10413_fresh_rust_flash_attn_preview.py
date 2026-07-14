#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path("/data/agentkernel-seq2seq-text-lab")
OUT_DIR = ROOT / "runs/local/artifacts/stage10413_fresh_rust_flash_attn_preview"
BUNDLE_PATH = OUT_DIR / "fresh_rust_flash_attn_preview_bundle.json"
SUMMARY_PATH = OUT_DIR / "fresh_rust_flash_attn_preview_summary.json"

CANDIDATES = ROOT / "runs/local/artifacts/stage10125_true_source_backed_rust_root_discovery_manifest/true_source_backed_rust_root_candidates.jsonl"
SPANS = Path("/arxiv/TOLBERT_BRAIN/data/repos/spans_repos.jsonl")
TARGET_ROOT = "candle::candle-flash-attn"
MAX_TEXT = 1200
PERSPECTIVES = [
    "symptom_localization",
    "evidence_citation",
    "alternative_hypothesis_elimination",
    "patch_impact",
    "verifier_outcome",
    "minimal_fix_selection",
    "regression_risk",
    "abstention_insufficient_evidence",
]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def truncate(text: str) -> str:
    text = str(text or "").strip()
    if len(text) <= MAX_TEXT:
        return text
    return text[: MAX_TEXT - 3].rstrip() + "..."


def path_kind(path_text: str) -> str:
    lower = path_text.lower()
    name = Path(lower).name
    if "/tests/" in lower or lower.startswith("tests/") or name.endswith("_tests.rs") or name.startswith("test_"):
        return "test"
    if name == "build.rs":
        return "build"
    if "/src/" in lower or lower.startswith("src/") or name in {"lib.rs", "main.rs"}:
        return "implementation"
    return "support"


def load_candidate() -> dict[str, Any]:
    for row in load_jsonl(CANDIDATES):
        if row["candidate_root_id"] == TARGET_ROOT:
            return row
    raise SystemExit(f"missing candidate root: {TARGET_ROOT}")


def gather_spans(paths: list[str]) -> dict[str, dict[str, Any]]:
    want = set(paths)
    gathered: dict[str, dict[str, Any]] = {}
    with SPANS.open("r", encoding="utf-8") as handle:
        for line in handle:
            obj = json.loads(line)
            span_id = str(obj.get("span_id") or "")
            if ":" not in span_id:
                continue
            _, path_text = span_id.split(":", 1)
            if path_text not in want or path_text in gathered:
                continue
            gathered[path_text] = {
                "path": path_text,
                "meta": obj.get("meta") if isinstance(obj.get("meta"), dict) else {},
                "text": truncate(str(obj.get("text") or "")),
            }
            if len(gathered) == len(want):
                break
    return gathered


def evidence_item(path_text: str, gathered: dict[str, dict[str, Any]], retrieval_reason: str) -> dict[str, Any]:
    span = gathered.get(path_text, {})
    return {
        "path": path_text,
        "source_type": "external_repo_graph_span",
        "retrieval_reason": retrieval_reason,
        "distance_from_seed": 0,
        "text": span.get("text", ""),
        "meta": span.get("meta", {}),
    }


def perspective_row(bundle_id: str, perspective: str, evidence: dict[str, list[dict[str, Any]]], candidate_paths: list[str], selected_tests: list[str]) -> dict[str, Any]:
    tasks = {
        "symptom_localization": "Choose the most likely rust edit target from the visible code and verifier evidence.",
        "evidence_citation": "Name the visible rust fact that best supports the chosen edit target.",
        "alternative_hypothesis_elimination": "Explain why a plausible alternative rust target is less justified.",
        "patch_impact": "Compare candidate rust edits by likely behavior change and risk.",
        "verifier_outcome": "Predict which visible rust test or build constraint should change if the fix is correct.",
        "minimal_fix_selection": "Choose the smallest maintainable rust intervention supported by the evidence.",
        "regression_risk": "Identify what the likely rust fix might break or destabilize.",
        "abstention_insufficient_evidence": "Decide whether the visible rust evidence is enough for a singleton answer or whether abstention is more honest.",
    }
    return {
        "bundle_id": bundle_id,
        "language_family": "rust",
        "perspective": perspective,
        "prompt_contract": {
            "task": tasks[perspective],
            "candidate_paths": candidate_paths,
            "selected_tests": selected_tests,
            "visible_evidence_keys": sorted(key for key, value in evidence.items() if value),
            "abstention_option_required": perspective == "abstention_insufficient_evidence",
        },
        "gold_answer_status": "human_maintainer_adjudication_required",
        "eligible_for_training_or_scoring_now": False,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    candidate = load_candidate()
    candidate_paths = [str(p) for p in candidate.get("candidate_paths_preview") or []]
    gathered = gather_spans(candidate_paths)

    implementation = [p for p in candidate_paths if path_kind(p) == "implementation"][:2]
    tests = [p for p in candidate_paths if path_kind(p) == "test"][:1]
    builds = [p for p in candidate_paths if path_kind(p) == "build"][:1]
    support = [p for p in candidate_paths if path_kind(p) == "support"][:1]
    selected_tests = tests[:]

    evidence = {
        "candidate_change_surface": [evidence_item(p, gathered, "discovered_rust_candidate_surface") for p in implementation + builds],
        "verifier_and_test_constraint": [evidence_item(p, gathered, "rust_test_or_build_constraint") for p in tests + builds],
        "symptom_or_call_path_analogue": [evidence_item(p, gathered, "rust_package_primary_signal") for p in implementation[:1] + tests],
        "nearby_definition_or_usage_context": [evidence_item(p, gathered, "rust_nearby_definition_context") for p in implementation[1:2] + support],
        "external_analogue_reference": [evidence_item(p, gathered, "rust_package_analogue_context") for p in support],
        "algorithmic_background_reference": [evidence_item(p, gathered, "rust_algorithmic_background") for p in implementation[:1]],
    }

    bundle_id = "stage10413::candle::candle-flash-attn::rust"
    bundle = {
        "bundle_id": bundle_id,
        "root_example_id": TARGET_ROOT,
        "repo_id": candidate["repo_id"],
        "language_family": "rust",
        "source_route": "external_repo_graph_spans",
        "seed_paths": candidate_paths,
        "selected_tests": selected_tests,
        "claim_boundary": {
            "gold_answers_fully_adjudicated": False,
            "supports_training_or_scoring_now": False,
            "preview_only": True,
        },
        "maintainer_visible_evidence": evidence,
        "candidate_paths": candidate_paths,
        "discovery_metadata": {
            "package_root": candidate["package_root"],
            "richness_score": candidate["richness_score"],
            "competition_geometries": candidate["competition_geometries"],
            "review_ready_for_bundle_construction": candidate["review_ready_for_bundle_construction"],
            "test_file_count": candidate["test_file_count"],
            "build_file_count": candidate["build_file_count"],
        },
        "perspective_rows": [
            perspective_row(bundle_id, perspective, evidence, candidate_paths, selected_tests)
            for perspective in PERSPECTIVES
        ],
    }

    summary = {
        "created_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "stage": 10413,
        "stage_name": "stage10413_fresh_rust_flash_attn_preview",
        "passed": True,
        "bundle_id": bundle_id,
        "candidate_root_id": TARGET_ROOT,
        "selected_tests_count": len(selected_tests),
        "candidate_paths_count": len(candidate_paths),
        "visible_evidence_keys": sorted(k for k, v in evidence.items() if v),
        "claim_boundary": [
            "This is a fresh Rust preview bundle, not yet an admitted maintainer-grade eval unit.",
            "It is stronger than prior fresh Rust candidates because it carries both a test file and implementation-vs-test geometry.",
            "Gold adjudication, anti-cheat review, and expert rubric review are still required before scoring or training use.",
        ],
        "next_best_step": "Attach Rust review packets and adjudication stubs for this bundle, then compare its evidence quality against candle-core/tokenizers before admitting it into multilingual scaling.",
    }

    BUNDLE_PATH.write_text(json.dumps(bundle, indent=2) + "\n", encoding="utf-8")
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
