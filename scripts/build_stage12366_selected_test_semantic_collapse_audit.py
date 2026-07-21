#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12366_selected_test_semantic_collapse_audit"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
BASE_SCRIPT = ROOT / "scripts/build_stage12352_combined_train_support_ledger_v4.py"
BASE_SUMMARY = ROOT / "runs/summaries/stage12352_combined_train_support_ledger_v4.json"
SOURCES = {
    "stage12360_einops_candidate_only": ROOT / "runs/local/artifacts/stage12360_review_corrected_mixed_selected_test_decision/stage12360_admitted_einops_only_rows.jsonl",
    "stage12362_git_rust_candidate_only": ROOT / "runs/local/artifacts/stage12362_git_rust_selected_test_admission/git_rust_selected_test_train_support_rows.jsonl",
}
VALID_SELECTED_TEST_TASK = "transition_candidate_selection"
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


def target_semantic(row: dict) -> str:
    target = row.get("bounded_choice_target_label")
    for option in row.get("opaque_options") or []:
        if option.get("label") == target:
            return str(option.get("semantic_id") or "")
    return ""


def mark_quarantined(row: dict, reason: str) -> dict:
    out = dict(row)
    out["admission"] = dict(out.get("admission") or {})
    out["admission"]["training_allowed"] = False
    out["admission"]["train_support_allowed"] = False
    out["blocked_reasons"] = sorted(set((out.get("blocked_reasons") or []) + [reason]))
    out["semantic_collapse_audit"] = {
        "stage": STAGE,
        "decision": "quarantine_until_task_specific_target_rendering",
        "reason": reason,
    }
    return out


def row_allowed(row: dict, root_targets: dict[str, set[str]]) -> tuple[bool, str]:
    task = row.get("task_family") or row.get("record_type")
    semantic = target_semantic(row)
    root_id = row.get("root_id") or row.get("root_lineage_key") or row.get("row_id")
    if task == VALID_SELECTED_TEST_TASK:
        return True, ""
    if semantic == "candidate_0" and len(root_targets[root_id]) <= 1:
        return False, "semantic_collapse_same_candidate0_target_across_task_families"
    if task in {
        "transition_continue_or_stop",
        "transition_evidence_citation",
        "transition_next_action",
        "transition_verifier_transition",
    } and semantic == "candidate_0":
        return False, "selected_test_candidate_target_not_task_specific"
    return True, ""


def main() -> None:
    subprocess.run(["python", str(BASE_SCRIPT)], cwd=str(ROOT), check=True)
    base = json.loads(BASE_SUMMARY.read_text(encoding="utf-8"))
    admitted: list[dict] = []
    quarantined: list[dict] = []
    source_counts: dict[str, int] = {}
    source_quarantine_counts: dict[str, int] = {}
    collapse_groups: dict[str, list[dict]] = {}

    for source_name, path in SOURCES.items():
        rows = read_jsonl(path)
        root_targets: dict[str, set[str]] = defaultdict(set)
        for row in rows:
            root_targets[row.get("root_id") or row.get("row_id")].add(target_semantic(row))
        collapse_groups[source_name] = [
            {
                "root_id": root_id,
                "target_semantic_values": sorted(values),
                "collapsed": len(values) <= 1,
            }
            for root_id, values in sorted(root_targets.items())
        ]
        for row in rows:
            allowed, reason = row_allowed(row, root_targets)
            if allowed:
                admitted.append(row)
                source_counts[source_name] = source_counts.get(source_name, 0) + 1
            else:
                quarantined.append(mark_quarantined(row, reason))
                source_quarantine_counts[source_name] = source_quarantine_counts.get(source_name, 0) + 1

    language_counts = dict(base.get("language_counts") or {})
    task_counts = dict(base.get("task_family_or_record_type_counts") or {})
    risky_counts = dict(base.get("risky_claim_counts_should_be_zero") or {})
    for row in admitted:
        language = row.get("language_family") or "session_unknown_language"
        language_counts[language] = language_counts.get(language, 0) + 1
        task = row.get("task_family") or row.get("record_type") or "unknown"
        task_counts[task] = task_counts.get(task, 0) + 1
        admission = row.get("admission") or {}
        for field in RISKY_FIELDS:
            if admission.get(field):
                risky_counts[field] = risky_counts.get(field, 0) + 1

    total = int(base.get("current_admitted_train_support_tasks") or 0) + len(admitted)
    combined_source_counts = dict(base.get("source_counts") or {})
    combined_source_counts.update(source_counts)

    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUT / "anti_collapse_admitted_rows.jsonl", admitted)
    write_jsonl(OUT / "anti_collapse_quarantined_rows.jsonl", quarantined)
    audit = {
        "stage": STAGE,
        "decision": "selected_test_semantic_collapse_corrected_ledger_ready",
        "training_allowed": False,
        "claim_boundary": "Ledger/audit artifact. Counts only selected-test candidate-selection rows from collapsed root projections; quarantines non-task-specific projections.",
        "base_ledger_ref": str(BASE_SUMMARY),
        "base_train_support_rows": base.get("current_admitted_train_support_tasks"),
        "admitted_rows_from_audited_sources": len(admitted),
        "quarantined_rows_from_audited_sources": len(quarantined),
        "current_admitted_train_support_tasks": total,
        "remaining_gap_to_500": max(0, 500 - total),
        "source_counts": combined_source_counts,
        "quarantined_source_counts": source_quarantine_counts,
        "language_counts": language_counts,
        "task_family_or_record_type_counts": task_counts,
        "risky_claim_counts_should_be_zero": risky_counts,
        "collapse_groups": collapse_groups,
        "rule": {
            "candidate_selection": "may use selected-test-backed candidate when decoys are real alternatives",
            "other_transition_families": "must use task-specific targets: action, stop policy, verifier status, or evidence ref/class",
            "blocked_pattern": "same candidate_0 target reused across 3+ task families for one root",
        },
    }
    (OUT / "selected_test_semantic_collapse_audit.json").write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
