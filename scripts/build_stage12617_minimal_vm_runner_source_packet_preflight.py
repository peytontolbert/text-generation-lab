#!/usr/bin/env python3
"""Build Stage12617 minimal VM runner source-packet preflight.

Stage12616 recommends a future source packet after contract review, but keeps
source implementation blocked. This stage defines the minimal source-packet
requirements without creating runner source, creating scratch storage, launching
VMs, executing replay, or admitting training.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12617_minimal_vm_runner_source_packet_preflight"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
S12616 = ROOT / "runs/local/artifacts/stage12616_independent_vm_storage_contract_review"
S12616_EXTERNAL = ROOT / "runs/summaries/stage12616_independent_vm_storage_contract_review.json"
EXPECTED_STAGE12616_SUMMARY = "2ba9dd2c01e9547d355c8a8212e90670c559d47beb8f3c3f7218f6a52db3b3f6"
EXPECTED_STAGE12616_CONTRACT = "b396670f36fa79b2dc1c6c1acec40423a0fd831e93171e83cdbed2a01023ad16"
EXPECTED_STAGE12616_POINTER = "4c0e7ff45b88692cdabeea3e74cc1930aadc93655b6407890d903a981574a6ab"
EXPECTED_STAGE12616_PRIVATE = "dfd175d90ff617cac18368cc48f20ff705a83397ce00ada818ff28abe859dea0"
EXPECTED_GATE_SCOPE = "reviewed_stage12602_execute_reviewed_slot_function_only"

FALSE_FIELDS = (
    "implementation_ready", "source_packet_implementation_allowed", "source_packet_materialized",
    "source_packet_executable", "stage12595_allowed", "stage12613_allowed", "stage12614_allowed",
    "stage12615_allowed", "stage12616_allowed", "stage12617_allowed", "stage12618_allowed",
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


class SourcePacketPreflightError(RuntimeError):
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
        raise SourcePacketPreflightError("json_object_required:" + path.name)
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
        "stage12618_allowed": False,
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
            raise SourcePacketPreflightError(f"{label}_gate_drift:{field}")


def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise SourcePacketPreflightError(f"{label}_public_leak:{needle}")


def load_stage12616() -> dict[str, Any]:
    summary = read_json(S12616 / "summary.json")
    external = read_json(S12616_EXTERNAL)
    contract = read_json(S12616 / "contract.json")
    pointer = read_json(S12616 / "digest_pointer.json")
    private = read_json(S12616 / "private/independent_vm_storage_contract_review.json")
    if summary != external:
        raise SourcePacketPreflightError("stage12616_external_summary_mismatch")
    expected = (
        (stable_hash(summary), EXPECTED_STAGE12616_SUMMARY, "summary"),
        (stable_hash(contract), EXPECTED_STAGE12616_CONTRACT, "contract"),
        (stable_hash(pointer), EXPECTED_STAGE12616_POINTER, "pointer"),
        (stable_hash(private), EXPECTED_STAGE12616_PRIVATE, "private"),
    )
    for actual, expected_hash, label in expected:
        if actual != expected_hash:
            raise SourcePacketPreflightError("stage12616_pin_drift:" + label)
    if summary.get("decision") != "INDEPENDENT_VM_STORAGE_CONTRACT_REVIEW_PASSED_SOURCE_PACKET_STILL_BLOCKED":
        raise SourcePacketPreflightError("stage12616_decision_drift")
    required_true = (
        "independent_contract_review_passed",
        "vm_runner_contract_review_passed",
        "storage_containment_review_passed",
        "source_packet_recommended",
    )
    for field in required_true:
        if summary.get(field) is not True:
            raise SourcePacketPreflightError("stage12616_required_true_drift:" + field)
    if summary.get("source_packet_implementation_allowed") is not False:
        raise SourcePacketPreflightError("stage12616_source_packet_authority_drift")
    if summary.get("stage12617_allowed") is not False:
        raise SourcePacketPreflightError("stage12616_stage12617_gate_drift")
    if summary.get("vm_runner_execution_allowed") is not False:
        raise SourcePacketPreflightError("stage12616_execution_gate_drift")
    if summary.get("training_allowed") is not False:
        raise SourcePacketPreflightError("stage12616_training_gate_drift")
    for label, record in (("summary", summary), ("contract", contract), ("pointer", pointer), ("private", private)):
        check_false(record, "stage12616_" + label)
    return {"summary": summary, "contract": contract, "pointer": pointer, "private": private}


def source_packet_requirements() -> dict[str, Any]:
    return {
        "record_type": "stage12617_minimal_vm_runner_source_packet_requirements_v1",
        "packet_scope": EXPECTED_GATE_SCOPE,
        "implementation_authority": "none_in_this_stage",
        "minimum_future_modules": [
            "contract_manifest_loader",
            "private_scratch_dirfd_allocator",
            "qcow2_overlay_planner",
            "qemu_command_renderer",
            "guest_command_manifest_renderer",
            "phase_evidence_collector",
            "public_private_artifact_splitter",
            "public_leak_scanner",
            "exit_status_consistency_checker",
            "tree_digest_revert_checker",
        ],
        "hard_source_packet_requirements": [
            "no_subprocess_execution_in_source_packet_build_stage",
            "no_qemu_launch_path_until_explicit_execution_gate",
            "no_storage_root_creation_until_explicit_storage_gate",
            "no_network_device_argument_generation",
            "no_gpu_or_usb_passthrough_argument_generation",
            "no_virtiofs_9p_or_host_shared_folder_argument_generation",
            "no_host_workspace_mount_argument_generation",
            "no_private_scratch_root_mount_argument_generation",
            "only_qcow2_overlay_paths_under_private_scratch_root_label",
            "fixed_initial_patched_final_phase_sequence_only",
            "bounded_raw_stream_capture_policy_only",
            "public_outputs_hash_private_evidence_without_path_leakage",
        ],
        "required_static_review_checks_before_implementation_can_be_called_ready": [
            "ast_or_token_scan_finds_no_subprocess_invocation",
            "command_renderer_unit_tests_reject_host_mounts_network_gpu_usb",
            "path_allocator_tests_reject_absolute_escape_symlink_and_shared_device_drift",
            "artifact_splitter_tests_reject_private_path_and_raw_stream_public_leaks",
            "manifest_loader_tests_pin_stage12614_stage12615_stage12616_hashes",
            "no_training_or_eval_admission_fields_can_be_true",
        ],
        "still_forbidden": [
            "writing_runner_source_files_as_authorized_implementation",
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


def build_source_packet_preflight(stage12616: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    requirements = source_packet_requirements()
    private = {
        "record_type": "stage12617_private_minimal_vm_runner_source_packet_preflight_v1",
        "stage12616_summary_sha256": EXPECTED_STAGE12616_SUMMARY,
        "stage12616_private_contract_review_sha256": EXPECTED_STAGE12616_PRIVATE,
        "source_decision": stage12616["summary"]["decision"],
        "gate_scope": EXPECTED_GATE_SCOPE,
        "source_packet_preflight_only": True,
        "source_packet_requirements_defined": True,
        "source_packet_recommended_by_stage12616": True,
        "source_packet_authorization_required": True,
        "source_packet_requirements": requirements,
        "decision": "BLOCKED_MINIMAL_VM_RUNNER_SOURCE_PACKET_AUTHORIZATION_REQUIRED",
        **no_claim_fields(),
    }
    contract = {
        "record_type": "stage12617_public_minimal_vm_runner_source_packet_preflight_v1",
        "stage12616_summary_sha256": EXPECTED_STAGE12616_SUMMARY,
        "stage12616_contract_sha256": EXPECTED_STAGE12616_CONTRACT,
        "stage12616_private_contract_review_sha256": EXPECTED_STAGE12616_PRIVATE,
        "gate_scope": EXPECTED_GATE_SCOPE,
        "source_packet_preflight_only": True,
        "source_packet_requirements_defined": True,
        "source_packet_recommended_by_stage12616": True,
        "source_packet_authorization_required": True,
        "source_packet_requirements_sha256": stable_hash(requirements),
        "private_source_packet_preflight_sha256": stable_hash(private),
        "claim_boundary": {
            "source_packet": "requirements_defined_not_implemented",
            "implementation": "not_authorized",
            "vm_launch": "not_authorized",
            "replay": "not_authorized",
            "training": "not_authorized",
        },
        **no_claim_fields(),
    }
    summary = {
        "record_type": "stage12617_public_minimal_vm_runner_source_packet_preflight_summary_v1",
        "stage": STAGE,
        "decision": "BLOCKED_MINIMAL_VM_RUNNER_SOURCE_PACKET_AUTHORIZATION_REQUIRED",
        "stage12616_summary_sha256": EXPECTED_STAGE12616_SUMMARY,
        "gate_scope": EXPECTED_GATE_SCOPE,
        "source_packet_preflight_only": True,
        "source_packet_requirements_defined": True,
        "source_packet_recommended_by_stage12616": True,
        "source_packet_authorization_required": True,
        "source_packet_requirements_sha256": stable_hash(requirements),
        "private_source_packet_preflight_sha256": stable_hash(private),
        "downstream_blockers": [
            "source_packet_implementation_not_authorized",
            "vm_runner_source_absent",
            "vm_runner_implementation_absent",
            "vm_runner_execution_gate_absent",
            "private_scratch_root_not_created",
            "trusted_replay_raw_evidence_absent",
            "causal_transition_atoms_absent",
            "level3_materialization_forbidden",
            "training_admission_forbidden",
        ],
        **no_claim_fields(),
    }
    for label, record in (("summary", summary), ("contract", contract)):
        check_false(record, "stage12617_" + label)
        assert_public_sanitized(record, "stage12617_" + label)
    check_false(private, "stage12617_private")
    return summary, contract, private


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    stage12616 = load_stage12616()
    summary, contract, private = build_source_packet_preflight(stage12616)
    pointer = {
        "record_type": "stage12617_public_private_minimal_vm_runner_source_packet_preflight_pointer_v1",
        "stage12616_summary_sha256": EXPECTED_STAGE12616_SUMMARY,
        "contract_sha256": stable_hash(contract),
        "private_source_packet_preflight_sha256": stable_hash(private),
        "source_packet_preflight_only": True,
        "source_packet_requirements_defined": True,
        "source_packet_recommended_by_stage12616": True,
        "source_packet_authorization_required": True,
        **no_claim_fields(),
    }
    check_false(pointer, "stage12617_pointer")
    assert_public_sanitized(pointer, "stage12617_pointer")
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "private/minimal_vm_runner_source_packet_preflight.json", private)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
