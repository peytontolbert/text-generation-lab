#!/usr/bin/env python3
"""Build Stage12610 Level-3 materialization preflight blocker.

Stage12609 blocks causal transition atoms because trusted replay execution
evidence is absent. This stage records the Level-3 prerequisites and blocks
materialization until causal atoms, pre-outcome candidate commitment, and
observed stop/continue provenance exist.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12610_level3_materialization_preflight_blocker"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
S12609 = ROOT / "runs/local/artifacts/stage12609_causal_transition_atom_preflight_blocker"
S12609_EXTERNAL = ROOT / "runs/summaries/stage12609_causal_transition_atom_preflight_blocker.json"
EXPECTED_STAGE12609_SUMMARY = "30a4ea41084e9bd53af7a1c83ed9d7315edd5116f89ac50dc5d9bdcb507740f9"
EXPECTED_STAGE12609_CONTRACT = "3a1ed9c76210dad3a2db18909214f0866264844965f632bfc8978a7fb8ad13fc"
EXPECTED_STAGE12609_POINTER = "a68d255b21e78a679b3ba54851d8e1d0d5b2e19ecf3c8aae730dad26463fd921"
EXPECTED_STAGE12609_PRIVATE = "a598052447ddc2cdc90b9777b6ac276622f3f57e8371352c4bd27ec82587e9a8"
EXPECTED_GATE_SCOPE = "reviewed_stage12602_execute_reviewed_slot_function_only"
FALSE_FIELDS = (
    "implementation_ready", "stage12595_allowed", "execution_performed", "replay_trustworthy",
    "raw_replay_evidence_present", "causal_transition_atoms_materialized", "causal_transition_atoms_allowed",
    "level3_preflight_allowed", "level_3_materialized", "level_3_materialization_allowed",
    "training_admitted", "strict_eval_admitted", "sealed_eval_admitted", "strict_eval_eligible",
    "sealed_eval_eligible", "admission_allowed", "training_allowed", "ranking_allowed", "positive_stop",
)
PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "selector", "raw_stream", "stdout.raw", "stderr.raw", "before_commit_oid",
    "after_commit_oid", "production_path", "production_patch_sha256", "manual_executor_slot_contracts",
    "slot_1.patch", "slot_2.patch", "future_evidence", "repository_root", "patch_path", "snapshot",
)


class Level3PreflightError(RuntimeError):
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
        raise Level3PreflightError("json_object_required:" + path.name)
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
        "causal_transition_atoms_materialized": False,
        "causal_transition_atoms_allowed": False,
        "level3_preflight_allowed": False,
        "level_3_materialized": False,
        "level_3_materialization_allowed": False,
        "training_admitted": False,
        "strict_eval_admitted": False,
        "sealed_eval_admitted": False,
        "strict_eval_eligible": False,
        "sealed_eval_eligible": False,
        "admission_allowed": False,
        "training_allowed": False,
        "ranking_allowed": False,
        "positive_stop": False,
    }


def check_false(record: Mapping[str, Any], label: str) -> None:
    for field in FALSE_FIELDS:
        if field in record and record[field] is not False:
            raise Level3PreflightError(f"{label}_gate_drift:{field}")


def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise Level3PreflightError(f"{label}_public_leak:{needle}")


def load_stage12609() -> dict[str, Any]:
    summary = read_json(S12609 / "summary.json")
    external = read_json(S12609_EXTERNAL)
    contract = read_json(S12609 / "contract.json")
    pointer = read_json(S12609 / "digest_pointer.json")
    private = read_json(S12609 / "private/causal_transition_atom_preflight_blocker.json")
    if summary != external:
        raise Level3PreflightError("stage12609_external_summary_mismatch")
    expected = (
        (stable_hash(summary), EXPECTED_STAGE12609_SUMMARY, "summary"),
        (stable_hash(contract), EXPECTED_STAGE12609_CONTRACT, "contract"),
        (stable_hash(pointer), EXPECTED_STAGE12609_POINTER, "pointer"),
        (stable_hash(private), EXPECTED_STAGE12609_PRIVATE, "private"),
    )
    for actual, expected_hash, label in expected:
        if actual != expected_hash:
            raise Level3PreflightError("stage12609_pin_drift:" + label)
    if summary.get("decision") != "BLOCKED_TRUSTED_REPLAY_EXECUTION_EVIDENCE_REQUIRED_FOR_CAUSAL_ATOMS":
        raise Level3PreflightError("stage12609_decision_drift")
    if summary.get("causal_transition_atom_count") != 0:
        raise Level3PreflightError("stage12609_atom_count_drift")
    if summary.get("stage12610_allowed") is not False:
        raise Level3PreflightError("stage12609_broad_stage12610_drift")
    if summary.get("level3_preflight_allowed") is not False:
        raise Level3PreflightError("stage12609_level3_preflight_drift")
    if private.get("causal_atom_requirement_manifest", {}).get("required_before_any_atom") is None:
        raise Level3PreflightError("stage12609_atom_requirement_manifest_missing")
    for label, record in (("summary", summary), ("contract", contract), ("pointer", pointer), ("private", private)):
        check_false(record, "stage12609_" + label)
    return {"summary": summary, "contract": contract, "pointer": pointer, "private": private}


def level3_requirements() -> dict[str, Any]:
    return {
        "record_type": "stage12610_level3_materialization_requirements_v1",
        "required_before_level3": [
            "trusted_replay_raw_evidence_present",
            "independent_execution_artifact_review_passed",
            "causal_transition_atom_count_positive",
            "causal_transition_atoms_materialized",
            "causally_committed_pre_outcome_candidate_set_present",
            "observed_stop_continue_decision_provenance_present",
            "atom_to_candidate_commitment_join_verified",
            "atom_to_stop_continue_provenance_join_verified",
        ],
        "not_sufficient_for_training": [
            "level3_materialization_alone",
            "replay_success_alone",
            "causal_atoms_without_separate_training_admission",
        ],
        "forbidden_until_requirements_met": [
            "level_3_materialized",
            "training_admitted",
            "strict_eval_admitted",
            "sealed_eval_admitted",
        ],
    }


def build_level3_preflight_packet(stage12609: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    requirements = level3_requirements()
    private = {
        "record_type": "stage12610_private_level3_materialization_preflight_blocker_v1",
        "stage12609_summary_sha256": EXPECTED_STAGE12609_SUMMARY,
        "stage12609_private_atom_preflight_blocker_sha256": EXPECTED_STAGE12609_PRIVATE,
        "gate_scope": EXPECTED_GATE_SCOPE,
        "source_decision": stage12609["summary"]["decision"],
        "causal_transition_atom_count": 0,
        "causal_transition_atoms_present": False,
        "causally_committed_pre_outcome_candidate_set_present": False,
        "observed_stop_continue_decision_provenance_present": False,
        "level3_requirement_manifest": requirements,
        "decision": "BLOCKED_CAUSAL_TRANSITION_ATOMS_AND_PROVENANCE_REQUIRED_FOR_LEVEL3",
        "stage12611_allowed": False,
        "training_admission_preflight_allowed": False,
        **no_claim_fields(),
    }
    contract = {
        "record_type": "stage12610_public_level3_materialization_preflight_contract_v1",
        "stage12609_summary_sha256": EXPECTED_STAGE12609_SUMMARY,
        "stage12609_contract_sha256": EXPECTED_STAGE12609_CONTRACT,
        "stage12609_private_atom_preflight_blocker_sha256": EXPECTED_STAGE12609_PRIVATE,
        "gate_scope": EXPECTED_GATE_SCOPE,
        "causal_transition_atom_count": 0,
        "causal_transition_atoms_present": False,
        "causally_committed_pre_outcome_candidate_set_present": False,
        "observed_stop_continue_decision_provenance_present": False,
        "level3_requirement_manifest_sha256": stable_hash(requirements),
        "private_level3_preflight_blocker_sha256": stable_hash(private),
        "stage12611_allowed": False,
        "training_admission_preflight_allowed": False,
        "claim_boundary": {
            "level3": "forbidden_until_atoms_candidate_commitment_and_stop_continue_provenance_exist",
            "training_admission": "separate_future_gate_required_even_after_level3",
            "strict_eval": "separate_future_gate_required",
            "sealed_eval": "separate_future_gate_required",
        },
        **no_claim_fields(),
    }
    summary = {
        "record_type": "stage12610_public_level3_materialization_preflight_blocker_summary_v1",
        "stage": STAGE,
        "decision": "BLOCKED_CAUSAL_TRANSITION_ATOMS_AND_PROVENANCE_REQUIRED_FOR_LEVEL3",
        "stage12609_summary_sha256": EXPECTED_STAGE12609_SUMMARY,
        "gate_scope": EXPECTED_GATE_SCOPE,
        "causal_transition_atom_count": 0,
        "causal_transition_atoms_present": False,
        "causally_committed_pre_outcome_candidate_set_present": False,
        "observed_stop_continue_decision_provenance_present": False,
        "level3_requirement_manifest_sha256": stable_hash(requirements),
        "private_level3_preflight_blocker_sha256": stable_hash(private),
        "stage12611_allowed": False,
        "training_admission_preflight_allowed": False,
        "downstream_blockers": [
            "causal_transition_atoms_absent",
            "trusted_replay_raw_evidence_absent",
            "independent_execution_artifact_review_absent",
            "causally_committed_pre_outcome_candidate_set_absent",
            "observed_stop_continue_decision_absent",
            "level3_materialization_forbidden",
            "training_admission_forbidden",
            "strict_eval_admission_forbidden",
            "sealed_eval_admission_forbidden",
        ],
        **no_claim_fields(),
    }
    for label, record in (("summary", summary), ("contract", contract)):
        check_false(record, "stage12610_" + label)
        assert_public_sanitized(record, "stage12610_" + label)
    check_false(private, "stage12610_private")
    return summary, contract, private


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    stage12609 = load_stage12609()
    summary, contract, private = build_level3_preflight_packet(stage12609)
    pointer = {
        "record_type": "stage12610_public_private_level3_materialization_preflight_pointer_v1",
        "stage12609_summary_sha256": EXPECTED_STAGE12609_SUMMARY,
        "private_level3_preflight_blocker_sha256": stable_hash(private),
        "contract_sha256": stable_hash(contract),
        "causal_transition_atom_count": 0,
        "causal_transition_atoms_present": False,
        "level_3_materialized": False,
        "level_3_materialization_allowed": False,
        "stage12611_allowed": False,
        "training_admission_preflight_allowed": False,
        **no_claim_fields(),
    }
    check_false(pointer, "stage12610_pointer")
    assert_public_sanitized(pointer, "stage12610_pointer")
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "private/level3_materialization_preflight_blocker.json", private)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
