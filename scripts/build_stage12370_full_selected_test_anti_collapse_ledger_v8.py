#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12370_full_selected_test_anti_collapse_ledger_v8"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
BASE_SCRIPT = ROOT / "scripts/build_stage12352_combined_train_support_ledger_v4.py"
BASE_SUMMARY = ROOT / "runs/summaries/stage12352_combined_train_support_ledger_v4.json"
SELECTED_SOURCES = {
    "stage12322_priority_rust_cpp_selected_test": ROOT / "runs/local/artifacts/stage12322_priority_rust_cpp_selected_test_admission/priority_rust_cpp_selected_test_train_support_rows.jsonl",
    "stage12326_direct_python_selected_test": ROOT / "runs/local/artifacts/stage12326_direct_python_selected_test_admission/direct_python_selected_test_train_support_rows.jsonl",
    "stage12331_luxon_web_selected_test": ROOT / "runs/local/artifacts/stage12331_luxon_web_selected_test_admission/luxon_web_selected_test_train_support_rows.jsonl",
    "stage12339_openclaw_web_selected_test": ROOT / "runs/local/artifacts/stage12339_openclaw_web_selected_test_admission/openclaw_web_selected_test_train_support_rows.jsonl",
    "stage12343_openclaw_access_selected_test": ROOT / "runs/local/artifacts/stage12343_openclaw_access_selected_test_admission/openclaw_access_selected_test_train_support_rows.jsonl",
    "stage12351_web_fallback_selected_test": ROOT / "runs/local/artifacts/stage12351_web_fallback_selected_test_admissions/web_fallback_selected_test_train_support_rows.jsonl",
    "stage12360_einops_selected_test": ROOT / "runs/local/artifacts/stage12360_review_corrected_mixed_selected_test_decision/stage12360_admitted_einops_only_rows.jsonl",
    "stage12362_git_rust_selected_test": ROOT / "runs/local/artifacts/stage12362_git_rust_selected_test_admission/git_rust_selected_test_train_support_rows.jsonl",
    "stage12368_cpp_task_specific_selected_test": ROOT / "runs/local/artifacts/stage12368_cpp_task_specific_selected_test_admission/cpp_task_specific_selected_test_train_support_rows.jsonl",
}
NON_SELECTED_BASE_SOURCE_COUNTS = {
    "stage12320_event_local_observation": 76,
    "stage12323_v4_event_local": 15,
}
RISKY_FIELDS = ["strict_eval_eligible", "source_heldout_admissible", "level3_admitted", "patch_trace_admitted", "repair_claim_admitted"]
GENERIC_SELECTED_TEST_TARGETS = {
    "candidate_0",
    "selected_test_backed_verifier_candidate",
    "transition_candidate_selection::selected_test_backed_verifier_candidate",
}
TASK_SPECIFIC_PREFIXES = {
    "transition_next_action": ("transition_next_action::", "action_"),
    "transition_continue_or_stop": ("transition_continue_or_stop::", "policy_"),
    "transition_verifier_transition": ("transition_verifier_transition::", "status_"),
    "transition_evidence_citation": ("transition_evidence_citation::", "evidence_"),
}


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
    if row.get("target_semantic_id"):
        return str(row["target_semantic_id"])
    target = row.get("bounded_choice_target_label")
    for option in row.get("opaque_options") or []:
        if option.get("label") == target:
            return str(option.get("semantic_id") or option.get("canonical_value") or option.get("value") or option.get("role") or "")
    return str((row.get("target") or {}).get("semantic_value") or "")


def semantic_ok_for_task(task: str, semantic: str) -> bool:
    if task == "transition_candidate_selection":
        return bool(semantic)
    prefixes = TASK_SPECIFIC_PREFIXES.get(task)
    if not prefixes:
        return True
    if semantic in GENERIC_SELECTED_TEST_TARGETS:
        return False
    return semantic.startswith(prefixes)


def root_is_collapsed(rows: list[dict]) -> bool:
    semantics = {target_semantic(row) for row in rows}
    if len(semantics) <= 1:
        return True
    bad_non_candidate = [
        row for row in rows
        if row.get("task_family") != "transition_candidate_selection"
        and target_semantic(row) in GENERIC_SELECTED_TEST_TARGETS
    ]
    return bool(bad_non_candidate)


def mark_quarantined(row: dict, reason: str) -> dict:
    out = dict(row)
    out["admission"] = dict(out.get("admission") or {})
    out["admission"]["training_allowed"] = False
    out["admission"]["train_support_allowed"] = False
    out["blocked_reasons"] = sorted(set((out.get("blocked_reasons") or []) + [reason]))
    out["full_selected_test_anti_collapse_audit"] = {
        "stage": STAGE,
        "decision": "quarantine_non_task_specific_projection",
        "target_semantic": target_semantic(row),
        "reason": reason,
    }
    return out


