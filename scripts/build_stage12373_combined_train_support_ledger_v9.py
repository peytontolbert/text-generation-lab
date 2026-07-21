#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12373_combined_train_support_ledger_v9"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
BASE_SCRIPT = ROOT / "scripts/build_stage12370_full_selected_test_anti_collapse_ledger_v8.py"
BASE_SUMMARY = ROOT / "runs/summaries/stage12370_full_selected_test_anti_collapse_ledger_v8.json"
BASE_ROWS = ROOT / "runs/local/artifacts/stage12370_full_selected_test_anti_collapse_ledger_v8/full_selected_test_anti_collapse_admitted_rows.jsonl"
EXTRA = ROOT / "runs/local/artifacts/stage12372_git_rust_task_specific_selected_test_rerender/git_rust_task_specific_selected_test_rows.jsonl"
SUPERSEDED_ROOTS = {"stage12362::rust::gitcore_varint_decode"}
RISKY_FIELDS = ["strict_eval_eligible", "source_heldout_admissible", "level3_admitted", "patch_trace_admitted", "repair_claim_admitted"]


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def risky_counts(rows: list[dict]) -> dict:
    counts: Counter[str] = Counter()
    for row in rows:
        admission = row.get("admission") or {}
        for field in RISKY_FIELDS:
            if admission.get(field) or row.get(field):
                counts[field] += 1
    return dict(counts)


def main() -> None:
    subprocess.run(["python", str(BASE_SCRIPT)], cwd=str(ROOT), check=True)
    base = json.loads(BASE_SUMMARY.read_text(encoding="utf-8"))
    base_rows = read_jsonl(BASE_ROWS)
    extra_rows = read_jsonl(EXTRA)
    kept_base_rows = [row for row in base_rows if row.get("root_id") not in SUPERSEDED_ROOTS]
    selected_rows = kept_base_rows + extra_rows
    source_counts = dict(base.get("source_counts") or {})
    source_counts["stage12362_git_rust_selected_test"] = 0
    source_counts["stage12372_git_rust_task_specific_rerender"] = len(extra_rows)
    language_counts: Counter[str] = Counter({"session_unknown_language": 91})
    task_counts: Counter[str] = Counter({"event_local_transition_observation": 91})
    for row in selected_rows:
        language_counts[row.get("language_family") or "session_unknown_language"] += 1
        task_counts[row.get("task_family") or row.get("record_type") or "unknown"] += 1
    total = 91 + len(selected_rows)
    target_semantics_by_root: dict[str, set[str]] = {}
    for row in extra_rows:
        target_semantics_by_root.setdefault(row.get("root_id") or row.get("row_id"), set()).add(row.get("target_semantic_id") or "")
    anti_collapse_failures = {
        root_id: sorted(values)
        for root_id, values in target_semantics_by_root.items()
        if len(values) < 5
    }
    ledger = dict(base)
    ledger.update({
        "stage": STAGE,
        "decision": "combined_train_support_ledger_v9_ready_500_not_reached" if not anti_collapse_failures and not risky_counts(selected_rows) else "combined_train_support_ledger_v9_needs_review",
        "current_admitted_train_support_tasks": total,
        "remaining_gap_to_500": max(0, 500 - total),
        "non_selected_base_rows": 91,
        "selected_test_rows_admitted_after_audit": len(selected_rows),
        "source_counts": source_counts,
        "language_counts": dict(language_counts),
        "task_family_or_record_type_counts": dict(task_counts),
        "risky_claim_counts_should_be_zero": risky_counts(selected_rows),
        "superseded_roots": sorted(SUPERSEDED_ROOTS),
        "stage12372_added_rows": len(extra_rows),
        "stage12372_target_semantic_values_by_root": {key: sorted(value) for key, value in target_semantics_by_root.items()},
        "anti_collapse_failures_should_be_empty": anti_collapse_failures,
    })
    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUT / "combined_selected_test_rows_v9.jsonl", selected_rows)
    (OUT / "combined_train_support_ledger_v9.json").write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
