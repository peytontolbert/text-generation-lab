#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_SCRIPT = ROOT / "scripts/build_stage12360_review_corrected_mixed_selected_test_decision.py"
BASE_SUMMARY = ROOT / "runs/summaries/stage12360_review_corrected_mixed_selected_test_decision.json"
STAGE = "stage12363_combined_train_support_ledger_v6"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
EXTRA = ROOT / "runs/local/artifacts/stage12362_git_rust_selected_test_admission/git_rust_selected_test_train_support_rows.jsonl"


def read_jsonl(path: Path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    subprocess.run(["python", str(BASE_SCRIPT)], cwd=str(ROOT), check=True)
    base = json.loads(BASE_SUMMARY.read_text(encoding="utf-8"))
    extra_rows = read_jsonl(EXTRA)
    source_counts = dict(base.get("source_counts") or {})
    source_counts["stage12362_git_rust_selected_test"] = len(extra_rows)
    language_counts = dict(base.get("language_counts") or {})
    task_counts = dict(base.get("task_family_or_record_type_counts") or {})
    risky_counts = dict(base.get("risky_claim_counts_should_be_zero") or {})
    for row in extra_rows:
        language = row.get("language_family") or "session_unknown_language"
        language_counts[language] = language_counts.get(language, 0) + 1
        task = row.get("task_family") or row.get("record_type") or "unknown"
        task_counts[task] = task_counts.get(task, 0) + 1
        admission = row.get("admission") or {}
        for field in ["strict_eval_eligible", "source_heldout_admissible", "level3_admitted", "patch_trace_admitted", "repair_claim_admitted"]:
            if admission.get(field):
                risky_counts[field] = risky_counts.get(field, 0) + 1
    total = int(base.get("current_admitted_train_support_tasks") or 0) + len(extra_rows)
    ledger = dict(base)
    ledger.update({
        "stage": STAGE,
        "decision": "combined_train_support_ledger_v6_ready_500_not_reached",
        "current_admitted_train_support_tasks": total,
        "remaining_gap_to_500": max(0, 500 - total),
        "delta_vs_stage12324": total - 141,
        "source_counts": source_counts,
        "language_counts": language_counts,
        "task_family_or_record_type_counts": task_counts,
        "risky_claim_counts_should_be_zero": risky_counts,
    })
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "combined_train_support_ledger_v6.json").write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