def main() -> None:
    subprocess.run(["python", str(BASE_SCRIPT)], cwd=str(ROOT), check=True)
    base = json.loads(BASE_SUMMARY.read_text(encoding="utf-8"))
    admitted: list[dict] = []
    quarantined: list[dict] = []
    source_counts: Counter[str] = Counter()
    quarantine_counts: Counter[str] = Counter()
    root_audit: list[dict] = []

    for source_name, path in SELECTED_SOURCES.items():
        rows = read_jsonl(path)
        by_root: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            by_root[row.get("root_id") or row.get("root_lineage_key") or row.get("row_id")].append(row)
        for root_id, root_rows in sorted(by_root.items()):
            collapsed = root_is_collapsed(root_rows)
            target_semantics = sorted({target_semantic(row) for row in root_rows})
            admitted_for_root = 0
            quarantined_for_root = 0
            for row in root_rows:
                task = row.get("task_family") or row.get("record_type") or ""
                semantic = target_semantic(row)
                if collapsed and task != "transition_candidate_selection":
                    quarantined.append(mark_quarantined(row, "semantic_collapse_same_selected_test_target_across_task_families"))
                    quarantine_counts[source_name] += 1
                    quarantined_for_root += 1
                elif not semantic_ok_for_task(task, semantic):
                    quarantined.append(mark_quarantined(row, "target_semantic_not_task_specific"))
                    quarantine_counts[source_name] += 1
                    quarantined_for_root += 1
                else:
                    admitted.append(row)
                    source_counts[source_name] += 1
                    admitted_for_root += 1
            root_audit.append({
                "source": source_name,
                "root_id": root_id,
                "collapsed": collapsed,
                "target_semantics": target_semantics,
                "admitted": admitted_for_root,
                "quarantined": quarantined_for_root,
            })

    language_counts: Counter[str] = Counter({"session_unknown_language": 91})
    task_counts: Counter[str] = Counter({"event_local_transition_observation": 91})
    risky_counts: Counter[str] = Counter()
    for row in admitted:
        language_counts[row.get("language_family") or "session_unknown_language"] += 1
        task_counts[row.get("task_family") or row.get("record_type") or "unknown"] += 1
        admission = row.get("admission") or {}
        for field in RISKY_FIELDS:
            if admission.get(field) or row.get(field):
                risky_counts[field] += 1
    total = sum(NON_SELECTED_BASE_SOURCE_COUNTS.values()) + len(admitted)
    combined_source_counts = dict(NON_SELECTED_BASE_SOURCE_COUNTS)
    combined_source_counts.update(dict(source_counts))
    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUT / "full_selected_test_anti_collapse_admitted_rows.jsonl", admitted)
    write_jsonl(OUT / "full_selected_test_anti_collapse_quarantined_rows.jsonl", quarantined)
    ledger = {
        "stage": STAGE,
        "decision": "full_selected_test_anti_collapse_ledger_ready_500_not_reached",
        "training_allowed": False,
        "claim_boundary": "Ledger/audit artifact. Selected-test rows are counted only when task semantics are specific; collapsed projections are quarantined.",
        "supersedes": [
            str(BASE_SUMMARY),
            str(ROOT / "runs/summaries/stage12366_selected_test_semantic_collapse_audit.json"),
            str(ROOT / "runs/summaries/stage12369_combined_train_support_ledger_v7.json"),
        ],
        "base_stage12352_reported_rows_before_full_anti_collapse": base.get("current_admitted_train_support_tasks"),
        "current_admitted_train_support_tasks": total,
        "remaining_gap_to_500": max(0, 500 - total),
        "non_selected_base_rows": sum(NON_SELECTED_BASE_SOURCE_COUNTS.values()),
        "selected_test_rows_admitted_after_audit": len(admitted),
        "selected_test_rows_quarantined_after_audit": len(quarantined),
        "source_counts": combined_source_counts,
        "quarantined_source_counts": dict(quarantine_counts),
        "language_counts": dict(language_counts),
        "task_family_or_record_type_counts": dict(task_counts),
        "risky_claim_counts_should_be_zero": dict(risky_counts),
        "root_audit": root_audit,
        "rule": {
            "collapsed_root": "If a root uses the same generic selected-test candidate as target across task families, only transition_candidate_selection may count.",
            "task_specific_required": "next_action/continue_or_stop/verifier_transition/evidence_citation must target action/policy/status/evidence semantics respectively.",
            "replacement_path": "Re-render collapsed roots with task-specific target vocabularies rather than deleting the underlying verifier evidence.",
        },
    }
    (OUT / "full_selected_test_anti_collapse_ledger_v8.json").write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
