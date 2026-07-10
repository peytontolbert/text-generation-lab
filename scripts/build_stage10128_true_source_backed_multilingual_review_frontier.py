#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10128
NAME = "stage10128_true_source_backed_multilingual_review_frontier"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
ATLAS = OUT_DIR / "true_source_backed_multilingual_review_frontier.json"
QUEUE = OUT_DIR / "true_source_backed_multilingual_review_frontier_queue.jsonl"
WORKBOOK = OUT_DIR / "true_source_backed_multilingual_review_frontier_first_wave_signoff_workbook.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRUE_SOURCE_BACKED_MULTILINGUAL_REVIEW_FRONTIER_STAGE10128.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

BASE_BUNDLES = ROOT / "runs/local/artifacts/stage10119_true_source_backed_maintainer_root_bundle_preview/true_source_backed_maintainer_root_bundle_preview.jsonl"
BASE_REVIEW_MANIFEST = ROOT / "runs/local/artifacts/stage10120_true_source_backed_maintainer_root_bundle_review_packets/true_source_backed_maintainer_root_bundle_review_packet_manifest.json"
BASE_BLOCKED = ROOT / "runs/local/artifacts/stage10122_true_source_backed_root_bundle_adjudicated_manifest_compiler/true_source_backed_root_bundle_blocked_manifest.json"
RUST_BUNDLES = ROOT / "runs/local/artifacts/stage10126_true_source_backed_rust_root_bundle_preview/true_source_backed_rust_root_bundle_preview.jsonl"
RUST_REVIEW_MANIFEST = ROOT / "runs/local/artifacts/stage10127_true_source_backed_rust_review_packets_and_signoff/true_source_backed_rust_review_packet_manifest.json"

LANGUAGE_PRIORITY = {
    "web_js_ts_html": 5,
    "rust": 4,
    "c_cpp": 3,
    "python": 2,
}
PENDING_BLOCK_REASONS = [
    "rubric_status_not_completed",
    "rubric_bundle_not_marked_valid",
    "rubric_missing_reviewer_id",
    "rubric_missing_decision_rationale",
    "anti_cheat_status_not_completed",
    "anti_cheat_not_marked_admissible",
    "anti_cheat_missing_reviewer_id",
    "anti_cheat_missing_decision_rationale",
    "gold_status_not_completed",
    "gold_bundle_not_ready",
    "gold_missing_reviewer_id",
]


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


def _reason(flag: bool, text: str) -> list[str]:
    return [text] if flag else []


def _score_bundle(bundle: dict[str, Any], blocked_reasons: list[str], review_paths: dict[str, str]) -> dict[str, Any]:
    language = str(bundle.get("language_family") or "")
    tests = list(bundle.get("selected_tests") or [])
    candidates = list(bundle.get("candidate_paths") or [])
    evidence = bundle.get("maintainer_visible_evidence") if isinstance(bundle.get("maintainer_visible_evidence"), dict) else {}
    perspectives = list(bundle.get("perspective_rows") or [])
    abstention_required = sum(
        1 for row in perspectives if isinstance(row.get("prompt_contract"), dict) and row["prompt_contract"].get("abstention_option_required")
    )

    claim_score = LANGUAGE_PRIORITY.get(language, 0) * 10
    evidence_score = min(len(tests), 5) * 3 + min(len(candidates), 6)
    evidence_score += 2 if "nearby_definition_or_usage_context" in evidence else 0
    evidence_score += 2 if "verifier_and_test_constraint" in evidence else 0
    shortcut_risk = 0
    shortcut_risk += 4 if len(candidates) <= 2 else 0
    shortcut_risk += 2 if len(tests) == 0 else 0
    shortcut_risk += 2 if abstention_required > 0 else 0
    total = claim_score + evidence_score + shortcut_risk

    claim_reasons = [
        f"language_priority::{language}::{LANGUAGE_PRIORITY.get(language, 0)}",
        *(_reason(language == "web_js_ts_html", "web_language_scarcity_for_product_claim")),
        *(_reason(language == "rust", "rust_now_present_and_needed_for_four_language_claim")),
        *(_reason(language == "c_cpp", "c_cpp_needed_for_multilingual_maintainer_claim")),
        *(_reason(language == "python", "python_needed_for_multilingual_maintainer_claim")),
    ]
    evidence_reasons = [
        f"selected_tests::{len(tests)}",
        f"candidate_paths::{len(candidates)}",
        *(_reason("nearby_definition_or_usage_context" in evidence, "has_nearby_definition_or_usage_context")),
        *(_reason("verifier_and_test_constraint" in evidence, "has_verifier_and_test_constraint")),
        *(_reason(abstention_required > 0, "includes_abstention_perspective")),
    ]
    shortcut_reasons = [
        *(_reason(len(candidates) <= 2, "few_candidate_paths_shortcut_risk")),
        *(_reason(len(tests) == 0, "no_selected_tests_shortcut_risk")),
        *(_reason(abstention_required > 0, "abstention_requires_honesty_review")),
    ]
    return {
        "bundle_id": bundle["bundle_id"],
        "language_family": language,
        "repo_id": bundle["repo_id"],
        "source_route": bundle.get("source_route"),
        "selected_tests_count": len(tests),
        "candidate_paths_count": len(candidates),
        "abstention_perspectives": abstention_required,
        "claim_priority_score": claim_score,
        "evidence_richness_score": evidence_score,
        "shortcut_risk_score": shortcut_risk,
        "priority_score": total,
        "claim_reasons": claim_reasons,
        "evidence_reasons": evidence_reasons,
        "shortcut_risk_reasons": shortcut_reasons,
        "blocked_reasons": blocked_reasons,
        "review_packet_paths": review_paths,
    }


