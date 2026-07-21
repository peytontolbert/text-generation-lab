#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12375_combined_train_support_ledger_v10"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
BASE_SCRIPT = ROOT / "scripts/build_stage12370_full_selected_test_anti_collapse_ledger_v8.py"
BASE_SUMMARY = ROOT / "runs/summaries/stage12370_full_selected_test_anti_collapse_ledger_v8.json"
BASE_ROWS = ROOT / "runs/local/artifacts/stage12370_full_selected_test_anti_collapse_ledger_v8/full_selected_test_anti_collapse_admitted_rows.jsonl"
CPP_RERENDER = ROOT / "runs/local/artifacts/stage12368_cpp_task_specific_selected_test_admission/cpp_task_specific_selected_test_train_support_rows.jsonl"
GIT_RERENDER = ROOT / "runs/local/artifacts/stage12372_git_rust_task_specific_selected_test_rerender/git_rust_task_specific_selected_test_rows.jsonl"
SUPERSEDED_ROOTS = {
    "stage12118::c_cpp::002::Neargye_magic_enum",
    "stage12118::c_cpp::019::fastfloat_fast_float",
    "stage12362::rust::gitcore_varint_decode",
}
NON_SELECTED_BASE_ROWS = 91
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


def target_semantic(row: dict) -> str:
    if row.get("target_semantic_id"):
        return str(row["target_semantic_id"])
    target = row.get("bounded_choice_target_label")
    for option in row.get("opaque_options") or []:
        if option.get("label") == target:
            return str(option.get("semantic_id") or option.get("canonical_value") or option.get("value") or "")
    return ""


def main() -> None:
    subprocess.run(["python", str(BASE_SCRIPT)], cwd=str(ROOT), check=True)
    base = json.loads(BASE_SUMMARY.read_text(encoding="utf-8"))
    base_rows = read_jsonl(BASE_ROWS)
    cpp_rows = read_jsonl(CPP_RERENDER)
    git_rows = read_jsonl(GIT_RERENDER)
    superseded_rows = [row for row in base_rows if row.get("root_id") in SUPERSEDED_ROOTS]
    kept_base_rows = [row for row in base_rows if row.get("root_id") not in SUPERSEDED_ROOTS]
    selected_rows = kept_base_rows + cpp_rows + git_rows

    source_counts = dict(base.get("source_counts") or {})
    source_counts["stage12322_priority_rust_cpp_selected_test_superseded_candidate_only"] = 0
    source_counts["stage12362_git_rust_selected_test_superseded_candidate_only"] = 0
    source_counts["stage12368_cpp_task_specific_selected_test"] = len(cpp_rows)
    source_counts["stage12372_git_rust_task_specific_rerender"] = len(git_rows)

    language_counts: Counter[str] = Counter({"session_unknown_language": NON_SELECTED_BASE_ROWS})
    task_counts: Counter[str] = Counter({"event_local_transition_observation": NON_SELECTED_BASE_ROWS})
    semantic_by_root: dict[str, set[str]] = {}
    for row in selected_rows:
        language_counts[row.get("language_family") or "session_unknown_language"] += 1
        task_counts[row.get("task_family") or row.get("record_type") or "unknown"] += 1
        if row.get("stage") in {"stage12368_cpp_task_specific_selected_test_admission", "stage12372_git_rust_task_specific_selected_test_rerender"}:
            semantic_by_root.setdefault(row.get("root_id") or row.get("row_id"), set()).add(target_semantic(row))

    anti_collapse_failures = {root: sorted(values) for root, values in semantic_by_root.items() if len(values) < 5}
    total = NON_SELECTED_BASE_ROWS + len(selected_rows)
    ledger = dict(base)
    ledger.update({
        "stage": STAGE,
        "decision": "combined_train_support_ledger_v10_ready_500_not_reached" if not anti_collapse_failures and not risky_counts(selected_rows) else "combined_train_support_ledger_v10_needs_review",
        "training_allowed": False,
        "claim_boundary": "Authoritative current ledger. Training remains blocked until row count and QC gates are met; row-local admission is not global training clearance.",
        "supersedes": [
            str(BASE_SUMMARY),
            str(ROOT / "runs/summaries/stage12368_cpp_task_specific_selected_test_admission.json"),
            str(ROOT / "runs/summaries/stage12372_git_rust_task_specific_selected_test_rerender.json"),
            str(ROOT / "runs/summaries/stage12373_combined_train_support_ledger_v9.json"),
        ],
        "current_admitted_train_support_tasks": total,
        "remaining_gap_to_500": max(0, 500 - total),
        "non_selected_base_rows": NON_SELECTED_BASE_ROWS,
        "selected_test_rows_admitted_after_audit": len(selected_rows),
        "selected_test_rows_superseded_from_base": len(superseded_rows),
        "superseded_roots": sorted(SUPERSEDED_ROOTS),
        "source_counts": source_counts,
        "language_counts": dict(language_counts),
        "task_family_or_record_type_counts": dict(task_counts),
        "risky_claim_counts_should_be_zero": risky_counts(selected_rows),
        "rerender_target_semantic_values_by_root": {root: sorted(values) for root, values in semantic_by_root.items()},
        "anti_collapse_failures_should_be_empty": anti_collapse_failures,
        "training_blockers": [
            "500_train_support_target_not_reached",
            "Stage12374_python_task_specific_rerender_pending",
            "Open-SWE/MCP transformation rows not yet admitted under Stage12364 policy",
        ],
    })
    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUT / "combined_selected_test_rows_v10.jsonl", selected_rows)
    write_jsonl(OUT / "superseded_base_selected_test_rows_v10.jsonl", superseded_rows)
    (OUT / "combined_train_support_ledger_v10.json").write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
