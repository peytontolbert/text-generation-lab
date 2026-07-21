#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12414_selected_test_verifier_log_materialization"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

WORKLIST = ROOT / "runs/local/artifacts/stage12407_prioritized_adapter_materialization_worklist/prioritized_adapter_materialization_worklist.jsonl"
SOURCE_ADAPTERS = ROOT / "runs/local/artifacts/stage12406_transition_source_expansion_preflight/source_adapter_candidates.jsonl"
COMBINED_SELECTED_ROWS = ROOT / "runs/local/artifacts/stage12385_combined_train_support_ledger_v15_dedup/combined_selected_test_rows_v15_dedup.jsonl"
COMBINED_LEDGER = ROOT / "runs/local/artifacts/stage12385_combined_train_support_ledger_v15_dedup/combined_train_support_ledger_v15_dedup.json"
STAGE12203_LEVEL3 = ROOT / "runs/local/artifacts/stage12203_controlled_selected_verifier_replay/level3_episode_records.jsonl"
STAGE12203_COMMANDS = ROOT / "runs/local/artifacts/stage12203_controlled_selected_verifier_replay/command_results.jsonl"
STAGE12207_LEVEL3 = ROOT / "runs/local/artifacts/stage12207_no_install_selected_test_log_level3_joiner/no_install_selected_test_level3_records.jsonl"
STAGE12215_LEVEL3 = ROOT / "runs/local/artifacts/stage12215_hydratable_selected_verifier_reexecution/level3_reexecution_records.jsonl"
STAGE12215_OBSERVATIONS = ROOT / "runs/local/artifacts/stage12215_hydratable_selected_verifier_reexecution/reexecution_observations.jsonl"

TASKS = [
    "transition_candidate_selection",
    "transition_next_action",
    "transition_continue_or_stop",
    "transition_evidence_citation",
    "transition_verifier_transition",
]

REAL_LOG_STAGES = {
    "stage12203_controlled_selected_verifier_replay",
    "stage12207_no_install_selected_test_log_level3_joiner",
    "stage12215_hydratable_selected_verifier_reexecution",
}

BLOCKED_SOURCE_PATH_REASONS = {
    "10ef201641c8646f1137e980": "stage12322_adapter_artifact_not_direct_real_verifier_log",
    "5fe72d88ae4aa24f0b9cd355": "stage12322_summary_not_direct_real_verifier_log",
    "c5d3d1c7f1abd42a730a8f73": "stage12322_summary_not_direct_real_verifier_log",
    "9c723412cf35632c02cedfa9": "stage12326_summary_not_direct_real_verifier_log",
    "a285a1b11e47b01ce31c7da9": "stage12355_control_artifact_only_not_real_verifier_log",
    "0337cb07cc28ec8810fbad15": "stage12355_control_summary_only_not_real_verifier_log",
    "75a644de09c32c235a6459e0": "stage12360_review_ledger_not_direct_real_verifier_log",
    "1b4aa964b2b1e51da6494374": "stage12360_review_summary_not_direct_real_verifier_log",
}


TARGETS = {
    "candidate_selected_test_backed",
    "action_run_selected_verifier",
    "policy_stop_selected_verifier_passed",
    "evidence_selected_verifier_log",
    "status_pass_current_state",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    return value if isinstance(value, dict) else {}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:n]


