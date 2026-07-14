#!/usr/bin/env python3
"""Roll Stage11992 PASS_CURRENT_BUILD_AND_RUN rows into transition support v4."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ROOT = Path("runs/local/artifacts/stage11993_transition_support_rollup_v4")
BASE = Path("runs/local/artifacts/stage11990_transition_support_rollup_v3/transition_support_rows_v3.jsonl")
ADDED = Path(
    "runs/local/artifacts/stage11992_pass_build_and_run_admission_audit/"
    "pass_build_and_run_admitted_rows.jsonl"
)
ROWS_OUT = ROOT / "transition_support_rows_v4.jsonl"
SUMMARY = ROOT / "transition_support_rollup_v4.json"
SUMMARY_MIRROR = Path("runs/summaries/stage11993_transition_support_rollup_v4.json")


LANGUAGE_FLOORS = {
    "python": 50,
    "rust": 50,
    "c_cpp": 50,
    "web_js_ts_html": 50,
}
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


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def root_key(row: dict) -> str | None:
    return (
        row.get("root_lineage_key")
        or row.get("root_id")
        or row.get("source_root_id")
        or row.get("source_bundle_id")
        or row.get("row_id")
    )


def key(row: dict) -> tuple[str | None, str | None, str | None]:
    return (
        row.get("row_id"),
        root_key(row),
        row.get("observed_verifier_transition"),
    )


def retag_base(row: dict) -> dict:
    out = dict(row)
    out["stage11993_source"] = "stage11990"
    return out


def retag_added(row: dict) -> dict:
    out = dict(row)
    out["split"] = "train"
    out["split_role"] = "stage11993_transition_support_v4_train_support_only"
    out["train_support_only"] = True
    out["strict_eval_eligible"] = False
    out["source_heldout_admissible"] = False
    out["stage11993_source"] = "stage11992"
    return out


def remaining_floor(counts: Counter, floors: dict[str, int]) -> dict[str, int]:
    return {k: max(0, target - counts.get(k, 0)) for k, target in floors.items()}


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    SUMMARY_MIRROR.parent.mkdir(parents=True, exist_ok=True)

    base_rows = [retag_base(row) for row in read_jsonl(BASE)]
    added_rows = [retag_added(row) for row in read_jsonl(ADDED)]

    rows: list[dict] = []
    seen: set[tuple[str | None, str | None, str | None]] = set()
    duplicates = 0
    for row in base_rows + added_rows:
        row_key = key(row)
        if row_key in seen:
            duplicates += 1
            continue
        seen.add(row_key)
        rows.append(row)

    write_jsonl(ROWS_OUT, rows)

    language_counts = Counter(row.get("language_family") for row in rows)
    status_counts = Counter(row.get("observed_verifier_transition") for row in rows)
    repo_counts = Counter(row.get("repo_family") for row in rows)
    unique_roots = {root_key(row) for row in rows}

    summary = {
        "stage": "stage11993_transition_support_rollup_v4",
        "base_rows_path": str(BASE),
        "added_rows_path": str(ADDED),
        "rows_path": str(ROWS_OUT),
        "base_rows": len(base_rows),
        "added_rows": len(added_rows),
        "duplicate_rows_skipped": duplicates,
        "total_rows": len(rows),
        "unique_roots": len(unique_roots),
        "language_counts": dict(sorted(language_counts.items())),
        "repo_family_counts_top20": dict(repo_counts.most_common(20)),
        "status_counts": dict(sorted(status_counts.items())),
        "remaining_language_floor": remaining_floor(language_counts, LANGUAGE_FLOORS),
        "remaining_status_floor": remaining_floor(status_counts, STATUS_FLOORS),
        "decision": "support_inventory_v4_not_train_ready",
        "reason": (
            "PASS_CURRENT_BUILD_AND_RUN coverage improved, but root/language/status floors remain far below Transition-Root-250."
        ),
        "next_stage_recommendation": {
            "stage": "stage11994_transition_root_250_supply_plan",
            "action": "Target missing FAIL/NOT_EXERCISED/INSUFFICIENT and additional C/C++/Rust/Web independent roots before another training probe.",
        },
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    SUMMARY_MIRROR.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