def _merged_inputs() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, str]], dict[str, list[str]], list[str]]:
    failures: list[str] = []
    base_bundles = load_jsonl(BASE_BUNDLES)
    rust_bundles = load_jsonl(RUST_BUNDLES)
    base_review = load_json(BASE_REVIEW_MANIFEST)
    rust_review = load_json(RUST_REVIEW_MANIFEST)
    base_blocked = load_json(BASE_BLOCKED)

    if len(base_bundles) != 8:
        failures.append("stage10119_bundle_count_not_8")
    if len(rust_bundles) != 4:
        failures.append("stage10126_rust_bundle_count_not_4")
    if base_review.get("passed") is not True:
        failures.append("stage10120_not_passed")
    if rust_review.get("passed") is not True:
        failures.append("stage10127_not_passed")
    if base_blocked.get("passed") is not True:
        failures.append("stage10122_not_passed")

    bundle_index = {str(bundle["bundle_id"]): bundle for bundle in base_bundles + rust_bundles}
    review_index = {}
    for row in (base_review.get("rows") or []):
        review_index[str(row["bundle_id"])] = row["review_packet_paths"]
    for row in (rust_review.get("rows") or []):
        review_index[str(row["bundle_id"])] = row["review_packet_paths"]

    blocked_index = {str(row["bundle_id"]): list(row.get("blocked_reasons") or []) for row in (base_blocked.get("rows") or [])}
    for bundle in rust_bundles:
        blocked_index[str(bundle["bundle_id"])] = list(PENDING_BLOCK_REASONS)

    return bundle_index, review_index, blocked_index, failures


def _pick_first_wave(queue_rows: list[dict[str, Any]]) -> list[str]:
    chosen: list[str] = []
    by_language: dict[str, list[dict[str, Any]]] = {}
    for row in queue_rows:
        by_language.setdefault(row["language_family"], []).append(row)

    for language in ["web_js_ts_html", "python", "c_cpp", "rust"]:
        for row in by_language.get(language, [])[:2]:
            chosen.append(row["bundle_id"])

    for row in queue_rows:
        if len(chosen) >= 8:
            break
        if row["bundle_id"] not in chosen:
            chosen.append(row["bundle_id"])
    return chosen[:8]


def _build_workbook(queue_rows: list[dict[str, Any]], wave_ids: list[str]) -> dict[str, Any]:
    indexed = {row["bundle_id"]: row for row in queue_rows}
    rows: list[dict[str, Any]] = []
    pos = 1
    for wave_rank, bundle_id in enumerate(wave_ids, start=1):
        row = indexed[bundle_id]
        common = {
            "bundle_id": bundle_id,
            "wave_rank": wave_rank,
            "language_family": row["language_family"],
            "repo_id": row["repo_id"],
            "priority_score": row["priority_score"],
            "claim_priority_score": row["claim_priority_score"],
            "evidence_richness_score": row["evidence_richness_score"],
            "shortcut_risk_score": row["shortcut_risk_score"],
            "supporting_paths": row["review_packet_paths"],
        }
        rows.append(
            {
                "queue_position": pos,
                "task": "expert_maintainer_rubric_review",
                "review_file": row["review_packet_paths"]["expert_maintainer_rubric_review"],
                "required_human_action": "Decide whether the maintainer-visible evidence supports a valid bounded evaluation bundle rather than a templated shortcut.",
                **common,
            }
        )
        pos += 1
        rows.append(
            {
                "queue_position": pos,
                "task": "cell_specific_anti_cheat_review",
                "review_file": row["review_packet_paths"]["anti_cheat_review_card"],
                "required_human_action": "Stress-test the bundle for candidate-count priors, missing-test shortcuts, and language-template leakage before allowing same-surface comparison use.",
                **common,
            }
        )
        pos += 1
        gold_path = row["review_packet_paths"].get("perspective_gold_adjudication")
        if not gold_path:
            gold_path = str(Path(row["review_packet_paths"]["packet_dir"]) / "perspective_gold_adjudication.json")
        rows.append(
            {
                "queue_position": pos,
                "task": "perspective_gold_adjudication",
                "review_file": gold_path,
                "required_human_action": "Fill all eight perspective gold answers and rationales so the bundle can clear the adjudicated manifest gate.",
                **common,
            }
        )
        pos += 1
    return {
        "passed": True,
        "row_count": len(rows),
        "rows": rows,
        "metrics": {
            "first_wave_bundles": len(wave_ids),
            "signoff_tasks": len(rows),
            "wave_language_counts": dict(sorted(Counter(row["language_family"] for row in rows if row["task"] == "expert_maintainer_rubric_review").items())),
        },
    }


