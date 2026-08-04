#!/usr/bin/env python3
"""Build Stage12623 dataset gap plan only.

Stage12622 recorded the current dataset admission census after VM work was paused.
This stage turns that census into a bounded admission work plan. It does not
admit rows, run training, allocate GPUs, resume VM/replay, materialize Level-3,
or authorize broad successor work.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12623_dataset_gap_plan_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
S12622 = ROOT / "runs/local/artifacts/stage12622_dataset_admission_census_only"
S12622_SUMMARY = ROOT / "runs/summaries/stage12622_dataset_admission_census_only.json"
EXPECTED_HASHES = {
    "stage12622_summary": "60aba795ee7ccdae5746ed54e443cd8d3df75e12fce5cf56cca812e1157011dd",
    "stage12622_contract": "da1d716b8e7af0f58e1c36ea5b87170649db657286340c11faa77b06c4f1199c",
    "stage12622_pointer": "270b4a5a7873d6f7f810ca7f28921f4dd1de938dc2b7a6b19ddc9b4ddab6755a",
    "stage12622_private": "97ce60cf2d69df36f4106d56888a2c2f972acb73c2dfad60f72a84e18eac83fc",
    "admission_manifest": "8cf5bb10e84db65c3adb9c2434af976938c902347f22a9bd0be74275e7b33646",
}

FALSE_FIELDS = (
    "implementation_ready", "dataset_admission_allowed", "dataset_rows_admitted", "new_rows_admitted",
    "frontier_100m_training_dataset_ready", "source_packet_implementation_allowed", "source_packet_executable",
    "stage12620_allowed", "stage12621_allowed", "stage12622_allowed", "stage12623_allowed", "stage12624_allowed",
    "vm_branch_active", "vm_runner_implementation_allowed", "vm_runner_implementation_ready",
    "vm_runner_execution_allowed", "vm_runner_evidence_present", "vm_runner_trustworthy",
    "storage_root_created", "storage_write_performed", "execution_performed", "replay_trustworthy",
    "raw_replay_evidence_present", "trusted_replay_raw_evidence_present", "causal_transition_atoms_present",
    "causal_transition_atoms_allowed", "level3_preflight_allowed", "level_3_materialized",
    "level_3_materialization_allowed", "training_admission_preflight_allowed", "training_admission_allowed",
    "training_admitted", "training_allowed", "training_run_allowed", "gpu_allocation_requested",
    "cuda2_training_allowed", "strict_eval_admitted", "sealed_eval_admitted", "strict_eval_eligible",
    "sealed_eval_eligible", "admission_allowed", "ranking_allowed", "positive_stop",
)
PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "agentkernel_vm_replay", "/dev/", "selector", "raw_stream",
    "stdout.raw", "stderr.raw", "before_commit_oid", "after_commit_oid", "production_path",
    "production_patch_sha256", "manual_executor_slot_contracts", "slot_1.patch",
    "slot_2.patch", "repository_root", "patch_path", "slot_1/", "slot_2/",
)


class DatasetGapPlanError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def stable_hash(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise DatasetGapPlanError("json_object_required:" + path.name)
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True).encode("ascii") + b"\n"
    with path.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def no_claim_fields() -> dict[str, Any]:
    return {field: False for field in FALSE_FIELDS}


def check_false(record: Mapping[str, Any], label: str) -> None:
    for field in FALSE_FIELDS:
        if field in record and record[field] is not False:
            raise DatasetGapPlanError(f"{label}_gate_drift:{field}")


def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise DatasetGapPlanError(f"{label}_public_leak:{needle}")


def load_stage12622() -> dict[str, Any]:
    summary = read_json(S12622 / "summary.json")
    external = read_json(S12622_SUMMARY)
    contract = read_json(S12622 / "contract.json")
    pointer = read_json(S12622 / "digest_pointer.json")
    private = read_json(S12622 / "private/dataset_admission_census_only.json")
    if summary != external:
        raise DatasetGapPlanError("stage12622_external_summary_mismatch")
    for label, value in (
        ("stage12622_summary", summary),
        ("stage12622_contract", contract),
        ("stage12622_pointer", pointer),
        ("stage12622_private", private),
    ):
        if stable_hash(value) != EXPECTED_HASHES[label]:
            raise DatasetGapPlanError("stage12622_pin_drift:" + label)
    if summary.get("decision") != "DATASET_ADMISSION_CENSUS_RECORDED_SCALE_GAP_REMAINS_BLOCKING":
        raise DatasetGapPlanError("stage12622_decision_drift")
    if summary.get("stage12623_dataset_gap_plan_only_allowed") is not True:
        raise DatasetGapPlanError("stage12622_gap_plan_only_missing")
    if summary.get("stage12623_allowed") is not False:
        raise DatasetGapPlanError("stage12622_broad_successor_gate_drift")
    if summary.get("training_allowed") is not False:
        raise DatasetGapPlanError("stage12622_training_gate_drift")
    return {"summary": summary, "contract": contract, "pointer": pointer, "private": private}


def build_gap_plan(census_summary: Mapping[str, Any]) -> dict[str, Any]:
    if census_summary.get("control_board_countable_supply_tasks") != 190:
        raise DatasetGapPlanError("control_board_count_drift")
    if census_summary.get("authoritative_ledger_admitted_train_support_tasks") != 158:
        raise DatasetGapPlanError("authoritative_ledger_count_drift")
    if census_summary.get("control_board_remaining_gap_to_500") != 310:
        raise DatasetGapPlanError("control_board_gap_drift")
    if census_summary.get("authoritative_ledger_remaining_gap_to_500") != 342:
        raise DatasetGapPlanError("authoritative_ledger_gap_drift")
    if census_summary.get("dataset_admission_manifest_catalog_patch_candidate_count") != 30:
        raise DatasetGapPlanError("catalog_candidate_count_drift")
    if census_summary.get("derived_countable_as_new_train_support_rows") != 0:
        raise DatasetGapPlanError("derived_rows_countable_drift")
    candidate_worklist = [
        {
            "candidate_source": "stage12419_count_source_delta",
            "candidate_kind": "count_reconciliation",
            "projected_unique_task_count": 32,
            "dedupe_keys": ["root_id", "task_family", "source_stage", "source_record_id"],
            "exclusion_rules": ["exclude_derived_projection_rows", "exclude_rows_already_in_stage12376"],
            "required_admission_evidence": ["stage12376_ledger_update", "duplicate_family_check", "source_quality_review"],
            "admission_status": "not_admitted",
            "control_board_reconciliation": "already_in_190_control_board_supply_not_yet_authoritative_ledger_admitted",
        },
        {
            "candidate_source": "long_context_dataset_admission_manifest_catalog_patch_candidates",
            "candidate_kind": "catalog_patch_candidate_triage",
            "projected_unique_task_count": 30,
            "dedupe_keys": ["dataset_name", "source_id_equals", "provenance_tier", "role_override"],
            "exclusion_rules": ["exclude_eval_only", "exclude_retrieval_aux_only", "exclude_reject_routes"],
            "required_admission_evidence": ["source_backed_task_projection", "quality_tier_review", "train_support_policy_review"],
            "admission_status": "not_admitted",
            "control_board_reconciliation": "candidate_new_to_authoritative_ledger_after_review_only",
        },
        {
            "candidate_source": "long_context_dataset_admission_manifest_paper_support_only",
            "candidate_kind": "algorithm_grounding_task_plan",
            "projected_unique_task_count": 22,
            "dedupe_keys": ["dataset_name", "paper_or_source_id", "task_projection_family"],
            "exclusion_rules": ["exclude_repair_claims", "exclude_level3_claims", "exclude_unreviewed_generic_rows"],
            "required_admission_evidence": ["grounded_objective_review", "non_repair_train_support_policy_review"],
            "admission_status": "not_admitted",
            "control_board_reconciliation": "candidate_new_to_authoritative_ledger_after_review_only",
        },
    ]
    planning_waves = [
        {
            "wave": "A_reconcile_count_sources",
            "objective": "reconcile_stage12376_158_vs_stage12419_190_without_counting_derived_projection_rows",
            "target_delta_tasks": 32,
            "admission_action": "none_plan_only",
            "successor_review_required": "source_count_reconciliation_review",
        },
        {
            "wave": "B_strict_trace_import_adapter",
            "objective": "convert_the_one_STRICT_TRACE_EPISODE_IMPORT_route_into_reviewable_train_support_candidates",
            "candidate_dataset_routes": {"STRICT_TRACE_EPISODE_IMPORT": 1, "TRACE_SUPPORT_ONLY": 1},
            "admission_action": "adapter_plan_only",
            "successor_review_required": "strict_adapter_materialization_preflight",
        },
        {
            "wave": "C_catalog_patch_candidate_triage",
            "objective": "triage_30_catalog_patch_candidates_for_source_backed_train_support_eligibility",
            "candidate_count": 30,
            "admission_action": "triage_plan_only",
            "successor_review_required": "per_candidate_source_and_quality_review",
        },
        {
            "wave": "D_paper_support_to_grounded_tasks",
            "objective": "turn_22_paper_support_only_routes_into_algorithm_grounding_tasks_without_repair_or_Level3_claims",
            "candidate_dataset_routes": {"PAPER_SUPPORT_ONLY": 22},
            "admission_action": "projection_plan_only",
            "successor_review_required": "non_repair_train_support_policy_review",
        },
        {
            "wave": "E_retrieval_aux_preserve_as_auxiliary",
            "objective": "keep_3_retrieval_aux_only_routes_out_of_countable_train_support_until_a_new_policy_allows_it",
            "candidate_dataset_routes": {"RETRIEVAL_AUX_ONLY": 3},
            "admission_action": "no_counting_plan_only",
            "successor_review_required": "retrieval_aux_policy_review_if_needed",
        },
    ]
    return {
        "record_type": "stage12623_dataset_gap_plan_v1",
        "planning_baseline": "stage12376_authoritative_ledger_158",
        "authoritative_ledger_baseline_preserved": "stage12376_158_admitted_train_support_tasks",
        "authoritative_training_gap_to_500": 342,
        "authoritative_ledger_gap_to_500": 342,
        "control_board_advisory_countable_supply_tasks": 190,
        "control_board_advisory_gap_to_500": 310,
        "count_source_delta_to_reconcile": 32,
        "current_compiled_trainer_rows": census_summary["full_context_trainer_rows"],
        "current_split_train_rows": census_summary["split_train_rows"],
        "current_split_eval_rows": census_summary["split_eval_rows"],
        "current_split_strict_eval_rows": census_summary["split_strict_eval_rows"],
        "catalog_patch_candidate_count": 30,
        "dataset_route_counts": {
            "PAPER_SUPPORT_ONLY": 22,
            "STRICT_TRACE_EPISODE_IMPORT": 1,
            "TRACE_SUPPORT_ONLY": 1,
            "EVAL_ONLY": 3,
            "RETRIEVAL_AUX_ONLY": 3,
            "REJECT_GENERIC": 10,
            "REJECT_UNKNOWN": 12,
        },
        "derived_sanitized_projection_rows": census_summary["derived_sanitized_projection_rows"],
        "derived_countable_as_new_train_support_rows": 0,
        "candidate_worklist": candidate_worklist,
        "planning_waves": planning_waves,
        "minimum_next_gate": "stage12624_count_source_reconciliation_preflight_only",
        "plan_only": True,
        "new_admission_performed": False,
        "training_allowed_after_plan": False,
    }


def build_gap_plan_packet(stage12622: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    plan = build_gap_plan(stage12622["summary"])
    private = {
        "record_type": "stage12623_private_dataset_gap_plan_only_v1",
        **no_claim_fields(),
        "source_hashes": EXPECTED_HASHES,
        "dataset_gap_plan_only": True,
        "vm_branch_remains_paused": True,
        "stage12624_count_source_reconciliation_preflight_only_allowed": True,
        "gap_plan": plan,
        "decision": "DATASET_GAP_PLAN_RECORDED_NO_ADMISSION_OR_TRAINING",
    }
    contract = {
        "record_type": "stage12623_public_dataset_gap_plan_only_v1",
        **no_claim_fields(),
        "stage12622_summary_sha256": EXPECTED_HASHES["stage12622_summary"],
        "stage12622_contract_sha256": EXPECTED_HASHES["stage12622_contract"],
        "stage12622_private_census_sha256": EXPECTED_HASHES["stage12622_private"],
        "dataset_gap_plan_sha256": stable_hash(plan),
        "private_dataset_gap_plan_sha256": stable_hash(private),
        "dataset_gap_plan_only": True,
        "vm_branch_remains_paused": True,
        "stage12624_count_source_reconciliation_preflight_only_allowed": True,
        "claim_boundary": {
            "plan": "dataset_gap_plan_only",
            "new_admission": "not_authorized",
            "training": "not_authorized",
            "vm": "paused_not_used_for_gap_plan",
            "replay": "not_executed",
            "level3": "not_materialized",
        },
    }
    summary = {
        "record_type": "stage12623_public_dataset_gap_plan_only_summary_v1",
        **no_claim_fields(),
        "stage": STAGE,
        "decision": "DATASET_GAP_PLAN_RECORDED_NO_ADMISSION_OR_TRAINING",
        "stage12622_summary_sha256": EXPECTED_HASHES["stage12622_summary"],
        "dataset_gap_plan_sha256": stable_hash(plan),
        "private_dataset_gap_plan_sha256": stable_hash(private),
        "dataset_gap_plan_only": True,
        "vm_branch_remains_paused": True,
        "stage12624_count_source_reconciliation_preflight_only_allowed": True,
        "authoritative_planning_baseline_tasks": 158,
        "control_board_advisory_countable_supply_tasks": 190,
        "authoritative_ledger_admitted_train_support_tasks": 158,
        "count_source_delta_to_reconcile": 32,
        "authoritative_training_gap_to_500": 342,
        "control_board_advisory_gap_to_500": 310,
        "authoritative_ledger_gap_to_500": 342,
        "current_compiled_trainer_rows": 11,
        "current_split_train_rows": 589,
        "catalog_patch_candidate_count": 30,
        "paper_support_only_route_count": 22,
        "strict_trace_episode_import_route_count": 1,
        "trace_support_only_route_count": 1,
        "retrieval_aux_only_route_count": 3,
        "derived_sanitized_projection_rows": 292,
        "derived_countable_as_new_train_support_rows": 0,
        "planned_wave_count": len(plan["planning_waves"]),
        "frontier_100m_training_dataset_ready": False,
        "downstream_blockers": [
            "count_source_delta_32_not_reconciled",
            "admission_wave_reviews_not_materialized",
            "new_train_support_rows_not_admitted",
            "compiled_trainer_rows_only_11",
            "frontier_training_admission_absent",
            "training_admission_forbidden",
        ],
    }
    for label, record in (("summary", summary), ("contract", contract)):
        check_false(record, "stage12623_" + label)
        assert_public_sanitized(record, "stage12623_" + label)
    check_false(private, "stage12623_private")
    return summary, contract, private


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    stage12622 = load_stage12622()
    summary, contract, private = build_gap_plan_packet(stage12622)
    pointer = {
        "record_type": "stage12623_public_private_dataset_gap_plan_only_pointer_v1",
        **no_claim_fields(),
        "stage12622_summary_sha256": EXPECTED_HASHES["stage12622_summary"],
        "contract_sha256": stable_hash(contract),
        "private_dataset_gap_plan_sha256": stable_hash(private),
        "dataset_gap_plan_only": True,
        "vm_branch_remains_paused": True,
        "stage12624_count_source_reconciliation_preflight_only_allowed": True,
    }
    check_false(pointer, "stage12623_pointer")
    assert_public_sanitized(pointer, "stage12623_pointer")
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "private/dataset_gap_plan_only.json", private)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
