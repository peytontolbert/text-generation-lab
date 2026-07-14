#!/usr/bin/env python3
"""Summarize Transition-Root-250 supply gaps and identify safe next materialization lanes."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path("runs/local/artifacts/stage11994_transition_root_250_supply_plan")
ROWS_V4 = Path("runs/local/artifacts/stage11993_transition_support_rollup_v4/transition_support_rows_v4.jsonl")
REJECTED = Path("runs/local/artifacts/stage11986_transition_root_250_second_batch_admission_audit/transition_root_250_second_batch_rejected_rows.jsonl")
SUMMARY = ROOT / "transition_root_250_supply_plan.json"
SUMMARY_MIRROR = Path("runs/summaries/stage11994_transition_root_250_supply_plan.json")

LANGUAGE_FLOORS = {"python": 50, "rust": 50, "c_cpp": 50, "web_js_ts_html": 50}
STATUS_FLOORS = {
    "FAIL_TO_PASS": 50,
    "PASS_TO_PASS": 100,
    "PASS_CURRENT_BUILD": 40,
    "PASS_CURRENT_BUILD_AND_RUN": 40,
    "INSUFFICIENT_EVIDENCE": 40,
    "NOT_EXERCISED": 40,
}


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def root_key(row: dict) -> str | None:
    return row.get("root_lineage_key") or row.get("root_id") or row.get("source_root_id") or row.get("source_bundle_id") or row.get("row_id")


def remaining(counts: Counter, floors: dict[str, int]) -> dict[str, int]:
    return {key: max(0, target - counts.get(key, 0)) for key, target in floors.items()}


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    SUMMARY_MIRROR.parent.mkdir(parents=True, exist_ok=True)
    rows = read_jsonl(ROWS_V4)
    rejected = read_jsonl(REJECTED)

    lang_counts = Counter(row.get("language_family") for row in rows)
    status_counts = Counter(row.get("observed_verifier_transition") for row in rows)
    repo_counts = Counter(row.get("repo_family") for row in rows)
    unique_roots_by_lang = defaultdict(set)
    for row in rows:
        unique_roots_by_lang[row.get("language_family")].add(root_key(row))

    convertible_zero_test = []
    underhydrated_negative = []
    for row in rejected:
        reason = row.get("stage11986_rejection_reason")
        if reason in {"pass_to_pass_without_executed_tests", "pass_to_pass_without_tests_ctest_empty"}:
            convertible_zero_test.append({
                "row_id": row.get("row_id"),
                "repo_family": row.get("repo_family"),
                "language_family": row.get("language_family"),
                "root_key": root_key(row),
                "reason": reason,
                "recommended_status": "NOT_EXERCISED",
            })
        elif reason and reason.startswith("nonzero_or_timeout"):
            underhydrated_negative.append({
                "row_id": row.get("row_id"),
                "repo_family": row.get("repo_family"),
                "language_family": row.get("language_family"),
                "root_key": root_key(row),
                "reason": reason,
                "recommended_status": "INSUFFICIENT_EVIDENCE" if "INSUFFICIENT" in reason else "quarantine_or_reprobe",
            })

    priority_lanes = [
        {
            "lane": "clean_zero_test_to_not_exercised",
            "available_candidates": len(convertible_zero_test),
            "action": "Convert only successful zero-test/no-test observations into NOT_EXERCISED rows; reject dependency failures/timeouts.",
            "next_stage": "stage11995_not_exercised_negative_admission",
        },
        {
            "lane": "fresh_fail_to_pass",
            "needed": remaining(status_counts, STATUS_FLOORS)["FAIL_TO_PASS"],
            "action": "Generate controlled mutations from clean PASS_TO_PASS/PASS_CURRENT_BUILD_AND_RUN roots; do not count synthetic rows as new root scale.",
        },
        {
            "lane": "fresh_independent_cpp_roots",
            "needed": remaining(lang_counts, LANGUAGE_FLOORS)["c_cpp"],
            "action": "Prioritize small local CMake/CTest roots with executable tests; current C/C++ is the thinnest language lane.",
        },
        {
            "lane": "fresh_independent_web_roots",
            "needed": remaining(lang_counts, LANGUAGE_FLOORS)["web_js_ts_html"],
            "action": "Prefer pnpm/npm workspace-aware probes with real test counts; avoid static-only web rows for transition claims.",
        },
    ]

    summary = {
        "stage": "stage11994_transition_root_250_supply_plan",
        "input_rows_path": str(ROWS_V4),
        "total_rows": len(rows),
        "unique_roots": len({root_key(row) for row in rows}),
        "language_counts": dict(sorted(lang_counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "repo_family_counts_top20": dict(repo_counts.most_common(20)),
        "unique_roots_by_language": {k: len(v) for k, v in sorted(unique_roots_by_lang.items())},
        "remaining_language_floor": remaining(lang_counts, LANGUAGE_FLOORS),
        "remaining_status_floor": remaining(status_counts, STATUS_FLOORS),
        "convertible_zero_test_not_exercised_candidates": convertible_zero_test,
        "underhydrated_negative_candidates_for_quarantine_or_reprobe": underhydrated_negative[:25],
        "priority_lanes": priority_lanes,
        "decision": "build_not_exercised_negative_admission_before_training",
        "claim_boundary": "Planning/support only. No frontier training or Gemma comparison is justified from v4 inventory scale.",
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    SUMMARY_MIRROR.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