def build_frontier() -> dict[str, Any]:
    bundle_index, review_index, blocked_index, failures = _merged_inputs()
    queue_rows: list[dict[str, Any]] = []
    for bundle_id, bundle in bundle_index.items():
        review_paths = review_index.get(bundle_id)
        blocked_reasons = blocked_index.get(bundle_id)
        if review_paths is None:
            failures.append(f"missing_review_paths::{bundle_id}")
            continue
        if blocked_reasons is None:
            failures.append(f"missing_blocked_reasons::{bundle_id}")
            continue
        queue_rows.append(_score_bundle(bundle, blocked_reasons, review_paths))

    queue_rows.sort(
        key=lambda row: (
            -row["priority_score"],
            -row["shortcut_risk_score"],
            -row["evidence_richness_score"],
            row["bundle_id"],
        )
    )
    for idx, row in enumerate(queue_rows, start=1):
        row["queue_position"] = idx
        row["priority_tier"] = "highest" if idx <= 6 else "high" if idx <= 8 else "follow_on"

    wave_ids = _pick_first_wave(queue_rows)
    workbook = _build_workbook(queue_rows, wave_ids)
    metrics = {
        "bundle_count": len(queue_rows),
        "queue_language_counts": dict(sorted(Counter(row["language_family"] for row in queue_rows).items())),
        "first_wave_bundle_count": len(wave_ids),
        "first_wave_language_counts": workbook["metrics"]["wave_language_counts"],
        "four_language_review_ready": True,
        "rust_review_ready_bundles": sum(1 for row in queue_rows if row["language_family"] == "rust"),
    }
    if workbook["metrics"]["signoff_tasks"] != 24:
        failures.append("first_wave_signoff_tasks_not_24")
    if workbook["metrics"]["wave_language_counts"] != {"c_cpp": 2, "python": 2, "rust": 2, "web_js_ts_html": 2}:
        failures.append("first_wave_language_counts_unexpected")

    atlas = {
        "passed": not failures,
        "stage": STAGE,
        "name": NAME,
        "metrics": metrics,
        "priority_queue": queue_rows,
        "recommended_first_wave": {
            "bundle_ids": wave_ids,
            "reason": (
                "Open one honest four-language maintainer-grade slice first: two bundles each from web, python, c_cpp, and rust, all under the same rubric, anti-cheat, and gold-adjudication contract."
            ),
        },
        "failures": failures,
    }
    return {"passed": not failures, "failures": failures, "atlas": atlas, "queue_rows": queue_rows, "workbook": workbook}


def main() -> None:
    built = build_frontier()
    write_json(ATLAS, built["atlas"])
    write_jsonl(QUEUE, built["queue_rows"])
    write_json(WORKBOOK, built["workbook"])
    next_step = (
        "Work the 24 first-wave tasks to clear two bundles each for web, python, c_cpp, and rust through rubric, anti-cheat, and perspective-gold review, then rerun the adjudication compiler on that four-language slice."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {**built["atlas"]["metrics"], "failures": built["failures"]},
        "artifacts": {
            "atlas": display(ATLAS),
            "queue": display(QUEUE),
            "workbook": display(WORKBOOK),
            "doc": display(DOC),
        },
        "decision": (
            "Merged rust into the multilingual maintainer review frontier so the first-wave signoff queue now covers web, python, c_cpp, and rust under one unified review ledger."
        ),
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    write_json(SUMMARY, summary)
    DOC.write_text(
        "\n".join(
            [
                "# Stage10128 True Source-Backed Multilingual Review Frontier",
                "",
                f"Passed: `{summary['passed']}`",
                f"Bundle count: `{built['atlas']['metrics']['bundle_count']}`",
                f"First-wave bundles: `{built['atlas']['metrics']['first_wave_bundle_count']}`",
                "",
                summary["decision"],
                "",
                f"Next: {next_step}",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": built["passed"], "metrics": built["atlas"]["metrics"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
