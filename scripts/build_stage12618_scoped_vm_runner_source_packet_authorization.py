#!/usr/bin/env python3
"""Build Stage12618 scoped VM runner source-packet authorization.

Stage12617 defined the source-packet requirements but did not authorize
materialization. This stage grants a narrow authorization for a later stage to
materialize reviewed source-packet files only. It does not create source files,
create scratch storage, launch QEMU, execute replay, or admit training.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12618_scoped_vm_runner_source_packet_authorization"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
S12617 = ROOT / "runs/local/artifacts/stage12617_minimal_vm_runner_source_packet_preflight"
S12617_EXTERNAL = ROOT / "runs/summaries/stage12617_minimal_vm_runner_source_packet_preflight.json"
EXPECTED_STAGE12617_SUMMARY = "57867ad7f6c555b57eda21d35ba9a250d14b21ee118ba14e0e4a8c47988a9d8f"
EXPECTED_STAGE12617_CONTRACT = "309e11f6bc3641987c9baa2c3ecf46ae1f758398645f0a5c4cd99ab0852655b9"
EXPECTED_STAGE12617_POINTER = "a93364fb8ec7674857da50bb9f5cabb69b663a512025a41da0c9dd5cd7e35fe8"
EXPECTED_STAGE12617_PRIVATE = "ab6269db234e705fa6a0d376cf829f71fccf40e512ba283e67d6f0c09dd8b42b"
EXPECTED_GATE_SCOPE = "reviewed_stage12602_execute_reviewed_slot_function_only"

FALSE_FIELDS = (
    "implementation_ready", "source_packet_implementation_allowed",
    "source_packet_materialized", "source_packet_executable",
    "stage12595_allowed", "stage12613_allowed", "stage12614_allowed", "stage12615_allowed",
    "stage12616_allowed", "stage12617_allowed",
    "execution_performed", "replay_trustworthy", "raw_replay_evidence_present",
    "trusted_replay_raw_evidence_present", "external_bwrap_execution_evidence_present",
    "alternate_replay_evidence_present", "alternate_replay_trustworthy",
    "vm_runner_implementation_ready", "vm_runner_execution_allowed", "vm_runner_evidence_present",
    "vm_runner_trustworthy", "storage_root_created", "storage_write_performed",
    "host_workspace_mounted_in_guest", "host_volume_mounted_in_guest",
    "guest_network_enabled", "guest_gpu_enabled", "causal_transition_atoms_present",
    "causal_transition_atoms_materialized", "causal_transition_atoms_allowed",
    "causally_committed_pre_outcome_candidate_set_present",
    "observed_stop_continue_decision_provenance_present", "level3_preflight_allowed",
    "level_3_materialized", "level_3_materialization_allowed",
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


class SourcePacketAuthorizationError(RuntimeError):
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
        raise SourcePacketAuthorizationError("json_object_required:" + path.name)
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True).encode("ascii") + b"\n"
    with path.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def no_claim_fields() -> dict[str, Any]:
    return {
        "implementation_ready": False,
        "source_packet_implementation_allowed": False,
        "source_packet_materialized": False,
        "source_packet_executable": False,
        "stage12595_allowed": False,
        "stage12613_allowed": False,
        "stage12614_allowed": False,
        "stage12615_allowed": False,
        "stage12616_allowed": False,
        "stage12617_allowed": False,
        "execution_performed": False,
        "replay_trustworthy": False,
        "raw_replay_evidence_present": False,
        "trusted_replay_raw_evidence_present": False,
        "external_bwrap_execution_evidence_present": False,
        "alternate_replay_evidence_present": False,
        "alternate_replay_trustworthy": False,
        "vm_runner_implementation_ready": False,
        "vm_runner_execution_allowed": False,
        "vm_runner_evidence_present": False,
        "vm_runner_trustworthy": False,
        "storage_root_created": False,
        "storage_write_performed": False,
        "host_workspace_mounted_in_guest": False,
        "host_volume_mounted_in_guest": False,
        "guest_network_enabled": False,
        "guest_gpu_enabled": False,
        "causal_transition_atoms_present": False,
        "causal_transition_atoms_materialized": False,
        "causal_transition_atoms_allowed": False,
        "causally_committed_pre_outcome_candidate_set_present": False,
        "observed_stop_continue_decision_provenance_present": False,
        "level3_preflight_allowed": False,
        "level_3_materialized": False,
        "level_3_materialization_allowed": False,
        "training_admission_preflight_allowed": False,
        "training_admission_allowed": False,
        "training_admitted": False,
        "training_allowed": False,
        "training_run_allowed": False,
        "gpu_allocation_requested": False,
        "cuda2_training_allowed": False,
        "strict_eval_admitted": False,
        "sealed_eval_admitted": False,
        "strict_eval_eligible": False,
        "sealed_eval_eligible": False,
        "admission_allowed": False,
        "ranking_allowed": False,
        "positive_stop": False,
    }


def check_false(record: Mapping[str, Any], label: str) -> None:
    for field in FALSE_FIELDS:
        if field in record and record[field] is not False:
            raise SourcePacketAuthorizationError(f"{label}_gate_drift:{field}")


def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise SourcePacketAuthorizationError(f"{label}_public_leak:{needle}")


def load_stage12617() -> dict[str, Any]:
    summary = read_json(S12617 / "summary.json")
    external = read_json(S12617_EXTERNAL)
    contract = read_json(S12617 / "contract.json")
    pointer = read_json(S12617 / "digest_pointer.json")
    private = read_json(S12617 / "private/minimal_vm_runner_source_packet_preflight.json")
    if summary != external:
        raise SourcePacketAuthorizationError("stage12617_external_summary_mismatch")
    expected = (
        (stable_hash(summary), EXPECTED_STAGE12617_SUMMARY, "summary"),
        (stable_hash(contract), EXPECTED_STAGE12617_CONTRACT, "contract"),
        (stable_hash(pointer), EXPECTED_STAGE12617_POINTER, "pointer"),
        (stable_hash(private), EXPECTED_STAGE12617_PRIVATE, "private"),
    )
    for actual, expected_hash, label in expected:
        if actual != expected_hash:
            raise SourcePacketAuthorizationError("stage12617_pin_drift:" + label)
    if summary.get("decision") != "BLOCKED_MINIMAL_VM_RUNNER_SOURCE_PACKET_AUTHORIZATION_REQUIRED":
        raise SourcePacketAuthorizationError("stage12617_decision_drift")
    required_true = (
        "source_packet_preflight_only",
        "source_packet_requirements_defined",
        "source_packet_recommended_by_stage12616",
        "source_packet_authorization_required",
    )
    for field in required_true:
        if summary.get(field) is not True:
            raise SourcePacketAuthorizationError("stage12617_required_true_drift:" + field)
    if summary.get("source_packet_implementation_allowed") is not False:
        raise SourcePacketAuthorizationError("stage12617_source_packet_authority_drift")
    if summary.get("source_packet_materialized") is not False:
        raise SourcePacketAuthorizationError("stage12617_materialization_drift")
    if summary.get("stage12618_allowed") is not False:
        raise SourcePacketAuthorizationError("stage12617_stage12618_gate_drift")
    if summary.get("vm_runner_execution_allowed") is not False:
        raise SourcePacketAuthorizationError("stage12617_execution_gate_drift")
    if summary.get("training_allowed") is not False:
        raise SourcePacketAuthorizationError("stage12617_training_gate_drift")
    for label, record in (("summary", summary), ("contract", contract), ("pointer", pointer), ("private", private)):
        check_false(record, "stage12617_" + label)
    return {"summary": summary, "contract": contract, "pointer": pointer, "private": private}


def authorization_scope() -> dict[str, Any]:
    return {
        "record_type": "stage12618_scoped_vm_runner_source_packet_authorization_scope_v1",
        "authorized_next_stage": "stage12619_minimal_vm_runner_source_packet_materialization",
        "authorization_grants": [
            "materialize_non_executable_source_packet_files",
            "materialize_static_tests_for_source_packet_files",
            "materialize_public_private_source_packet_manifest",
        ],
        "required_boundaries_for_authorized_materialization": [
            "no_subprocess_invocation",
            "no_qemu_launch_path",
            "no_private_scratch_root_creation",
            "no_vm_image_creation",
            "no_arxiv_write",
            "no_host_workspace_mount_argument",
            "no_private_scratch_root_mount_argument",
            "no_network_gpu_usb_argument",
            "no_replay_execution",
            "no_training_or_eval_admission",
        ],
        "review_required_after_materialization": [
            "independent_source_packet_static_review",
            "public_leak_scan",
            "forbidden_true_gate_scan",
            "targeted_unit_tests",
            "full_stage_regression_chain",
        ],
        "still_forbidden": [
            "creating_private_scratch_root",
            "creating_vm_images",
            "launching_qemu",
            "executing_replay",
            "claiming_replay_trust",
            "materializing_causal_atoms",
            "materializing_level3",
            "admitting_training",
        ],
    }


def build_authorization_packet(stage12617: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    scope = authorization_scope()
    private = {
        "record_type": "stage12618_private_scoped_vm_runner_source_packet_authorization_v1",
        **no_claim_fields(),
        "stage12617_summary_sha256": EXPECTED_STAGE12617_SUMMARY,
        "stage12617_private_source_packet_preflight_sha256": EXPECTED_STAGE12617_PRIVATE,
        "source_decision": stage12617["summary"]["decision"],
        "gate_scope": EXPECTED_GATE_SCOPE,
        "source_packet_authorization_recorded": True,
        "successor_authorization_adjudicates_stage12617_blocked_state": True,
        "stage12618_allowed": True,
        "source_packet_non_executable_materialization_allowed": True,
        "stage12619_allowed": True,
        "authorization_scope": scope,
        "decision": "SCOPED_SOURCE_PACKET_MATERIALIZATION_AUTHORIZED_EXECUTION_STILL_BLOCKED",
    }
    contract = {
        "record_type": "stage12618_public_scoped_vm_runner_source_packet_authorization_v1",
        **no_claim_fields(),
        "stage12617_summary_sha256": EXPECTED_STAGE12617_SUMMARY,
        "stage12617_contract_sha256": EXPECTED_STAGE12617_CONTRACT,
        "stage12617_private_source_packet_preflight_sha256": EXPECTED_STAGE12617_PRIVATE,
        "gate_scope": EXPECTED_GATE_SCOPE,
        "source_packet_authorization_recorded": True,
        "successor_authorization_adjudicates_stage12617_blocked_state": True,
        "stage12618_allowed": True,
        "source_packet_non_executable_materialization_allowed": True,
        "stage12619_allowed": True,
        "authorization_scope_sha256": stable_hash(scope),
        "private_source_packet_authorization_sha256": stable_hash(private),
        "claim_boundary": {
            "source_packet": "non_executable_materialization_authorized_next",
            "storage_write": "not_authorized",
            "vm_launch": "not_authorized",
            "replay": "not_authorized",
            "training": "not_authorized",
        },
    }
    summary = {
        "record_type": "stage12618_public_scoped_vm_runner_source_packet_authorization_summary_v1",
        **no_claim_fields(),
        "stage": STAGE,
        "decision": "SCOPED_SOURCE_PACKET_MATERIALIZATION_AUTHORIZED_EXECUTION_STILL_BLOCKED",
        "stage12617_summary_sha256": EXPECTED_STAGE12617_SUMMARY,
        "gate_scope": EXPECTED_GATE_SCOPE,
        "source_packet_authorization_recorded": True,
        "successor_authorization_adjudicates_stage12617_blocked_state": True,
        "stage12618_allowed": True,
        "source_packet_non_executable_materialization_allowed": True,
        "stage12619_allowed": True,
        "authorization_scope_sha256": stable_hash(scope),
        "private_source_packet_authorization_sha256": stable_hash(private),
        "downstream_blockers": [
            "vm_runner_source_not_materialized_yet",
            "independent_source_packet_static_review_absent",
            "vm_runner_execution_gate_absent",
            "private_scratch_root_not_created",
            "trusted_replay_raw_evidence_absent",
            "causal_transition_atoms_absent",
            "level3_materialization_forbidden",
            "training_admission_forbidden",
        ],
    }
    for label, record in (("summary", summary), ("contract", contract)):
        check_false(record, "stage12618_" + label)
        assert_public_sanitized(record, "stage12618_" + label)
    check_false(private, "stage12618_private")
    return summary, contract, private


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    stage12617 = load_stage12617()
    summary, contract, private = build_authorization_packet(stage12617)
    pointer = {
        "record_type": "stage12618_public_private_scoped_vm_runner_source_packet_authorization_pointer_v1",
        **no_claim_fields(),
        "stage12617_summary_sha256": EXPECTED_STAGE12617_SUMMARY,
        "contract_sha256": stable_hash(contract),
        "private_source_packet_authorization_sha256": stable_hash(private),
        "source_packet_authorization_recorded": True,
        "successor_authorization_adjudicates_stage12617_blocked_state": True,
        "stage12618_allowed": True,
        "source_packet_non_executable_materialization_allowed": True,
        "stage12619_allowed": True,
    }
    check_false(pointer, "stage12618_pointer")
    assert_public_sanitized(pointer, "stage12618_pointer")
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "private/scoped_vm_runner_source_packet_authorization.json", private)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
