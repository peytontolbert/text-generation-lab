#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10126
NAME = "stage10126_true_source_backed_rust_root_bundle_preview"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
BUNDLES = OUT_DIR / "true_source_backed_rust_root_bundle_preview.jsonl"
MANIFEST = OUT_DIR / "true_source_backed_rust_root_bundle_preview_manifest.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRUE_SOURCE_BACKED_RUST_ROOT_BUNDLE_PREVIEW_STAGE10126.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

CANDIDATES = ROOT / "runs/local/artifacts/stage10125_true_source_backed_rust_root_discovery_manifest/true_source_backed_rust_root_candidates.jsonl"
SPANS = Path("/arxiv/TOLBERT_BRAIN/data/repos/spans_repos.jsonl")

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
TARGET_BUNDLES = 4
MAX_TEXT = 1200


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "next_best_step": summary["next_best_step"],
        }
    )
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0) or 0)),
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _truncate(text: str) -> str:
    text = str(text or "").strip()
    if len(text) <= MAX_TEXT:
        return text
    return text[: MAX_TEXT - 3].rstrip() + "..."


def _path_kind(path_text: str) -> str:
    lower = path_text.lower()
    name = Path(lower).name
    if "/tests/" in lower or lower.startswith("tests/") or name.endswith("_tests.rs") or name.startswith("test_"):
        return "test"
    if name == "build.rs":
        return "build"
    if "/src/" in lower or lower.startswith("src/") or name in {"lib.rs", "main.rs"}:
        return "implementation"
    return "support"


def _candidate_rows() -> list[dict[str, Any]]:
    rows = load_jsonl(CANDIDATES)
    ready = [row for row in rows if row.get("review_ready_for_bundle_construction")]
    return ready[:TARGET_BUNDLES]


def _selected_paths(candidates: list[dict[str, Any]]) -> set[str]:
    paths: set[str] = set()
    for row in candidates:
        for path_text in row.get("candidate_paths_preview") or []:
            paths.add(str(path_text))
    return paths


def _gather_span_texts(paths: set[str]) -> dict[str, dict[str, Any]]:
    gathered: dict[str, dict[str, Any]] = {}
    with SPANS.open("r", encoding="utf-8") as handle:
        for line in handle:
            obj = json.loads(line)
            span_id = str(obj.get("span_id", ""))
            if ":" not in span_id:
                continue
            _, path_text = span_id.split(":", 1)
            if path_text not in paths or path_text in gathered:
                continue
            gathered[path_text] = {
                "path": path_text,
                "source_id": str(obj.get("source_id") or ""),
                "node_path": obj.get("node_path"),
                "meta": obj.get("meta") if isinstance(obj.get("meta"), dict) else {},
                "text": _truncate(str(obj.get("text") or "")),
            }
            if len(gathered) == len(paths):
                break
    return gathered


def _evidence_item(path_text: str, gathered: dict[str, dict[str, Any]], retrieval_reason: str) -> dict[str, Any]:
    span = gathered.get(path_text, {})
    return {
        "path": path_text,
        "source_type": "external_repo_graph_span",
        "retrieval_reason": retrieval_reason,
        "distance_from_seed": 0,
        "text": span.get("text", ""),
        "meta": span.get("meta", {}),
    }


def _perspective_row(bundle_id: str, perspective: str, evidence: dict[str, list[dict[str, Any]]], candidate_paths: list[str], selected_tests: list[str]) -> dict[str, Any]:
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


