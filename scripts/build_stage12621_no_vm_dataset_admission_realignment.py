#!/usr/bin/env python3
"""Build Stage12621 no-VM dataset admission realignment.

The VM/microVM runner branch is useful for the trusted causal replay branch, but
it is not a global prerequisite for every possible training dry run. This stage
pauses VM implementation work and re-centers the frontier 100M maintainer path
on admitted dataset scale and quality. It does not admit training, execute VM
work, create storage, run replay, touch GPUs, or launch training.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12621_no_vm_dataset_admission_realignment"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
S12620_SUMMARY = ROOT / "runs/summaries/stage12620_independent_source_packet_static_review.json"
S12376_SUMMARY = ROOT / "runs/summaries/stage12376_combined_train_support_ledger_v11.json"
S12419_SUMMARY = ROOT / "runs/summaries/stage12419_current_dataset_control_board_v17.json"
STRICT_CARD = ROOT / "runs/local/artifacts/strict_long_context_train_ready_plus_audit_v1/strict_long_context_training_dataset_card.json"
BUNDLE_CARD = ROOT / "runs/local/artifacts/strict_software_maintainer_training_bundle_plus_audit_v1/strict_software_maintainer_training_bundle_card.json"
EXPECTED_HASHES = {
    "stage12620_summary": "aa16a056540005b91bb51f54f3dfdbf7a0a764c3a0fc6522d59a771fda0a753a",
    "stage12376_summary": "a7aa3bcae28c5741f1955d2b954744143266bb61d2e824d78343e932cc3b695e",
    "stage12419_summary": "61b8a0541c06cec23ac06d75e5da9679c073d7615b97ee2257748049e4d5d954",
    "strict_long_context_card": "4651e42fb28e7d1c1461bd1010c6b121a9391d8f296ce7c9bbf931b1f6f6f639",
    "strict_software_bundle_card": "3d8a514a2f0cfd68bde9afe3af239be97dd9b3063e39460acc5615eb31803700",
}

FALSE_FIELDS = (
    "implementation_ready", "source_packet_implementation_allowed", "source_packet_executable",
    "stage12620_allowed", "stage12621_allowed", "stage12622_allowed", "vm_branch_active",
    "vm_runner_implementation_allowed", "vm_runner_implementation_ready", "vm_runner_execution_allowed",
    "vm_runner_evidence_present", "vm_runner_trustworthy", "storage_root_created", "storage_write_performed",
    "execution_performed", "replay_trustworthy", "raw_replay_evidence_present",
    "trusted_replay_raw_evidence_present", "causal_transition_atoms_present", "causal_transition_atoms_allowed",
    "level3_preflight_allowed", "level_3_materialized", "level_3_materialization_allowed",
    "training_admission_preflight_allowed", "training_admission_allowed", "training_admitted",
    "training_allowed", "training_run_allowed", "gpu_allocation_requested", "cuda2_training_allowed",
    "strict_eval_admitted", "sealed_eval_admitted", "strict_eval_eligible", "sealed_eval_eligible",
    "admission_allowed", "ranking_allowed", "positive_stop",
)
PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "agentkernel_vm_replay", "/dev/", "selector", "raw_stream",
    "stdout.raw", "stderr.raw", "before_commit_oid", "after_commit_oid", "production_path",
    "production_patch_sha256", "manual_executor_slot_contracts", "slot_1.patch",
    "slot_2.patch", "repository_root", "patch_path", "slot_1/", "slot_2/",
)


class DatasetRealignmentError(RuntimeError):
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
        raise DatasetRealignmentError("json_object_required:" + path.name)
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
            raise DatasetRealignmentError(f"{label}_gate_drift:{field}")


def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise DatasetRealignmentError(f"{label}_public_leak:{needle}")


def load_pinned_inputs() -> dict[str, dict[str, Any]]:
    inputs = {
        "stage12620_summary": read_json(S12620_SUMMARY),
        "stage12376_summary": read_json(S12376_SUMMARY),
        "stage12419_summary": read_json(S12419_SUMMARY),
        "strict_long_context_card": read_json(STRICT_CARD),
        "strict_software_bundle_card": read_json(BUNDLE_CARD),
    }
    for label, value in inputs.items():
        actual = stable_hash(value)
        if actual != EXPECTED_HASHES[label]:
            raise DatasetRealignmentError(f"input_pin_drift:{label}")
    if inputs["stage12376_summary"].get("training_allowed") is not False:
        raise DatasetRealignmentError("stage12376_training_gate_drift")
    if inputs["stage12419_summary"].get("training_allowed") is not False:
        raise DatasetRealignmentError("stage12419_training_gate_drift")
    if inputs["stage12620_summary"].get("stage12620_static_review_only_allowed") is not True:
        raise DatasetRealignmentError("stage12620_static_review_marker_missing")
    if inputs["stage12620_summary"].get("training_allowed") is not False:
        raise DatasetRealignmentError("stage12620_training_gate_drift")
    return inputs


def extract_dataset_state(inputs: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    strict_compile = inputs["strict_long_context_card"].get("compile_summary", {})
    bundle_compile = inputs["strict_software_bundle_card"].get("long_context_summary", {}).get("compile_summary", {})
    if strict_compile.get("full_context_rows") != 11:
        raise DatasetRealignmentError("strict_full_context_row_drift")
    if strict_compile.get("retrieval_rows") != 729:
        raise DatasetRealignmentError("strict_retrieval_row_drift")
    if bundle_compile.get("full_context_rows") != 11:
        raise DatasetRealignmentError("bundle_full_context_row_drift")
    ledger = inputs["stage12376_summary"]
    if ledger.get("current_admitted_train_support_tasks") != 158:
        raise DatasetRealignmentError("stage12376_admitted_count_drift")
    if ledger.get("remaining_gap_to_500") != 342:
        raise DatasetRealignmentError("stage12376_gap_drift")
    control_decision = inputs["stage12419_summary"].get("decision", "")
    if "countable_supply_190" not in control_decision:
        raise DatasetRealignmentError("stage12419_supply_decision_drift")
    return {
        "record_type": "stage12621_dataset_scale_state_v1",
        "authoritative_ledger_admitted_train_support_tasks": 158,
        "authoritative_ledger_target_train_support_tasks": 500,
        "authoritative_ledger_remaining_gap_to_500": 342,
        "control_board_countable_supply_tasks": 190,
        "strict_plus_audit_full_context_trainer_rows": 11,
        "strict_plus_audit_memory_rows": strict_compile.get("memory_rows"),
        "strict_plus_audit_retrieval_rows": 729,
        "strict_plus_audit_accepted_pack_count": strict_compile.get("train_ready_audit_summary", {}).get("accepted_pack_count"),
        "strict_plus_audit_included_shard_count": strict_compile.get("train_ready_audit_summary", {}).get("included_shard_count"),
        "global_training_allowed_by_authoritative_ledgers": False,
        "small_dry_run_possible_from_existing_bundle": True,
        "frontier_100m_training_dataset_ready": False,
    }


def build_realignment_packet(inputs: Mapping[str, Mapping[str, Any]]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    dataset_state = extract_dataset_state(inputs)
    realignment = {
        "record_type": "stage12621_no_vm_dataset_admission_realignment_record_v1",
        "vm_microvm_requirement_scope": "trusted_causal_replay_branch_only",
        "vm_branch_status": "paused_until_replay_execution_evidence_is_again_the_active_blocker",
        "frontier_100m_critical_path": "admitted_dataset_scale_and_admission_quality",
        "existing_bundle_use": "dry_run_or_ablation_only_not_frontier_training_claim",
        "next_safe_work": "dataset_admission_census_and_scale_gap_plan_only",
        "explicit_non_goals": [
            "no_vm_runner_implementation",
            "no_qemu_launch",
            "no_private_scratch_root_creation",
            "no_replay_execution",
            "no_causal_atom_materialization",
            "no_level3_materialization",
            "no_training_run",
            "no_gpu_allocation",
        ],
    }
    private = {
        "record_type": "stage12621_private_no_vm_dataset_admission_realignment_v1",
        **no_claim_fields(),
        "source_hashes": EXPECTED_HASHES,
        "dataset_scale_state": dataset_state,
        "realignment": realignment,
        "vm_branch_paused": True,
        "dataset_scale_quality_critical_path": True,
        "stage12622_dataset_admission_census_only_allowed": True,
        "decision": "VM_BRANCH_PAUSED_DATASET_ADMISSION_SCALE_AND_QUALITY_CRITICAL_PATH",
    }
    contract = {
        "record_type": "stage12621_public_no_vm_dataset_admission_realignment_v1",
        **no_claim_fields(),
        "stage12620_summary_sha256": EXPECTED_HASHES["stage12620_summary"],
        "stage12376_summary_sha256": EXPECTED_HASHES["stage12376_summary"],
        "stage12419_summary_sha256": EXPECTED_HASHES["stage12419_summary"],
        "dataset_scale_state_sha256": stable_hash(dataset_state),
        "realignment_sha256": stable_hash(realignment),
        "private_no_vm_dataset_realignment_sha256": stable_hash(private),
        "vm_branch_paused": True,
        "dataset_scale_quality_critical_path": True,
        "stage12622_dataset_admission_census_only_allowed": True,
        "claim_boundary": {
            "vm": "paused_not_required_for_dataset_census_or_dry_run",
            "existing_training_bundle": "dry_run_or_ablation_only",
            "frontier_training": "not_authorized_dataset_scale_quality_blocked",
            "replay_branch": "paused_not_reverted",
        },
    }
    summary = {
        "record_type": "stage12621_public_no_vm_dataset_admission_realignment_summary_v1",
        **no_claim_fields(),
        "stage": STAGE,
        "decision": "VM_BRANCH_PAUSED_DATASET_ADMISSION_SCALE_AND_QUALITY_CRITICAL_PATH",
        "stage12620_summary_sha256": EXPECTED_HASHES["stage12620_summary"],
        "stage12376_summary_sha256": EXPECTED_HASHES["stage12376_summary"],
        "stage12419_summary_sha256": EXPECTED_HASHES["stage12419_summary"],
        "dataset_scale_state_sha256": stable_hash(dataset_state),
        "realignment_sha256": stable_hash(realignment),
        "private_no_vm_dataset_realignment_sha256": stable_hash(private),
        "vm_branch_paused": True,
        "dataset_scale_quality_critical_path": True,
        "stage12622_dataset_admission_census_only_allowed": True,
        "authoritative_ledger_admitted_train_support_tasks": 158,
        "authoritative_ledger_remaining_gap_to_500": 342,
        "control_board_countable_supply_tasks": 190,
        "strict_plus_audit_full_context_trainer_rows": 11,
        "strict_plus_audit_retrieval_rows": 729,
        "frontier_100m_training_dataset_ready": False,
        "downstream_blockers": [
            "admitted_train_support_scale_below_500_target",
            "frontier_training_admission_absent",
            "dataset_quality_census_not_current",
            "trusted_replay_branch_paused_without_replay_evidence",
            "causal_transition_atoms_absent",
            "level3_materialization_forbidden",
            "training_admission_forbidden",
        ],
    }
    for label, record in (("summary", summary), ("contract", contract)):
        check_false(record, "stage12621_" + label)
        assert_public_sanitized(record, "stage12621_" + label)
    check_false(private, "stage12621_private")
    return summary, contract, private


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    inputs = load_pinned_inputs()
    summary, contract, private = build_realignment_packet(inputs)
    pointer = {
        "record_type": "stage12621_public_private_no_vm_dataset_admission_realignment_pointer_v1",
        **no_claim_fields(),
        "stage12620_summary_sha256": EXPECTED_HASHES["stage12620_summary"],
        "contract_sha256": stable_hash(contract),
        "private_no_vm_dataset_realignment_sha256": stable_hash(private),
        "vm_branch_paused": True,
        "dataset_scale_quality_critical_path": True,
        "stage12622_dataset_admission_census_only_allowed": True,
    }
    check_false(pointer, "stage12621_pointer")
    assert_public_sanitized(pointer, "stage12621_pointer")
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "private/no_vm_dataset_admission_realignment.json", private)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
