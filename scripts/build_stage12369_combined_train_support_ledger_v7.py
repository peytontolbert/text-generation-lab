#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12369_combined_train_support_ledger_v7"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
BASE_SCRIPT = ROOT / "scripts/build_stage12366_selected_test_semantic_collapse_audit.py"
BASE_SUMMARY = ROOT / "runs/summaries/stage12366_selected_test_semantic_collapse_audit.json"
EXTRA = ROOT / "runs/local/artifacts/stage12368_cpp_task_specific_selected_test_admission/cpp_task_specific_selected_test_train_support_rows.jsonl"
RISKY_FIELDS = ["strict_eval_eligible", "source_heldout_admissible", "level3_admitted", "patch_trace_admitted", "repair_claim_admitted"]


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    subprocess.run(["python", str(BASE_SCRIPT)], cwd=str(ROOT), check=True)
    base = json.loads(BASE_SUMMARY.read_text(encoding="utf-8"))
    extra_rows = read_jsonl(EXTRA)
    source_counts = dict(base.get("source_counts") or {})
    source_counts["stage12368_cpp_task_specific_selected_test"] = len(extra_rows)
    language_counts = dict(base.get("language_counts") or {})
    task_counts = dict(base.get("task_family_or_record_type_counts") or {})
    risky_counts = dict(base.get("risky_claim_counts_should_be_zero") or {})
    target_semantics_by_root: dict[str, set[str]] = {}
    for row in extra_rows:
        language = row.get("language_family") or "session_unknown_language"
        language_counts[language] = language_counts.get(language, 0) + 1
        task = row.get("task_family") or row.get("record_type") or "unknown"
        task_counts[task] = task_counts.get(task, 0) + 1
        target_semantics_by_root.setdefault(row.get("root_id") or row.get("row_id"), set()).add(row.get("target_semantic_id") or "")
        admission = row.get("admission") or {}
        for field in RISKY_FIELDS:
            if admission.get(field):
                risky_counts[field] = risky_counts.get(field, 0) + 1
    anti_collapse_failures = {
        root_id: sorted(values)
        for root_id, values in target_semantics_by_root.items()
        if len(values) < 5
    }
    total = int(base.get("current_admitted_train_support_tasks") or 0) + len(extra_rows)
    ledger = dict(base)
    ledger.update({
        "stage": STAGE,
        "decision": "combined_train_support_ledger_v7_ready_500_not_reached" if not anti_collapse_failures and not risky_counts else "combined_train_support_ledger_v7_needs_review",
        "current_admitted_train_support_tasks": total,
        "remaining_gap_to_500": max(0, 500 - total),
        "source_counts": source_counts,
        "language_counts": language_counts,
        "task_family_or_record_type_counts": task_counts,
        "risky_claim_counts_should_be_zero": risky_counts,
        "stage12368_added_rows": len(extra_rows),
        "stage12368_target_semantic_values_by_root": {key: sorted(value) for key, value in target_semantics_by_root.items()},
        "anti_collapse_failures_should_be_empty": anti_collapse_failures,
    })
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "combined_train_support_ledger_v7.json").write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
