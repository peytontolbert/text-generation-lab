#!/usr/bin/env python3
"""Build Stage12611 separate training admission preflight blocker.

Stage12610 blocks Level-3 materialization. This stage records the separate
training-admission requirements and keeps training/eval admission closed. It
makes explicit that replay success, causal atoms, or Level-3 alone would still
not admit training without a later independent training gate.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12611_separate_training_admission_preflight_blocker"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
S12610 = ROOT / "runs/local/artifacts/stage12610_level3_materialization_preflight_blocker"
S12610_EXTERNAL = ROOT / "runs/summaries/stage12610_level3_materialization_preflight_blocker.json"
EXPECTED_STAGE12610_SUMMARY = "e60a8c931f26a45f8fc5c94924f1afaa707a1603eb953965c776a7fab21c9f9f"
EXPECTED_STAGE12610_CONTRACT = "6a1cbdcfe159ba557920f5286b9be324626187386afe9b53802616eb7154a3ba"
EXPECTED_STAGE12610_POINTER = "c5549508f4b8a317f18ced69be7bdfb223f4978f30e1bedd88622bd57d320cf8"
EXPECTED_STAGE12610_PRIVATE = "45f31d6f2043c4e2901db8b12f261c1a52f5c15c6f616aab2ba3ba152cf124ff"
EXPECTED_GATE_SCOPE = "reviewed_stage12602_execute_reviewed_slot_function_only"
FALSE_FIELDS = (
    "implementation_ready", "stage12595_allowed", "execution_performed", "replay_trustworthy",
    "raw_replay_evidence_present", "causal_transition_atoms_present", "causal_transition_atoms_materialized",
    "causal_transition_atoms_allowed", "causally_committed_pre_outcome_candidate_set_present",
    "observed_stop_continue_decision_provenance_present", "level3_preflight_allowed",
    "level_3_materialized", "level_3_materialization_allowed",
    "training_admission_preflight_allowed", "training_admission_allowed", "training_admitted",
    "training_allowed", "training_run_allowed", "gpu_allocation_requested", "cuda2_training_allowed",
    "strict_eval_admitted", "sealed_eval_admitted", "strict_eval_eligible", "sealed_eval_eligible",
    "admission_allowed", "ranking_allowed", "positive_stop",
)
PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "selector", "raw_stream", "stdout.raw", "stderr.raw", "before_commit_oid",
    "after_commit_oid", "production_path", "production_patch_sha256", "manual_executor_slot_contracts",
    "slot_1.patch", "slot_2.patch", "future_evidence", "repository_root", "patch_path", "snapshot",
)


class TrainingAdmissionError(RuntimeError):
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
        raise TrainingAdmissionError("json_object_required:" + path.name)
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
        "execution_performed": False,
        "replay_trustworthy": False,
        "raw_replay_evidence_present": False,
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
            raise TrainingAdmissionError(f"{label}_gate_drift:{field}")


def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise TrainingAdmissionError(f"{label}_public_leak:{needle}")


def load_stage12610() -> dict[str, Any]:
    summary = read_json(S12610 / "summary.json")
    external = read_json(S12610_EXTERNAL)
    contract = read_json(S12610 / "contract.json")
    pointer = read_json(S12610 / "digest_pointer.json")
    private = read_json(S12610 / "private/level3_materialization_preflight_blocker.json")
    if summary != external:
        raise TrainingAdmissionError("stage12610_external_summary_mismatch")
    expected = (
        (stable_hash(summary), EXPECTED_STAGE12610_SUMMARY, "summary"),
        (stable_hash(contract), EXPECTED_STAGE12610_CONTRACT, "contract"),
        (stable_hash(pointer), EXPECTED_STAGE12610_POINTER, "pointer"),
        (stable_hash(private), EXPECTED_STAGE12610_PRIVATE, "private"),
    )
    for actual, expected_hash, label in expected:
        if actual != expected_hash:
            raise TrainingAdmissionError("stage12610_pin_drift:" + label)
    if summary.get("decision") != "BLOCKED_CAUSAL_TRANSITION_ATOMS_AND_PROVENANCE_REQUIRED_FOR_LEVEL3":
        raise TrainingAdmissionError("stage12610_decision_drift")
    if summary.get("level_3_materialized") is not False:
        raise TrainingAdmissionError("stage12610_level3_drift")
    if summary.get("stage12611_allowed") is not False:
        raise TrainingAdmissionError("stage12610_broad_stage12611_drift")
    if summary.get("training_admission_preflight_allowed") is not False:
        raise TrainingAdmissionError("stage12610_training_preflight_drift")
    if private.get("level3_requirement_manifest", {}).get("not_sufficient_for_training") is None:
        raise TrainingAdmissionError("stage12610_training_separation_manifest_missing")
    for label, record in (("summary", summary), ("contract", contract), ("pointer", pointer), ("private", private)):
        check_false(record, "stage12610_" + label)
    return {"summary": summary, "contract": contract, "pointer": pointer, "private": private}


def training_admission_requirements() -> dict[str, Any]:
    return {
        "record_type": "stage12611_separate_training_admission_requirements_v1",
        "required_before_training_admission": [
            "trusted_replay_raw_evidence_present",
            "independent_execution_artifact_review_passed",
            "causal_transition_atoms_materialized",
            "level_3_materialized",
            "causally_committed_pre_outcome_candidate_set_present",
            "observed_stop_continue_decision_provenance_present",
            "separate_training_data_admission_review_passed",
            "train_eval_contamination_guard_passed",
            "strict_eval_and_sealed_eval_still_separate_or_explicitly_admitted_by_future_gate",
            "gpu_allocation_explicitly_authorized_for_cuda2_only_if_training_runs",
        ],
        "not_sufficient_for_training": [
            "replay_success_alone",
            "causal_transition_atoms_alone",
            "level3_materialization_alone",
            "public_handoff_or_preflight_artifacts_alone",
        ],
        "forbidden_until_requirements_met": [
            "training_admitted",
            "training_allowed",
            "training_run_allowed",
            "gpu_allocation_requested",
            "strict_eval_admitted",
            "sealed_eval_admitted",
        ],
    }


def build_training_preflight_packet(stage12610: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    requirements = training_admission_requirements()
    private = {
        "record_type": "stage12611_private_separate_training_admission_preflight_blocker_v1",
        "stage12610_summary_sha256": EXPECTED_STAGE12610_SUMMARY,
        "stage12610_private_level3_preflight_blocker_sha256": EXPECTED_STAGE12610_PRIVATE,
        "gate_scope": EXPECTED_GATE_SCOPE,
        "source_decision": stage12610["summary"]["decision"],
        "level_3_materialized": False,
        "causal_transition_atom_count": stage12610["summary"]["causal_transition_atom_count"],
        "causal_transition_atoms_present": False,
        "causally_committed_pre_outcome_candidate_set_present": False,
        "observed_stop_continue_decision_provenance_present": False,
        "trusted_replay_raw_evidence_present": False,
        "separate_training_admission_required": True,
        "level3_not_sufficient_for_training": True,
        "training_admission_blocker_recorded": True,
        "separate_training_data_admission_review_present": False,
        "training_admission_requirement_manifest": requirements,
        "decision": "BLOCKED_SEPARATE_TRAINING_ADMISSION_REQUIREMENTS_UNMET",
        "stage12612_allowed": False,
        "future_training_candidate_intake_allowed": False,
        **no_claim_fields(),
    }
    contract = {
        "record_type": "stage12611_public_separate_training_admission_preflight_contract_v1",
        "stage12610_summary_sha256": EXPECTED_STAGE12610_SUMMARY,
        "stage12610_contract_sha256": EXPECTED_STAGE12610_CONTRACT,
        "stage12610_private_level3_preflight_blocker_sha256": EXPECTED_STAGE12610_PRIVATE,
        "gate_scope": EXPECTED_GATE_SCOPE,
        "level_3_materialized": False,
        "causal_transition_atom_count": 0,
        "causal_transition_atoms_present": False,
        "causally_committed_pre_outcome_candidate_set_present": False,
        "observed_stop_continue_decision_provenance_present": False,
        "trusted_replay_raw_evidence_present": False,
        "separate_training_admission_required": True,
        "level3_not_sufficient_for_training": True,
        "training_admission_blocker_recorded": True,
        "separate_training_data_admission_review_present": False,
        "training_admission_requirement_manifest_sha256": stable_hash(requirements),
        "private_training_preflight_blocker_sha256": stable_hash(private),
        "stage12612_allowed": False,
        "future_training_candidate_intake_allowed": False,
        "claim_boundary": {
            "training_admission": "separate_future_gate_required_after_level3_and_data_review",
            "gpu": "no_gpu_allocation_requested_or_allowed_by_this_stage",
            "strict_eval": "not_admitted_by_training_preflight",
            "sealed_eval": "not_admitted_by_training_preflight",
        },
        **no_claim_fields(),
    }
    summary = {
        "record_type": "stage12611_public_separate_training_admission_preflight_blocker_summary_v1",
        "stage": STAGE,
        "decision": "BLOCKED_SEPARATE_TRAINING_ADMISSION_REQUIREMENTS_UNMET",
        "stage12610_summary_sha256": EXPECTED_STAGE12610_SUMMARY,
        "gate_scope": EXPECTED_GATE_SCOPE,
        "level_3_materialized": False,
        "causal_transition_atom_count": 0,
        "causal_transition_atoms_present": False,
        "causally_committed_pre_outcome_candidate_set_present": False,
        "observed_stop_continue_decision_provenance_present": False,
        "trusted_replay_raw_evidence_present": False,
        "separate_training_admission_required": True,
        "level3_not_sufficient_for_training": True,
        "training_admission_blocker_recorded": True,
        "separate_training_data_admission_review_present": False,
        "training_admission_requirement_manifest_sha256": stable_hash(requirements),
        "private_training_preflight_blocker_sha256": stable_hash(private),
        "stage12612_allowed": False,
        "future_training_candidate_intake_allowed": False,
        "downstream_blockers": [
            "trusted_replay_raw_evidence_absent",
            "causal_transition_atoms_absent",
            "level3_materialization_absent",
            "separate_training_data_admission_review_absent",
            "train_eval_contamination_guard_absent",
            "training_admission_forbidden",
            "gpu_allocation_forbidden",
            "strict_eval_admission_forbidden",
            "sealed_eval_admission_forbidden",
        ],
        **no_claim_fields(),
    }
    for label, record in (("summary", summary), ("contract", contract)):
        check_false(record, "stage12611_" + label)
        assert_public_sanitized(record, "stage12611_" + label)
    check_false(private, "stage12611_private")
    return summary, contract, private


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    stage12610 = load_stage12610()
    summary, contract, private = build_training_preflight_packet(stage12610)
    pointer = {
        "record_type": "stage12611_public_private_separate_training_admission_preflight_pointer_v1",
        "stage12610_summary_sha256": EXPECTED_STAGE12610_SUMMARY,
        "private_training_preflight_blocker_sha256": stable_hash(private),
        "contract_sha256": stable_hash(contract),
        "level_3_materialized": False,
        "causal_transition_atoms_present": False,
        "causally_committed_pre_outcome_candidate_set_present": False,
        "observed_stop_continue_decision_provenance_present": False,
        "separate_training_admission_required": True,
        "level3_not_sufficient_for_training": True,
        "training_admission_blocker_recorded": True,
        "training_admission_allowed": False,
        "training_admitted": False,
        "training_allowed": False,
        "training_run_allowed": False,
        "gpu_allocation_requested": False,
        "cuda2_training_allowed": False,
        "strict_eval_admitted": False,
        "sealed_eval_admitted": False,
        "stage12612_allowed": False,
        "future_training_candidate_intake_allowed": False,
        **no_claim_fields(),
    }
    check_false(pointer, "stage12611_pointer")
    assert_public_sanitized(pointer, "stage12611_pointer")
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "private/separate_training_admission_preflight_blocker.json", private)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
