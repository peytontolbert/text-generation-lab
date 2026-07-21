#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12360_review_corrected_mixed_selected_test_decision"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
BASE_SCRIPT = ROOT / "scripts/build_stage12352_combined_train_support_ledger_v4.py"
BASE_SUMMARY = ROOT / "runs/summaries/stage12352_combined_train_support_ledger_v4.json"
STAGE12358_ROWS = ROOT / "runs/local/artifacts/stage12358_mixed_selected_test_admissions/mixed_selected_test_train_support_rows.jsonl"


def read_jsonl(path: Path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = read_jsonl(STAGE12358_ROWS)
    admitted = [row for row in rows if row.get("repo_family") == "einops/einops"]
    deferred = [row for row in rows if row.get("repo_family") == "OpenHands/OpenHands"]
    for row in deferred:
        row.setdefault("review_decision", {})["stage12360"] = {
            "decision": "defer_not_counted",
            "reason": "OpenHands same-family heldout/support risk; save Web PASS budget for fresher non-OpenHands families.",
        }
        row["admission"] = dict(row.get("admission") or {})
        row["admission"]["training_allowed"] = False
        row["admission"]["train_support_allowed"] = False
        row["blocked_reasons"] = list(set((row.get("blocked_reasons") or []) + ["stage12360_openhands_family_deferred"]))
    write_jsonl(OUT / "stage12360_admitted_einops_only_rows.jsonl", admitted)
    write_jsonl(OUT / "stage12360_deferred_openhands_rows.jsonl", deferred)

    subprocess.run(["python", str(BASE_SCRIPT)], cwd=str(ROOT), check=True)
    base = json.loads(BASE_SUMMARY.read_text(encoding="utf-8"))
    source_counts = dict(base.get("source_counts") or {})
    source_counts["stage12360_einops_only_from_stage12358"] = len(admitted)
    language_counts = dict(base.get("language_counts") or {})
    task_counts = dict(base.get("task_family_or_record_type_counts") or {})
    risky_counts = dict(base.get("risky_claim_counts_should_be_zero") or {})
    for row in admitted:
        language = row.get("language_family") or "session_unknown_language"
        language_counts[language] = language_counts.get(language, 0) + 1
        task = row.get("task_family") or row.get("record_type") or "unknown"
        task_counts[task] = task_counts.get(task, 0) + 1
        admission = row.get("admission") or {}
        for field in ["strict_eval_eligible", "source_heldout_admissible", "level3_admitted", "patch_trace_admitted", "repair_claim_admitted"]:
            if admission.get(field):
                risky_counts[field] = risky_counts.get(field, 0) + 1
    total = int(base.get("current_admitted_train_support_tasks") or 0) + len(admitted)
    ledger = dict(base)
    ledger.update({
        "stage": STAGE,
        "decision": "review_corrected_ledger_ready_openhands_deferred",
        "training_allowed": False,
        "claim_boundary": "Review-corrected ledger. Counts einops train-support rows only; OpenHands Stage12358 rows are deferred and not counted.",
        "current_admitted_train_support_tasks": total,
        "remaining_gap_to_500": max(0, 500 - total),
        "delta_vs_stage12324": total - 141,
        "source_counts": source_counts,
        "language_counts": language_counts,
        "task_family_or_record_type_counts": task_counts,
        "risky_claim_counts_should_be_zero": risky_counts,
        "stage12358_review_correction": {
            "admitted_einops_rows": len(admitted),
            "deferred_openhands_rows": len(deferred),
            "openhands_reason": "same-family heldout/support risk; avoid Web PASS_TO_PASS inflation",
        },
    })
    (OUT / "review_corrected_train_support_ledger.json").write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
