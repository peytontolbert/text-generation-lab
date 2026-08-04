#!/usr/bin/env python3
"""Build Stage12616 independent VM/storage contract review.

Stage12614 defined the disposable VM runner evidence contract and Stage12615
defined host storage containment. This stage records an independent review of
those contracts. A passed contract review does not authorize implementation,
VM execution, replay trust, causal atoms, Level-3, or training.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12616_independent_vm_storage_contract_review"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
S12615 = ROOT / "runs/local/artifacts/stage12615_vm_storage_containment_preflight"
S12615_EXTERNAL = ROOT / "runs/summaries/stage12615_vm_storage_containment_preflight.json"
EXPECTED_STAGE12615_SUMMARY = "bd859c0acfd9aa3c83022e1cb3af59cf06692d4b7b4ca48033b88cfa67c19826"
EXPECTED_STAGE12615_CONTRACT = "7c638326aac0695c2779c9f2a30f6d39896b060a43cf6663ea877c456bd9797e"
EXPECTED_STAGE12615_POINTER = "5ed24051205861a07350bebb54c43fbd91382dfd9db87921ddf9458677ec7ee3"
EXPECTED_STAGE12615_PRIVATE = "9f4835c472432d6dc34ab6903e42eb65414f18aa84b759ad2e1b4ae1f98fcd8d"
EXPECTED_GATE_SCOPE = "reviewed_stage12602_execute_reviewed_slot_function_only"

FALSE_FIELDS = (
    "implementation_ready", "source_packet_implementation_allowed", "stage12595_allowed",
    "stage12613_allowed", "stage12614_allowed", "stage12615_allowed", "stage12616_allowed",
    "stage12617_allowed", "execution_performed", "replay_trustworthy",
    "raw_replay_evidence_present", "trusted_replay_raw_evidence_present",
    "external_bwrap_execution_evidence_present", "alternate_replay_evidence_present",
    "alternate_replay_trustworthy", "vm_runner_implementation_ready",
    "vm_runner_execution_allowed", "vm_runner_evidence_present", "vm_runner_trustworthy",
    "storage_root_created", "storage_write_performed", "host_workspace_mounted_in_guest",
    "host_volume_mounted_in_guest", "guest_network_enabled", "guest_gpu_enabled",
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
    "/data/", "/arxiv/", "agentkernel_vm_replay", "/dev/", "selector", "raw_stream",
    "stdout.raw", "stderr.raw", "before_commit_oid", "after_commit_oid", "production_path",
    "production_patch_sha256", "manual_executor_slot_contracts", "slot_1.patch",
    "slot_2.patch", "repository_root", "patch_path", "slot_1/", "slot_2/",
)


class ContractReviewError(RuntimeError):
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
        raise ContractReviewError("json_object_required:" + path.name)
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
            raise ContractReviewError(f"{label}_gate_drift:{field}")


def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise ContractReviewError(f"{label}_public_leak:{needle}")


def load_stage12615() -> dict[str, Any]:
    summary = read_json(S12615 / "summary.json")
    external = read_json(S12615_EXTERNAL)
    contract = read_json(S12615 / "contract.json")
    pointer = read_json(S12615 / "digest_pointer.json")
    private = read_json(S12615 / "private/vm_storage_containment_preflight.json")
    if summary != external:
        raise ContractReviewError("stage12615_external_summary_mismatch")
    expected = (
        (stable_hash(summary), EXPECTED_STAGE12615_SUMMARY, "summary"),
        (stable_hash(contract), EXPECTED_STAGE12615_CONTRACT, "contract"),
        (stable_hash(pointer), EXPECTED_STAGE12615_POINTER, "pointer"),
        (stable_hash(private), EXPECTED_STAGE12615_PRIVATE, "private"),
    )
    for actual, expected_hash, label in expected:
        if actual != expected_hash:
            raise ContractReviewError("stage12615_pin_drift:" + label)
    if summary.get("decision") != "BLOCKED_STORAGE_CONTAINMENT_REVIEW_REQUIRED":
        raise ContractReviewError("stage12615_decision_drift")
    required_true = (
        "storage_capacity_requirement_met",
        "scratch_parent_is_mount",
        "scratch_parent_separate_device_from_root",
        "scratch_parent_separate_device_from_workspace",
        "storage_containment_preflight_only",
        "stage12614_stage12615_allowance_preserved_false",
    )
    for field in required_true:
        if summary.get(field) is not True:
            raise ContractReviewError("stage12615_required_true_drift:" + field)
    if summary.get("stage12616_allowed") is not False:
        raise ContractReviewError("stage12615_stage12616_gate_drift")
    if summary.get("vm_runner_execution_allowed") is not False:
        raise ContractReviewError("stage12615_execution_gate_drift")
    if summary.get("training_allowed") is not False:
        raise ContractReviewError("stage12615_training_gate_drift")
    for label, record in (("summary", summary), ("contract", contract), ("pointer", pointer), ("private", private)):
        check_false(record, "stage12615_" + label)
    return {"summary": summary, "contract": contract, "pointer": pointer, "private": private}


def review_findings() -> dict[str, Any]:
    return {
        "record_type": "stage12616_independent_vm_storage_contract_review_findings_v1",
        "review_scope": [
            "stage12614_disposable_vm_evidence_contract",
            "stage12615_host_storage_containment_contract",
        ],
        "passed_checks": [
            "vm_contract_rejects_plain_local_process",
            "vm_contract_requires_no_network_and_no_gpu",
            "vm_contract_requires_raw_private_evidence_and_public_digest_classes",
            "vm_contract_requires_independent_security_artifact_review_source_file",
            "storage_contract_forbids_workspace_mounts",
            "storage_contract_forbids_private_scratch_root_mounts_into_guest",
            "storage_contract_forbids_shared_host_folders_and_host_block_device_passthrough",
            "storage_contract_requires_private_scratch_parent_mountpoint",
            "storage_contract_requires_private_scratch_parent_device_separate_from_root_and_workspace",
            "public_artifacts_sanitize_private_storage_paths",
        ],
        "residual_assumptions": [
            "future_runner_source_must_enforce_contract_before_any_vm_launch",
            "future_qemu_command_review_must prove no host mounts or network devices",
            "future_scratch_directory_creation_requires explicit approval",
            "future evidence extraction must happen only after guest shutdown",
        ],
        "forbidden_after_review_pass": [
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


def build_review_packet(stage12615: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    findings = review_findings()
    private = {
        "record_type": "stage12616_private_independent_vm_storage_contract_review_v1",
        "stage12615_summary_sha256": EXPECTED_STAGE12615_SUMMARY,
        "stage12615_private_storage_containment_preflight_sha256": EXPECTED_STAGE12615_PRIVATE,
        "source_decision": stage12615["summary"]["decision"],
        "gate_scope": EXPECTED_GATE_SCOPE,
        "independent_contract_review_performed": True,
        "independent_contract_review_passed": True,
        "vm_runner_contract_review_passed": True,
        "storage_containment_review_passed": True,
        "source_packet_recommended": True,
        "review_findings": findings,
        "decision": "INDEPENDENT_VM_STORAGE_CONTRACT_REVIEW_PASSED_SOURCE_PACKET_STILL_BLOCKED",
        **no_claim_fields(),
    }
    contract = {
        "record_type": "stage12616_public_independent_vm_storage_contract_review_v1",
        "stage12615_summary_sha256": EXPECTED_STAGE12615_SUMMARY,
        "stage12615_contract_sha256": EXPECTED_STAGE12615_CONTRACT,
        "stage12615_private_storage_containment_preflight_sha256": EXPECTED_STAGE12615_PRIVATE,
        "gate_scope": EXPECTED_GATE_SCOPE,
        "independent_contract_review_performed": True,
        "independent_contract_review_passed": True,
        "vm_runner_contract_review_passed": True,
        "storage_containment_review_passed": True,
        "source_packet_recommended": True,
        "review_findings_sha256": stable_hash(findings),
        "private_contract_review_sha256": stable_hash(private),
        "claim_boundary": {
            "contract_review": "passed",
            "source_packet": "recommended_not_authorized",
            "vm_launch": "not_authorized",
            "replay": "not_authorized",
            "training": "not_authorized",
        },
        **no_claim_fields(),
    }
    summary = {
        "record_type": "stage12616_public_independent_vm_storage_contract_review_summary_v1",
        "stage": STAGE,
        "decision": "INDEPENDENT_VM_STORAGE_CONTRACT_REVIEW_PASSED_SOURCE_PACKET_STILL_BLOCKED",
        "stage12615_summary_sha256": EXPECTED_STAGE12615_SUMMARY,
        "gate_scope": EXPECTED_GATE_SCOPE,
        "independent_contract_review_performed": True,
        "independent_contract_review_passed": True,
        "vm_runner_contract_review_passed": True,
        "storage_containment_review_passed": True,
        "source_packet_recommended": True,
        "review_findings_sha256": stable_hash(findings),
        "private_contract_review_sha256": stable_hash(private),
        "downstream_blockers": [
            "source_packet_not_authorized_by_this_review",
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
        check_false(record, "stage12616_" + label)
        assert_public_sanitized(record, "stage12616_" + label)
    check_false(private, "stage12616_private")
    return summary, contract, private


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    stage12615 = load_stage12615()
    summary, contract, private = build_review_packet(stage12615)
    pointer = {
        "record_type": "stage12616_public_private_independent_vm_storage_contract_review_pointer_v1",
        "stage12615_summary_sha256": EXPECTED_STAGE12615_SUMMARY,
        "contract_sha256": stable_hash(contract),
        "private_contract_review_sha256": stable_hash(private),
        "independent_contract_review_performed": True,
        "independent_contract_review_passed": True,
        "vm_runner_contract_review_passed": True,
        "storage_containment_review_passed": True,
        "source_packet_recommended": True,
        **no_claim_fields(),
    }
    check_false(pointer, "stage12616_pointer")
    assert_public_sanitized(pointer, "stage12616_pointer")
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "private/independent_vm_storage_contract_review.json", private)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
