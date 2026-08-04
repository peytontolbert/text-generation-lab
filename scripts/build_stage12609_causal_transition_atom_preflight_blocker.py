#!/usr/bin/env python3
"""Build Stage12609 causal transition atom preflight blocker.

Trusted replay evidence is still absent after Stage12608. This stage records the
requirements for causal transition atoms and blocks atom materialization until
independently reviewed replay execution artifacts exist.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12609_causal_transition_atom_preflight_blocker"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
S12608 = ROOT / "runs/local/artifacts/stage12608_bwrap_capable_execution_artifact_intake_preflight"
S12608_EXTERNAL = ROOT / "runs/summaries/stage12608_bwrap_capable_execution_artifact_intake_preflight.json"
EXPECTED_STAGE12608_SUMMARY = "2b96a3fce896b31efb1b5aabd5fe4b2b95d0878a8bb375a46411c2f9dd38a9b6"
EXPECTED_STAGE12608_CONTRACT = "e9448b0bb90a3f45e8ebd754c4d6679407b2906a97525eccc1a112a5978dd714"
EXPECTED_STAGE12608_POINTER = "0793273d65cb0cf0b364a27f19387f9c7db1c46a8fcd0b988c6cf78859a8d59e"
EXPECTED_STAGE12608_PRIVATE = "29e142384096a058e94e283af6e7f337d29a0b2933dce12f1759c8868d0bada0"
EXPECTED_GATE_SCOPE = "reviewed_stage12602_execute_reviewed_slot_function_only"
FALSE_FIELDS = (
    "implementation_ready", "stage12595_allowed", "execution_performed", "replay_trustworthy",
    "raw_replay_evidence_present", "causal_transition_atoms_materialized", "causal_transition_atoms_allowed",
    "level_3_materialized", "training_admitted", "strict_eval_admitted", "sealed_eval_admitted",
    "strict_eval_eligible", "sealed_eval_eligible", "admission_allowed", "training_allowed",
    "ranking_allowed", "positive_stop",
)
PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "selector", "raw_stream", "stdout.raw", "stderr.raw", "before_commit_oid",
    "after_commit_oid", "production_path", "production_patch_sha256", "manual_executor_slot_contracts",
    "slot_1.patch", "slot_2.patch", "future_evidence", "repository_root", "patch_path", "snapshot",
)


class AtomPreflightError(RuntimeError):
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
        raise AtomPreflightError("json_object_required:" + path.name)
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
        "level_3_materialized": False,
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
            raise AtomPreflightError(f"{label}_gate_drift:{field}")


def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise AtomPreflightError(f"{label}_public_leak:{needle}")


def load_stage12608() -> dict[str, Any]:
    summary = read_json(S12608 / "summary.json")
    external = read_json(S12608_EXTERNAL)
    contract = read_json(S12608 / "contract.json")
    pointer = read_json(S12608 / "digest_pointer.json")
    private = read_json(S12608 / "private/execution_artifact_intake_blocker.json")
    if summary != external:
        raise AtomPreflightError("stage12608_external_summary_mismatch")
    expected = (
        (stable_hash(summary), EXPECTED_STAGE12608_SUMMARY, "summary"),
        (stable_hash(contract), EXPECTED_STAGE12608_CONTRACT, "contract"),
        (stable_hash(pointer), EXPECTED_STAGE12608_POINTER, "pointer"),
        (stable_hash(private), EXPECTED_STAGE12608_PRIVATE, "private"),
    )
    for actual, expected_hash, label in expected:
        if actual != expected_hash:
            raise AtomPreflightError("stage12608_pin_drift:" + label)
    if summary.get("decision") != "BLOCKED_EXTERNAL_BWRAP_CAPABLE_EXECUTION_ARTIFACTS_MISSING":
        raise AtomPreflightError("stage12608_decision_drift")
    if summary.get("external_bwrap_capable_execution_artifacts_present") is not False:
        raise AtomPreflightError("stage12608_external_artifact_drift")
    if summary.get("stage12609_allowed") is not False:
        raise AtomPreflightError("stage12608_broad_stage12609_drift")
    if summary.get("causal_transition_atoms_allowed") is not False:
        raise AtomPreflightError("stage12608_atom_allowed_drift")
    if private.get("future_evidence_inspection", {}).get("all_required_evidence_present") is not False:
        raise AtomPreflightError("stage12608_future_evidence_drift")
    for label, record in (("summary", summary), ("contract", contract), ("pointer", pointer), ("private", private)):
        check_false(record, "stage12608_" + label)
    return {"summary": summary, "contract": contract, "pointer": pointer, "private": private}


def atom_requirements() -> dict[str, Any]:
    return {
        "record_type": "stage12609_causal_transition_atom_requirements_v1",
        "required_before_any_atom": [
            "all_stage12608_required_external_execution_artifacts_present",
            "per_slot_reviewed_slot_execution_result_json_present",
            "per_phase_raw_stdout_stderr_streams_present",
            "initial_patched_final_phase_reports_complete",
            "patched_phase_demonstrates_expected_behavioral_change",
            "final_phase_reverts_to_initial_failure_fingerprint",
            "filesystem_digest_reverts_to_initial",
            "independent_execution_artifact_review_passed",
            "causally_committed_pre_outcome_candidate_set_present",
            "observed_stop_continue_decision_provenance_present",
        ],
        "forbidden_until_requirements_met": [
            "causal_transition_atoms_materialized",
            "level_3_materialized",
            "training_admitted",
            "strict_eval_admitted",
            "sealed_eval_admitted",
        ],
    }


def build_atom_preflight_packet(stage12608: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    requirements = atom_requirements()
    private = {
        "record_type": "stage12609_private_causal_transition_atom_preflight_blocker_v1",
        "stage12608_summary_sha256": EXPECTED_STAGE12608_SUMMARY,
        "stage12608_private_intake_blocker_sha256": EXPECTED_STAGE12608_PRIVATE,
        "gate_scope": EXPECTED_GATE_SCOPE,
        "source_decision": stage12608["summary"]["decision"],
        "source_external_execution_artifacts_present": False,
        "source_required_evidence_file_count": stage12608["summary"]["required_evidence_file_count"],
        "source_present_evidence_file_count": stage12608["summary"]["present_evidence_file_count"],
        "source_missing_evidence_file_count": stage12608["summary"]["missing_evidence_file_count"],
        "causal_atom_requirement_manifest": requirements,
        "causal_transition_atom_count": 0,
        "decision": "BLOCKED_TRUSTED_REPLAY_EXECUTION_EVIDENCE_REQUIRED_FOR_CAUSAL_ATOMS",
        "stage12610_allowed": False,
        "level3_preflight_allowed": False,
        **no_claim_fields(),
    }
    contract = {
        "record_type": "stage12609_public_causal_transition_atom_preflight_contract_v1",
        "stage12608_summary_sha256": EXPECTED_STAGE12608_SUMMARY,
        "stage12608_contract_sha256": EXPECTED_STAGE12608_CONTRACT,
        "stage12608_private_intake_blocker_sha256": EXPECTED_STAGE12608_PRIVATE,
        "gate_scope": EXPECTED_GATE_SCOPE,
        "source_external_execution_artifacts_present": False,
        "causal_atom_requirement_manifest_sha256": stable_hash(requirements),
        "causal_transition_atom_count": 0,
        "private_atom_preflight_blocker_sha256": stable_hash(private),
        "stage12610_allowed": False,
        "level3_preflight_allowed": False,
        "claim_boundary": {
            "causal_atoms": "forbidden_until_trusted_replay_execution_evidence_and_independent_review_exist",
            "level3": "forbidden_until_causal_atoms_plus_pre_outcome_candidate_and_stop_continue_provenance",
            "training_admission": "separate_future_gate_required",
        },
        **no_claim_fields(),
    }
    summary = {
        "record_type": "stage12609_public_causal_transition_atom_preflight_blocker_summary_v1",
        "stage": STAGE,
        "decision": "BLOCKED_TRUSTED_REPLAY_EXECUTION_EVIDENCE_REQUIRED_FOR_CAUSAL_ATOMS",
        "stage12608_summary_sha256": EXPECTED_STAGE12608_SUMMARY,
        "gate_scope": EXPECTED_GATE_SCOPE,
        "source_external_execution_artifacts_present": False,
        "source_present_evidence_file_count": stage12608["summary"]["present_evidence_file_count"],
        "source_missing_evidence_file_count": stage12608["summary"]["missing_evidence_file_count"],
        "causal_atom_requirement_manifest_sha256": stable_hash(requirements),
        "causal_transition_atom_count": 0,
        "private_atom_preflight_blocker_sha256": stable_hash(private),
        "stage12610_allowed": False,
        "level3_preflight_allowed": False,
        "downstream_blockers": [
            "trusted_replay_raw_evidence_absent",
            "independent_execution_artifact_review_absent",
            "causal_transition_atoms_forbidden",
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
        check_false(record, "stage12609_" + label)
        assert_public_sanitized(record, "stage12609_" + label)
    check_false(private, "stage12609_private")
    return summary, contract, private


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    stage12608 = load_stage12608()
    summary, contract, private = build_atom_preflight_packet(stage12608)
    pointer = {
        "record_type": "stage12609_public_private_causal_transition_atom_preflight_pointer_v1",
        "stage12608_summary_sha256": EXPECTED_STAGE12608_SUMMARY,
        "private_atom_preflight_blocker_sha256": stable_hash(private),
        "contract_sha256": stable_hash(contract),
        "source_external_execution_artifacts_present": False,
        "causal_transition_atom_count": 0,
        "stage12610_allowed": False,
        "level3_preflight_allowed": False,
        **no_claim_fields(),
    }
    check_false(pointer, "stage12609_pointer")
    assert_public_sanitized(pointer, "stage12609_pointer")
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "private/causal_transition_atom_preflight_blocker.json", private)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
