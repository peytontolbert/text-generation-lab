#!/usr/bin/env python3
"""Build Stage12614 disposable VM runner contract preflight.

Stage12613 identified a stronger isolation target but did not authorize
implementation. This stage defines the disposable VM evidence contract and keeps
it blocked until independent contract review and a later implementation stage.
No replay execution, causal atoms, Level-3 materialization, or training
admission is authorized here.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12614_disposable_vm_runner_contract_preflight"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
S12613 = ROOT / "runs/local/artifacts/stage12613_stronger_isolation_remediation_preflight"
S12613_EXTERNAL = ROOT / "runs/summaries/stage12613_stronger_isolation_remediation_preflight.json"
EXPECTED_STAGE12613_SUMMARY = "7a0da4dcf0e8acd5f3c66b653bd4ac21b0fc6d227652d6f7a234d73792d4f9fb"
EXPECTED_STAGE12613_CONTRACT = "5a9ddeb2525ffa9f4fe992ec8ae2d3fa93bad498b15c6e64563b2ef8abf80c35"
EXPECTED_STAGE12613_POINTER = "bbbd3c0ed73b09747919ff6f2ebef8d7878956660a641c17d778226fe0b10b4d"
EXPECTED_STAGE12613_PRIVATE = "a99522b2e927312e759855149a802daec8fe1db2d281fb5b96a1df6f1ce27a96"
EXPECTED_GATE_SCOPE = "reviewed_stage12602_execute_reviewed_slot_function_only"

FALSE_FIELDS = (
    "implementation_ready", "stage12595_allowed", "stage12613_allowed", "stage12614_allowed",
    "stage12615_allowed", "execution_performed", "replay_trustworthy", "raw_replay_evidence_present",
    "trusted_replay_raw_evidence_present", "external_bwrap_execution_evidence_present",
    "alternate_replay_evidence_present", "alternate_replay_trustworthy",
    "vm_runner_contract_review_passed", "vm_runner_implementation_ready",
    "vm_runner_execution_allowed", "vm_runner_evidence_present", "vm_runner_trustworthy",
    "causal_transition_atoms_present", "causal_transition_atoms_materialized",
    "causal_transition_atoms_allowed", "causally_committed_pre_outcome_candidate_set_present",
    "observed_stop_continue_decision_provenance_present", "level3_preflight_allowed",
    "level_3_materialized", "level_3_materialization_allowed",
    "training_admission_preflight_allowed", "training_admission_allowed", "training_admitted",
    "training_allowed", "training_run_allowed", "gpu_allocation_requested", "cuda2_training_allowed",
    "strict_eval_admitted", "sealed_eval_admitted", "strict_eval_eligible", "sealed_eval_eligible",
    "admission_allowed", "ranking_allowed", "positive_stop",
)
PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "selector", "raw_stream", "stdout.raw", "stderr.raw",
    "before_commit_oid", "after_commit_oid", "production_path", "production_patch_sha256",
    "manual_executor_slot_contracts", "slot_1.patch", "slot_2.patch", "repository_root",
    "patch_path", "slot_1/", "slot_2/",
)
PHASES = ("initial", "patched", "final")


class VmContractPreflightError(RuntimeError):
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
        raise VmContractPreflightError("json_object_required:" + path.name)
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
        "stage12595_allowed": False,
        "stage12613_allowed": False,
        "stage12614_allowed": False,
        "stage12615_allowed": False,
        "execution_performed": False,
        "replay_trustworthy": False,
        "raw_replay_evidence_present": False,
        "trusted_replay_raw_evidence_present": False,
        "external_bwrap_execution_evidence_present": False,
        "alternate_replay_evidence_present": False,
        "alternate_replay_trustworthy": False,
        "vm_runner_contract_review_passed": False,
        "vm_runner_implementation_ready": False,
        "vm_runner_execution_allowed": False,
        "vm_runner_evidence_present": False,
        "vm_runner_trustworthy": False,
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
            raise VmContractPreflightError(f"{label}_gate_drift:{field}")


def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise VmContractPreflightError(f"{label}_public_leak:{needle}")


def load_stage12613() -> dict[str, Any]:
    summary = read_json(S12613 / "summary.json")
    external = read_json(S12613_EXTERNAL)
    contract = read_json(S12613 / "contract.json")
    pointer = read_json(S12613 / "digest_pointer.json")
    private = read_json(S12613 / "private/stronger_isolation_remediation_preflight.json")
    if summary != external:
        raise VmContractPreflightError("stage12613_external_summary_mismatch")
    expected = (
        (stable_hash(summary), EXPECTED_STAGE12613_SUMMARY, "summary"),
        (stable_hash(contract), EXPECTED_STAGE12613_CONTRACT, "contract"),
        (stable_hash(pointer), EXPECTED_STAGE12613_POINTER, "pointer"),
        (stable_hash(private), EXPECTED_STAGE12613_PRIVATE, "private"),
    )
    for actual, expected_hash, label in expected:
        if actual != expected_hash:
            raise VmContractPreflightError("stage12613_pin_drift:" + label)
    if summary.get("decision") != "BLOCKED_REPLAY_REMEDIATION_CONTRACT_REVIEW_REQUIRED":
        raise VmContractPreflightError("stage12613_decision_drift")
    if summary.get("recommended_stronger_runner") != "disposable_vm_or_microvm":
        raise VmContractPreflightError("stage12613_runner_recommendation_drift")
    if summary.get("stage12614_allowed") is not False:
        raise VmContractPreflightError("stage12613_stage12614_gate_drift")
    if summary.get("training_allowed") is not False:
        raise VmContractPreflightError("stage12613_training_gate_drift")
    for label, record in (("summary", summary), ("contract", contract), ("pointer", pointer), ("private", private)):
        check_false(record, "stage12613_" + label)
    return {"summary": summary, "contract": contract, "pointer": pointer, "private": private}


def private_vm_evidence_files() -> list[str]:
    files = [
        "host_vm_launch_manifest.json",
        "pinned_base_image_digest.txt",
        "pinned_source_archive_digest.txt",
        "reviewed_runner_source_digest.txt",
        "network_absence_attestation.json",
        "independent_security_artifact_review.json",
        "artifact_manifest.json",
    ]
    for slot in (1, 2):
        prefix = f"slot_{slot}"
        files.extend([
            f"{prefix}/vm_boot_manifest.json",
            f"{prefix}/guest_environment_manifest.json",
            f"{prefix}/command_manifest.json",
        ])
        for phase in PHASES:
            files.extend([
                f"{prefix}/{phase}/pytest_report.json",
                f"{prefix}/{phase}/stdout.raw",
                f"{prefix}/{phase}/stderr.raw",
            ])
        files.extend([
            f"{prefix}/phase_exit_statuses.json",
            f"{prefix}/tree_digests.json",
            f"{prefix}/reviewed_slot_execution_result.json",
        ])
    return files


def vm_runner_contract() -> dict[str, Any]:
    private_files = private_vm_evidence_files()
    return {
        "record_type": "stage12614_disposable_vm_runner_contract_v1",
        "preferred_runner": "qemu_kvm_disposable_vm_first",
        "fallback_runner": "qemu_tcg_only_if_kvm_unavailable_and_runtime_is_acceptable",
        "future_microvm_runner": "firecracker_after_equivalent_contract_review",
        "runner_scope": EXPECTED_GATE_SCOPE,
        "execution_authority": "none_in_this_stage",
        "required_private_evidence_file_count": len(private_files),
        "required_private_evidence_relative_files": private_files,
        "public_evidence_classes": [
            "base_image_digest",
            "source_archive_digest",
            "reviewed_runner_source_digest",
            "command_manifest_digest",
            "network_absence_attestation_digest",
            "phase_report_digests",
            "raw_stream_digests",
            "exit_status_agreement_digest",
            "tree_revert_digest",
            "artifact_manifest_digest",
            "independent_review_digest",
        ],
        "minimum_isolation_controls": [
            "fresh_ephemeral_disk_per_replay",
            "no_network_device_attached",
            "read_only_pinned_input_bundle",
            "guest_runs_only_reviewed_command_manifest",
            "host_exports_evidence_after_guest_shutdown",
            "no_gpu_device_exposed",
            "no_host_workspace_mount",
        ],
        "required_phase_sequence": list(PHASES),
        "required_pre_execution_checks": [
            "base_image_digest_matches_reviewed_contract",
            "source_archive_digest_matches_stage12604_materials",
            "runner_source_digest_matches_reviewed_contract",
            "command_manifest_digest_matches_reviewed_contract",
        ],
        "required_post_execution_checks": [
            "process_and_session_exit_status_match",
            "patched_phase_changes_only_bound_production_path",
            "final_tree_digest_matches_initial_after_revert",
            "raw_private_evidence_public_leak_scan_passed",
            "independent_security_and_artifact_review_passed_before_causal_atoms",
        ],
        "rejected_shortcuts": [
            "plain_local_pytest_process",
            "container_only_without_vm_backing",
            "missing_raw_streams",
            "missing_final_revert_digest",
            "public_training_admission_from_runner_success",
        ],
    }


def build_vm_contract_packet(stage12613: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    contract_manifest = vm_runner_contract()
    private = {
        "record_type": "stage12614_private_disposable_vm_runner_contract_preflight_v1",
        "stage12613_summary_sha256": EXPECTED_STAGE12613_SUMMARY,
        "stage12613_private_remediation_preflight_sha256": EXPECTED_STAGE12613_PRIVATE,
        "source_decision": stage12613["summary"]["decision"],
        "gate_scope": EXPECTED_GATE_SCOPE,
        "out_of_band_remediation_contract_only": True,
        "stage12613_stage12614_allowance_preserved_false": True,
        "vm_runner_contract_defined": True,
        "vm_runner_contract": contract_manifest,
        "decision": "BLOCKED_INDEPENDENT_VM_RUNNER_CONTRACT_REVIEW_REQUIRED",
        **no_claim_fields(),
    }
    contract = {
        "record_type": "stage12614_public_disposable_vm_runner_contract_preflight_v1",
        "stage12613_summary_sha256": EXPECTED_STAGE12613_SUMMARY,
        "stage12613_contract_sha256": EXPECTED_STAGE12613_CONTRACT,
        "stage12613_private_remediation_preflight_sha256": EXPECTED_STAGE12613_PRIVATE,
        "gate_scope": EXPECTED_GATE_SCOPE,
        "out_of_band_remediation_contract_only": True,
        "stage12613_stage12614_allowance_preserved_false": True,
        "preferred_runner": "qemu_kvm_disposable_vm_first",
        "fallback_runner": "qemu_tcg_only_if_kvm_unavailable_and_runtime_is_acceptable",
        "vm_runner_contract_defined": True,
        "vm_runner_contract_sha256": stable_hash(contract_manifest),
        "required_private_evidence_file_count": contract_manifest["required_private_evidence_file_count"],
        "public_evidence_class_count": len(contract_manifest["public_evidence_classes"]),
        "private_vm_contract_preflight_sha256": stable_hash(private),
        "claim_boundary": {
            "purpose": "define_vm_runner_evidence_contract_without_execution",
            "implementation": "not_authorized",
            "replay": "not_authorized",
            "level3": "not_authorized",
            "training": "not_authorized",
        },
        **no_claim_fields(),
    }
    summary = {
        "record_type": "stage12614_public_disposable_vm_runner_contract_preflight_summary_v1",
        "stage": STAGE,
        "decision": "BLOCKED_INDEPENDENT_VM_RUNNER_CONTRACT_REVIEW_REQUIRED",
        "stage12613_summary_sha256": EXPECTED_STAGE12613_SUMMARY,
        "gate_scope": EXPECTED_GATE_SCOPE,
        "out_of_band_remediation_contract_only": True,
        "stage12613_stage12614_allowance_preserved_false": True,
        "preferred_runner": "qemu_kvm_disposable_vm_first",
        "fallback_runner": "qemu_tcg_only_if_kvm_unavailable_and_runtime_is_acceptable",
        "vm_runner_contract_defined": True,
        "vm_runner_contract_sha256": stable_hash(contract_manifest),
        "required_private_evidence_file_count": contract_manifest["required_private_evidence_file_count"],
        "public_evidence_class_count": len(contract_manifest["public_evidence_classes"]),
        "private_vm_contract_preflight_sha256": stable_hash(private),
        "downstream_blockers": [
            "stage12613_stage12614_allowance_remains_false",
            "independent_vm_runner_contract_review_absent",
            "vm_runner_implementation_absent",
            "trusted_replay_raw_evidence_absent",
            "causal_transition_atoms_absent",
            "level3_materialization_forbidden",
            "separate_training_admission_gate_absent",
            "training_admission_forbidden",
        ],
        **no_claim_fields(),
    }
    for label, record in (("summary", summary), ("contract", contract)):
        check_false(record, "stage12614_" + label)
        assert_public_sanitized(record, "stage12614_" + label)
    check_false(private, "stage12614_private")
    return summary, contract, private


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    stage12613 = load_stage12613()
    summary, contract, private = build_vm_contract_packet(stage12613)
    pointer = {
        "record_type": "stage12614_public_private_disposable_vm_runner_contract_pointer_v1",
        "stage12613_summary_sha256": EXPECTED_STAGE12613_SUMMARY,
        "contract_sha256": stable_hash(contract),
        "private_vm_contract_preflight_sha256": stable_hash(private),
        "out_of_band_remediation_contract_only": True,
        "stage12613_stage12614_allowance_preserved_false": True,
        "preferred_runner": "qemu_kvm_disposable_vm_first",
        "vm_runner_contract_defined": True,
        **no_claim_fields(),
    }
    check_false(pointer, "stage12614_pointer")
    assert_public_sanitized(pointer, "stage12614_pointer")
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "private/disposable_vm_runner_contract_preflight.json", private)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