def iter_strings(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            found.append(str(key))
            found.extend(iter_strings(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(iter_strings(child))
    elif isinstance(value, str):
        found.append(value)
    return found


def load_real_log_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for stage, path in [
        ("stage12203_controlled_selected_verifier_replay", STAGE12203_LEVEL3),
        ("stage12203_controlled_selected_verifier_replay", STAGE12203_COMMANDS),
        ("stage12207_no_install_selected_test_log_level3_joiner", STAGE12207_LEVEL3),
        ("stage12215_hydratable_selected_verifier_reexecution", STAGE12215_LEVEL3),
        ("stage12215_hydratable_selected_verifier_reexecution", STAGE12215_OBSERVATIONS),
    ]:
        for row in read_jsonl(path):
            row = dict(row)
            row["_real_log_stage"] = stage
            rows.append(row)
    return rows


def direct_real_log_join(work_item: dict[str, Any], real_log_rows: list[dict[str, Any]]) -> dict[str, Any]:
    source_ref_hash = str(work_item.get("source_adapter_ref_hash") or "")
    source_stage = str(work_item.get("source_stage") or "")
    hash_hits = []
    stage_hits = []
    for row in real_log_rows:
        strings = set(iter_strings(row))
        if source_ref_hash in strings:
            hash_hits.append(row.get("_real_log_stage"))
        if source_stage == row.get("_real_log_stage") or source_stage == row.get("source_stage"):
            stage_hits.append(row.get("_real_log_stage"))
    return {
        "source_ref_hash_direct_hit_count": len(hash_hits),
        "source_ref_hash_direct_hit_stages": sorted(set(hash_hits)),
        "source_stage_direct_hit_count": len(stage_hits),
        "source_stage_direct_hit_stages": sorted(set(stage_hits)),
    }


def stage12322_null_target_count(selected_rows: list[dict[str, Any]]) -> int:
    return sum(
        1
        for row in selected_rows
        if row.get("stage") == "stage12322_priority_rust_cpp_selected_test_admission"
        and row.get("target_semantic_id") in {None, ""}
    )


def blocked_reasons_for(
    work_item: dict[str, Any],
    adapter: dict[str, Any],
    join: dict[str, Any],
    selected_rows: list[dict[str, Any]],
) -> list[str]:
    reasons = [
        "stage12407_work_item_is_request_only_not_real_verifier_log",
        "stage12406_source_adapter_candidate_is_hash_inventory_only",
        "rows_derived_only_from_stage12406_12407_hashes_are_disallowed",
        "missing_command_result_verifier_anchor_selected_test_anchor_state_update_stop_decision_join",
        "missing_source_test_hash_refs_joined_to_real_verifier_log_artifact",
        "missing_selected_test_scope_proof_joined_to_real_verifier_log_artifact",
        "missing_verifier_identity_or_output_class_joined_from_real_log",
    ]
    source_ref_hash = str(work_item.get("source_adapter_ref_hash") or "")
    source_stage = str(work_item.get("source_stage") or "")
    source_path_hash = str(adapter.get("source_path_hash") or "")
    if join["source_ref_hash_direct_hit_count"] == 0:
        reasons.append("source_ref_hash_not_present_in_stage12203_12207_12215_verifier_log_artifacts")
    if join["source_stage_direct_hit_count"] == 0 or source_stage not in REAL_LOG_STAGES:
        reasons.append("source_stage_points_to_selected_test_adapter_or_control_stage_not_real_verifier_log_stage")
    if source_path_hash in BLOCKED_SOURCE_PATH_REASONS:
        reasons.append(BLOCKED_SOURCE_PATH_REASONS[source_path_hash])
    if "stage12322" in source_stage and stage12322_null_target_count(selected_rows) > 0:
        reasons.append("stage12322_rows_have_null_target_semantic_id_do_not_reuse_blindly")
    if not source_ref_hash:
        reasons.append("missing_source_adapter_ref_hash")
    return sorted(set(reasons))


def guardrail_scan(rows: list[dict[str, Any]], blocked_items: list[dict[str, Any]]) -> dict[str, Any]:
    row_ids = [row.get("row_id") for row in rows]
    duplicate_row_ids = sorted(row_id for row_id, count in Counter(row_ids).items() if row_id and count > 1)
    generic_target_count = sum(1 for row in rows if row.get("target_semantic_id") == "selected_test_backed_verifier_candidate")
    risky_claim_counts = Counter()
    for row in rows:
        admission = row.get("admission") or {}
        for key in [
            "strict_eval_eligible",
            "source_heldout_admissible",
            "level3_admitted",
            "patch_trace_admitted",
            "repair_claim_admitted",
        ]:
            if admission.get(key) is True:
                risky_claim_counts[f"{key}_true"] += 1
        if row.get("target_semantic_id") not in TARGETS:
            risky_claim_counts["unexpected_target_semantic_id"] += 1
    return {
        "stage": STAGE,
        "scan_passed": not rows and not duplicate_row_ids and not risky_claim_counts,
        "fail_closed_zero_admission": True,
        "duplicate_row_ids": duplicate_row_ids,
        "duplicate_row_id_count": len(duplicate_row_ids),
        "generic_target_count": generic_target_count,
        "raw_leak_count": 0,
        "raw_leak_issues": [],
        "risky_claim_counts": dict(sorted(risky_claim_counts.items())),
        "target_semantic_collapse_count": 0,
        "blocked_item_count": len(blocked_items),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    work_items = [
        row
        for row in read_jsonl(WORKLIST)
        if row.get("recommended_next_action") == "materialize_selected_test_verifier_logs"
    ]
    adapters = {row.get("source_ref_hash"): row for row in read_jsonl(SOURCE_ADAPTERS)}
    selected_rows = read_jsonl(COMBINED_SELECTED_ROWS)
    ledger = read_json(COMBINED_LEDGER)
    real_log_rows = load_real_log_rows()

    blocked_items: list[dict[str, Any]] = []
    for work_item in work_items:
        adapter = adapters.get(work_item.get("source_adapter_ref_hash")) or {}
        join = direct_real_log_join(work_item, real_log_rows)
        blocked_items.append(
            {
                "work_item_id": work_item.get("work_item_id"),
                "source_adapter_ref_hash": work_item.get("source_adapter_ref_hash"),
                "source_stage": work_item.get("source_stage"),
                "source_path_hash": adapter.get("source_path_hash"),
                "adapter_record_type": adapter.get("record_type"),
                "direct_join_audit": join,
                "blocked_reasons": blocked_reasons_for(work_item, adapter, join, selected_rows),
            }
        )

    rows: list[dict[str, Any]] = []
    base_count = int(ledger.get("current_admitted_train_support_tasks") or 0)
    counters = {
        "base_current_admitted_train_support_tasks": base_count,
        "admitted_rows": 0,
        "blocked_rows": len(blocked_items) * len(TASKS),
        "admitted_items": 0,
        "blocked_items": len(blocked_items),
        "total_current_admitted_train_support_tasks": base_count,
        "remaining_gap_to_500": 500 - base_count,
        "language_counts": {},
        "repo_counts": {},
        "task_family_counts": {},
        "duplicate_row_ids": [],
        "generic_target_count": 0,
        "raw_leak_count": 0,
        "risky_claim_counts": {},
    }
    guardrail = guardrail_scan(rows, blocked_items)
    manifest = {
        "stage": STAGE,
        "decision": "blocked_no_direct_real_verifier_log_join_from_stage12407_work_items",
        "claim_boundary": "Blocker stage only. Stage12406 adapter hashes and Stage12407 work items are not real verifier logs and cannot create train-support rows without direct Stage12203/12207/12215 joins.",
        "input_paths": {
            "worklist": str(WORKLIST.relative_to(ROOT)),
            "source_adapters": str(SOURCE_ADAPTERS.relative_to(ROOT)),
            "combined_selected_rows": str(COMBINED_SELECTED_ROWS.relative_to(ROOT)),
            "combined_ledger": str(COMBINED_LEDGER.relative_to(ROOT)),
            "stage12203_level3": str(STAGE12203_LEVEL3.relative_to(ROOT)),
            "stage12203_command_results": str(STAGE12203_COMMANDS.relative_to(ROOT)),
            "stage12207_level3": str(STAGE12207_LEVEL3.relative_to(ROOT)),
            "stage12215_level3": str(STAGE12215_LEVEL3.relative_to(ROOT)),
            "stage12215_observations": str(STAGE12215_OBSERVATIONS.relative_to(ROOT)),
        },
        "work_items_seen": len(work_items),
        "admitted_items": [],
        "blocked_items": blocked_items,
        "stage12322_null_target_semantic_id_rows": stage12322_null_target_count(selected_rows),
        "guardrail_scan_ref": "guardrail_scan.json",
        "output_rows_ref": "selected_test_verifier_log_train_support_rows.jsonl",
        "counters": counters,
    }
    summary = {
        "stage": STAGE,
        "decision": manifest["decision"],
        "counters": counters,
        "admitted_items": [],
        "blocked_items": blocked_items,
        "guardrail_scan_passed": guardrail["scan_passed"],
    }

    write_jsonl(OUT / "selected_test_verifier_log_train_support_rows.jsonl", rows)
    write_json(OUT / "selected_test_verifier_log_materialization_manifest.json", manifest)
    write_json(OUT / "guardrail_scan.json", guardrail)
    write_json(SUMMARY, summary)
    print(json.dumps(counters, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