def _bundle(candidate: dict[str, Any], gathered: dict[str, dict[str, Any]]) -> dict[str, Any]:
    candidate_paths = [str(path_text) for path_text in (candidate.get("candidate_paths_preview") or [])]
    implementation = [p for p in candidate_paths if _path_kind(p) == "implementation"][:3]
    tests = [p for p in candidate_paths if _path_kind(p) == "test"][:2]
    builds = [p for p in candidate_paths if _path_kind(p) == "build"][:1]
    support = [p for p in candidate_paths if _path_kind(p) == "support"][:2]
    selected_tests = tests[:]
    evidence = {
        "candidate_change_surface": [_evidence_item(path_text, gathered, "discovered_rust_candidate_surface") for path_text in implementation[:2] + builds[:1]],
        "verifier_and_test_constraint": [_evidence_item(path_text, gathered, "rust_test_or_build_constraint") for path_text in tests[:2] + builds[:1]],
        "symptom_or_call_path_analogue": [_evidence_item(path_text, gathered, "rust_package_primary_signal") for path_text in implementation[:1] + tests[:1]],
        "nearby_definition_or_usage_context": [_evidence_item(path_text, gathered, "rust_nearby_definition_context") for path_text in implementation[1:3] + support[:1]],
        "external_analogue_reference": [_evidence_item(path_text, gathered, "rust_package_analogue_context") for path_text in support[:1]],
        "algorithmic_background_reference": [_evidence_item(path_text, gathered, "rust_algorithmic_background") for path_text in implementation[:1]],
    }
    bundle_id = f"stage10126::{candidate['candidate_root_id']}::rust"
    return {
        "bundle_id": bundle_id,
        "root_example_id": candidate["candidate_root_id"],
        "repo_id": candidate["repo_id"],
        "language_family": "rust",
        "source_route": "external_repo_graph_spans",
        "seed_paths": candidate_paths[:6],
        "selected_tests": selected_tests,
        "claim_boundary": {
            "gold_answers_fully_adjudicated": False,
            "supports_training_or_scoring_now": False,
            "preview_only": True,
        },
        "maintainer_visible_evidence": evidence,
        "candidate_paths": candidate_paths[:6],
        "discovery_metadata": {
            "package_root": candidate["package_root"],
            "richness_score": candidate["richness_score"],
            "competition_geometries": candidate["competition_geometries"],
            "review_ready_for_bundle_construction": candidate["review_ready_for_bundle_construction"],
        },
        "perspective_rows": [
            _perspective_row(bundle_id, perspective, evidence, candidate_paths[:6], selected_tests)
            for perspective in PERSPECTIVES
        ],
    }


def build() -> dict[str, Any]:
    candidates = _candidate_rows()
    failures: list[str] = []
    if len(candidates) < TARGET_BUNDLES:
        failures.append("review_ready_rust_candidates_below_target")
    selected_paths = _selected_paths(candidates)
    gathered = _gather_span_texts(selected_paths)
    bundles = [_bundle(candidate, gathered) for candidate in candidates]
    language_counts = Counter(bundle["language_family"] for bundle in bundles)
    metrics = {
        "preview_root_bundles": len(bundles),
        "bundle_language_counts": dict(sorted(language_counts.items())),
        "perspective_rows": sum(len(bundle["perspective_rows"]) for bundle in bundles),
        "bundles_with_selected_tests": sum(1 for bundle in bundles if bundle["selected_tests"]),
        "bundles_with_build_constraints": sum(
            1
            for bundle in bundles
            if any(Path(item.get("path", "")).name == "build.rs" for item in bundle["maintainer_visible_evidence"]["verifier_and_test_constraint"])
        ),
        "candidate_roots": [bundle["root_example_id"] for bundle in bundles],
    }
    manifest = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "metrics": metrics,
        "rows": bundles,
        "claim_boundary": {
            "preview_only": True,
            "supports_training_or_scoring_now": False,
            "gold_answers_human_required": True,
            "source_backed_rust_present": bool(bundles),
        },
        "failures": failures,
        "next_best_step": (
            "Attach review packets and adjudication stubs for these rust bundles, then merge the strongest reviewed rust bundles into the multilingual maintainer review queue."
        ),
    }
    return manifest


def main() -> None:
    built = build()
    write_jsonl(BUNDLES, built["rows"])
    write_json(MANIFEST, built)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": {
            "bundle_preview": display(BUNDLES),
            "manifest": display(MANIFEST),
            "doc": display(DOC),
        },
        "decision": (
            "Converted the top discovered rust roots into true source-backed maintainer bundle previews using recovered span evidence, so rust can enter the same review and anti-cheat path as the other language families."
        ),
        "next_best_step": built["next_best_step"],
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    write_json(SUMMARY, summary)
    DOC.write_text(
        "\n".join(
            [
                "# Stage10126 True Source-Backed Rust Root Bundle Preview",
                "",
                f"Passed: `{summary['passed']}`",
                f"Preview bundles: `{built['metrics']['preview_root_bundles']}`",
                f"Perspective rows: `{built['metrics']['perspective_rows']}`",
                "",
                summary["decision"],
                "",
                f"Next: {built['next_best_step']}",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": built["passed"], "failures": built["failures"], "metrics": built["metrics"]}, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
