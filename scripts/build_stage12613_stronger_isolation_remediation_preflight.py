#!/usr/bin/env python3
"""Build Stage12613 stronger isolation remediation preflight.

Stage12612 correctly blocks replay resumption because the required bwrap
evidence is absent. This stage does not resume replay. It records a remediation
contract: the trust objective is independently auditable replay evidence, while
the preferred stronger implementation target is a disposable VM or microVM
runner rather than host-dependent bwrap.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12613_stronger_isolation_remediation_preflight"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
S12612 = ROOT / "runs/local/artifacts/stage12612_trusted_replay_resumption_gate_blocker"
S12612_EXTERNAL = ROOT / "runs/summaries/stage12612_trusted_replay_resumption_gate_blocker.json"
EXPECTED_STAGE12612_SUMMARY = "11d10263c3acd8e25f9891afc5cdfe6b4f114c9101e319d1fdc5f4fdc3d6e538"
EXPECTED_STAGE12612_CONTRACT = "3ff3bff0fb5ee84bd0a0c67a858adb9bde99f12bd67ecfec066d56960d191646"
EXPECTED_STAGE12612_POINTER = "ed944aa702b19265a1b4ad3b9d32a1e59ccb09c052f904410eca58fd73577624"
EXPECTED_STAGE12612_PRIVATE = "1cd4a2b366e16125c072d2224ee1a7215f18cdc43f4b54e44f63605fd471a865"
EXPECTED_GATE_SCOPE = "reviewed_stage12602_execute_reviewed_slot_function_only"

FALSE_FIELDS = (
    "implementation_ready", "stage12595_allowed", "stage12613_allowed", "stage12614_allowed",
    "execution_performed", "replay_trustworthy", "raw_replay_evidence_present",
    "trusted_replay_raw_evidence_present", "external_bwrap_execution_evidence_present",
    "alternate_replay_evidence_present", "alternate_replay_trustworthy",
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
    "patch_path",
)


class RemediationPreflightError(RuntimeError):
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
        raise RemediationPreflightError("json_object_required:" + path.name)
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
        "execution_performed": False,
        "replay_trustworthy": False,
        "raw_replay_evidence_present": False,
        "trusted_replay_raw_evidence_present": False,
        "external_bwrap_execution_evidence_present": False,
        "alternate_replay_evidence_present": False,
        "alternate_replay_trustworthy": False,
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
            raise RemediationPreflightError(f"{label}_gate_drift:{field}")


def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise RemediationPreflightError(f"{label}_public_leak:{needle}")


def load_stage12612() -> dict[str, Any]:
    summary = read_json(S12612 / "summary.json")
    external = read_json(S12612_EXTERNAL)
    contract = read_json(S12612 / "contract.json")
    pointer = read_json(S12612 / "digest_pointer.json")
    private = read_json(S12612 / "private/trusted_replay_resumption_gate_blocker.json")
    if summary != external:
        raise RemediationPreflightError("stage12612_external_summary_mismatch")
    expected = (
        (stable_hash(summary), EXPECTED_STAGE12612_SUMMARY, "summary"),
        (stable_hash(contract), EXPECTED_STAGE12612_CONTRACT, "contract"),
        (stable_hash(pointer), EXPECTED_STAGE12612_POINTER, "pointer"),
        (stable_hash(private), EXPECTED_STAGE12612_PRIVATE, "private"),
    )
    for actual, expected_hash, label in expected:
        if actual != expected_hash:
            raise RemediationPreflightError("stage12612_pin_drift:" + label)
    if summary.get("decision") != "BLOCKED_TRUSTED_REPLAY_RESUMPTION_REQUIRES_EXTERNAL_BWRAP_EVIDENCE":
        raise RemediationPreflightError("stage12612_decision_drift")
    if summary.get("stage12613_allowed") is not False:
        raise RemediationPreflightError("stage12612_stage12613_gate_drift")
    if summary.get("training_allowed") is not False:
        raise RemediationPreflightError("stage12612_training_gate_drift")
    if summary.get("required_external_evidence_file_count") != 14:
        raise RemediationPreflightError("stage12612_evidence_count_drift")
    for label, record in (("summary", summary), ("contract", contract), ("pointer", pointer), ("private", private)):
        check_false(record, "stage12612_" + label)
    return {"summary": summary, "contract": contract, "pointer": pointer, "private": private}


def isolation_remediation_contract() -> dict[str, Any]:
    return {
        "record_type": "stage12613_stronger_isolation_remediation_contract_v1",
        "trust_objective": "independently_auditable_replay_evidence_not_a_specific_sandbox_brand",
        "preferred_runner_tier": "disposable_vm_or_microvm",
        "preferred_runner_examples": [
            "short_lived_qemu_or_kvm_vm",
            "firecracker_microvm_when_available",
            "kata_or_similar_vm_backed_container_when_available",
        ],
        "why_stronger_than_bwrap": [
            "separate_guest_kernel_boundary_or_vm_backed_isolation",
            "fresh_ephemeral_disk_per_replay",
            "host_controlled_evidence_export_after_guest_shutdown",
            "no_dependency_on_nested_user_namespace_or_loopback_setup_inside_current_container",
        ],
        "minimum_evidence_controls": [
            "pinned_base_image_digest",
            "pinned_source_archive_digest",
            "pinned_reviewed_runner_source_digest",
            "exact_command_manifest_digest",
            "network_disabled_or_proven_absent",
            "initial_patched_final_phase_reports",
            "raw_stream_digests",
            "process_and_session_exit_status_match",
            "input_patch_digests_match_stage12604_materials",
            "final_tree_digest_matches_initial_after_revert",
            "public_private_artifact_separation",
            "independent_security_and_artifact_review_required_before_causal_atoms",
        ],
        "acceptable_fallback_tiers": [
            {
                "tier": "vm_backed_container",
                "status": "acceptable_if_independently_reviewed_and_evidence_complete",
            },
            {
                "tier": "hardened_bwrap",
                "status": "acceptable_if_host_capable_and_stage12612_evidence_complete",
            },
            {
                "tier": "plain_local_process",
                "status": "not_acceptable_for_trusted_replay_claims",
            },
        ],
        "residual_assumptions_to_state_later": [
            "host_hypervisor_and_kernel_trusted_for_evidence_capture",
            "base_image_digest_resolves_to_reviewed_toolchain",
            "source_archive_created_from_pinned_material_without private path disclosure",
            "reviewer_can_recompute_public_semantic_hashes_from private evidence",
        ],
        "still_forbidden": [
            "claiming_replay_success",
            "materializing_causal_transition_atoms",
            "materializing_level3",
            "admitting_training",
            "allocating_gpu",
            "strict_or_sealed_eval_admission",
        ],
    }


def build_remediation_packet(stage12612: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    contract_manifest = isolation_remediation_contract()
    private = {
        "record_type": "stage12613_private_stronger_isolation_remediation_preflight_v1",
        "stage12612_summary_sha256": EXPECTED_STAGE12612_SUMMARY,
        "stage12612_private_resumption_gate_blocker_sha256": EXPECTED_STAGE12612_PRIVATE,
        "source_decision": stage12612["summary"]["decision"],
        "gate_scope": EXPECTED_GATE_SCOPE,
        "remediation_preflight_only": True,
        "stage12612_blocker_preserved": True,
        "external_bwrap_execution_required_by_stage12612": True,
        "recommended_stronger_runner": "disposable_vm_or_microvm",
        "alternate_contract_is_draft": True,
        "alternate_contract_requires_future_independent_review": True,
        "isolation_remediation_contract": contract_manifest,
        "decision": "BLOCKED_REPLAY_REMEDIATION_CONTRACT_REVIEW_REQUIRED",
        **no_claim_fields(),
    }
    contract = {
        "record_type": "stage12613_public_stronger_isolation_remediation_contract_v1",
        "stage12612_summary_sha256": EXPECTED_STAGE12612_SUMMARY,
        "stage12612_contract_sha256": EXPECTED_STAGE12612_CONTRACT,
        "stage12612_private_resumption_gate_blocker_sha256": EXPECTED_STAGE12612_PRIVATE,
        "gate_scope": EXPECTED_GATE_SCOPE,
        "remediation_preflight_only": True,
        "stage12612_blocker_preserved": True,
        "recommended_stronger_runner": "disposable_vm_or_microvm",
        "alternate_contract_is_draft": True,
        "alternate_contract_requires_future_independent_review": True,
        "isolation_remediation_contract_sha256": stable_hash(contract_manifest),
        "private_remediation_preflight_sha256": stable_hash(private),
        "claim_boundary": {
            "purpose": "realign_runner_choice_without_resuming_replay",
            "preferred_runner": "vm_or_microvm_isolation",
            "training": "not_authorized",
            "level3": "not_authorized",
            "causal_atoms": "not_authorized",
        },
        **no_claim_fields(),
    }
    summary = {
        "record_type": "stage12613_public_stronger_isolation_remediation_preflight_summary_v1",
        "stage": STAGE,
        "decision": "BLOCKED_REPLAY_REMEDIATION_CONTRACT_REVIEW_REQUIRED",
        "stage12612_summary_sha256": EXPECTED_STAGE12612_SUMMARY,
        "gate_scope": EXPECTED_GATE_SCOPE,
        "remediation_preflight_only": True,
        "stage12612_blocker_preserved": True,
        "recommended_stronger_runner": "disposable_vm_or_microvm",
        "alternate_contract_is_draft": True,
        "alternate_contract_requires_future_independent_review": True,
        "isolation_remediation_contract_sha256": stable_hash(contract_manifest),
        "private_remediation_preflight_sha256": stable_hash(private),
        "downstream_blockers": [
            "stage12612_external_evidence_still_missing",
            "alternate_trust_contract_not_independently_reviewed",
            "alternate_runner_not_implemented",
            "trusted_replay_raw_evidence_absent",
            "causal_transition_atoms_absent",
            "level3_materialization_forbidden",
            "separate_training_admission_gate_absent",
            "training_admission_forbidden",
        ],
        **no_claim_fields(),
    }
    for label, record in (("summary", summary), ("contract", contract)):
        check_false(record, "stage12613_" + label)
        assert_public_sanitized(record, "stage12613_" + label)
    check_false(private, "stage12613_private")
    return summary, contract, private


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    stage12612 = load_stage12612()
    summary, contract, private = build_remediation_packet(stage12612)
    pointer = {
        "record_type": "stage12613_public_private_stronger_isolation_remediation_pointer_v1",
        "stage12612_summary_sha256": EXPECTED_STAGE12612_SUMMARY,
        "contract_sha256": stable_hash(contract),
        "private_remediation_preflight_sha256": stable_hash(private),
        "remediation_preflight_only": True,
        "stage12612_blocker_preserved": True,
        "recommended_stronger_runner": "disposable_vm_or_microvm",
        "alternate_contract_is_draft": True,
        "alternate_contract_requires_future_independent_review": True,
        **no_claim_fields(),
    }
    check_false(pointer, "stage12613_pointer")
    assert_public_sanitized(pointer, "stage12613_pointer")
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "private/stronger_isolation_remediation_preflight.json", private)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
