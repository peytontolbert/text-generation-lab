#!/usr/bin/env python3
"""Build Stage12612 trusted replay resumption gate blocker.

The spine has reached explicit blockers for replay, causal atoms, Level-3, and
separate training admission. This stage records the exact resumption conditions
for returning to trusted replay execution, while keeping every downstream gate
closed until external bwrap-capable raw execution evidence exists.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12612_trusted_replay_resumption_gate_blocker"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
S12611 = ROOT / "runs/local/artifacts/stage12611_separate_training_admission_preflight_blocker"
S12611_EXTERNAL = ROOT / "runs/summaries/stage12611_separate_training_admission_preflight_blocker.json"
FUTURE_EVIDENCE_ROOT = ROOT / "runs/local/private/stage12608_bwrap_capable_reviewed_function_replay_execution"
EXPECTED_STAGE12611_SUMMARY = "20f3644b36a2420b65c7b17ab493626ec93dbf97b12151373f108c348a0a2681"
EXPECTED_STAGE12611_CONTRACT = "32a8701870899591d01715d5a5165bab456ae31c02911b03cc9954449a4a4815"
EXPECTED_STAGE12611_POINTER = "44661eb810082195cbd53c8a034a631bd7aabc148ccc0b66a675aa50975b8479"
EXPECTED_STAGE12611_PRIVATE = "65c7970060850add119accc60826b17066154754690a7fc6142f64857ff46591"
EXPECTED_GATE_SCOPE = "reviewed_stage12602_execute_reviewed_slot_function_only"
FALSE_FIELDS = (
    "implementation_ready", "stage12595_allowed", "execution_performed", "replay_trustworthy",
    "raw_replay_evidence_present", "trusted_replay_raw_evidence_present", "causal_transition_atoms_present",
    "causal_transition_atoms_materialized", "causal_transition_atoms_allowed",
    "causally_committed_pre_outcome_candidate_set_present", "observed_stop_continue_decision_provenance_present",
    "level3_preflight_allowed", "level_3_materialized", "level_3_materialization_allowed",
    "training_admission_preflight_allowed", "training_admission_allowed", "training_admitted",
    "training_allowed", "training_run_allowed", "gpu_allocation_requested", "cuda2_training_allowed",
    "strict_eval_admitted", "sealed_eval_admitted", "strict_eval_eligible", "sealed_eval_eligible",
    "admission_allowed", "ranking_allowed", "positive_stop", "stage12613_allowed",
)
PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "selector", "raw_stream", "stdout.raw", "stderr.raw", "before_commit_oid",
    "after_commit_oid", "production_path", "production_patch_sha256", "manual_executor_slot_contracts",
    "slot_1.patch", "slot_2.patch", "future_evidence", "repository_root", "patch_path", "snapshot",
)
PHASES = ("initial", "patched", "final")


class ResumptionGateError(RuntimeError):
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
        raise ResumptionGateError("json_object_required:" + path.name)
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
        "trusted_replay_raw_evidence_present": False,
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
        "stage12613_allowed": False,
    }


def check_false(record: Mapping[str, Any], label: str) -> None:
    for field in FALSE_FIELDS:
        if field in record and record[field] is not False:
            raise ResumptionGateError(f"{label}_gate_drift:{field}")


def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise ResumptionGateError(f"{label}_public_leak:{needle}")


def load_stage12611() -> dict[str, Any]:
    summary = read_json(S12611 / "summary.json")
    external = read_json(S12611_EXTERNAL)
    contract = read_json(S12611 / "contract.json")
    pointer = read_json(S12611 / "digest_pointer.json")
    private = read_json(S12611 / "private/separate_training_admission_preflight_blocker.json")
    if summary != external:
        raise ResumptionGateError("stage12611_external_summary_mismatch")
    expected = (
        (stable_hash(summary), EXPECTED_STAGE12611_SUMMARY, "summary"),
        (stable_hash(contract), EXPECTED_STAGE12611_CONTRACT, "contract"),
        (stable_hash(pointer), EXPECTED_STAGE12611_POINTER, "pointer"),
        (stable_hash(private), EXPECTED_STAGE12611_PRIVATE, "private"),
    )
    for actual, expected_hash, label in expected:
        if actual != expected_hash:
            raise ResumptionGateError("stage12611_pin_drift:" + label)
    if summary.get("decision") != "BLOCKED_SEPARATE_TRAINING_ADMISSION_REQUIREMENTS_UNMET":
        raise ResumptionGateError("stage12611_decision_drift")
    if summary.get("stage12612_allowed") is not False:
        raise ResumptionGateError("stage12611_broad_stage12612_drift")
    if summary.get("training_admission_allowed") is not False:
        raise ResumptionGateError("stage12611_training_allowed_drift")
    if summary.get("separate_training_admission_required") is not True:
        raise ResumptionGateError("stage12611_separate_training_boundary_missing")
    for label, record in (("summary", summary), ("contract", contract), ("pointer", pointer), ("private", private)):
        check_false(record, "stage12611_" + label)
    return {"summary": summary, "contract": contract, "pointer": pointer, "private": private}


def resumption_requirements() -> dict[str, Any]:
    required_files = []
    for slot in (1, 2):
        required_files.append(f"slot_{slot}/reviewed_slot_execution_result.json")
        for phase in PHASES:
            required_files.append(f"slot_{slot}/{phase}.stdout.raw")
            required_files.append(f"slot_{slot}/{phase}.stderr.raw")
    return {
        "record_type": "stage12612_trusted_replay_resumption_requirements_v1",
        "required_external_evidence_file_count": len(required_files),
        "required_external_evidence_relative_files": required_files,
        "required_after_evidence_arrives": [
            "verify_stage12607_private_handoff_pin",
            "verify_stage12608_required_evidence_file_set_complete",
            "independent_execution_artifact_review",
            "derive_causal_transition_atoms_only_after_review_passes",
            "join_atoms_to_pre_outcome_candidate_commitment",
            "join_atoms_to_observed_stop_continue_provenance",
            "run_level3_materialization_gate",
            "run_separate_training_admission_gate",
        ],
        "still_forbidden_at_resumption_gate": [
            "direct_training_admission",
            "direct_level3_materialization",
            "direct_causal_atom_materialization_without_review",
            "strict_eval_admission",
            "sealed_eval_admission",
            "gpu_allocation",
        ],
    }


def inspect_external_evidence_root() -> dict[str, Any]:
    requirements = resumption_requirements()
    present = []
    missing = []
    for relative in requirements["required_external_evidence_relative_files"]:
        if (FUTURE_EVIDENCE_ROOT / relative).is_file():
            present.append(relative)
        else:
            missing.append(relative)
    return {
        "future_private_evidence_root": str(FUTURE_EVIDENCE_ROOT),
        "future_private_evidence_root_exists": FUTURE_EVIDENCE_ROOT.exists(),
        "required_external_evidence_file_count": requirements["required_external_evidence_file_count"],
        "present_external_evidence_file_count": len(present),
        "missing_external_evidence_file_count": len(missing),
        "present_relative_files": present,
        "missing_relative_files": missing,
        "external_evidence_complete": not missing,
    }


def build_resumption_gate_packet(stage12611: Mapping[str, Any], evidence: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    requirements = resumption_requirements()
    if evidence.get("external_evidence_complete") is True:
        raise ResumptionGateError("unexpected_complete_external_replay_evidence_present")
    private = {
        "record_type": "stage12612_private_trusted_replay_resumption_gate_blocker_v1",
        "stage12611_summary_sha256": EXPECTED_STAGE12611_SUMMARY,
        "stage12611_private_training_preflight_blocker_sha256": EXPECTED_STAGE12611_PRIVATE,
        "gate_scope": EXPECTED_GATE_SCOPE,
        "source_decision": stage12611["summary"]["decision"],
        "trusted_replay_resumption_gate_recorded": True,
        "external_bwrap_execution_required": True,
        "external_bwrap_execution_evidence_present": False,
        "resumption_requirement_manifest": requirements,
        "external_evidence_inspection": dict(evidence),
        "decision": "BLOCKED_TRUSTED_REPLAY_RESUMPTION_REQUIRES_EXTERNAL_BWRAP_EVIDENCE",
        **no_claim_fields(),
    }
    contract = {
        "record_type": "stage12612_public_trusted_replay_resumption_gate_contract_v1",
        "stage12611_summary_sha256": EXPECTED_STAGE12611_SUMMARY,
        "stage12611_contract_sha256": EXPECTED_STAGE12611_CONTRACT,
        "stage12611_private_training_preflight_blocker_sha256": EXPECTED_STAGE12611_PRIVATE,
        "gate_scope": EXPECTED_GATE_SCOPE,
        "trusted_replay_resumption_gate_recorded": True,
        "external_bwrap_execution_required": True,
        "external_bwrap_execution_evidence_present": False,
        "required_external_evidence_file_count": evidence["required_external_evidence_file_count"],
        "present_external_evidence_file_count": evidence["present_external_evidence_file_count"],
        "missing_external_evidence_file_count": evidence["missing_external_evidence_file_count"],
        "resumption_requirement_manifest_sha256": stable_hash(requirements),
        "private_resumption_gate_blocker_sha256": stable_hash(private),
        "claim_boundary": {
            "replay_execution": "requires_external_bwrap_capable_evidence_before_any_success_claim",
            "causal_atoms": "forbidden_until_independent_execution_review_passes",
            "level3": "forbidden_until_atoms_candidate_commitment_and_stop_continue_provenance_exist",
            "training_admission": "separate_future_gate_required",
        },
        **no_claim_fields(),
    }
    summary = {
        "record_type": "stage12612_public_trusted_replay_resumption_gate_blocker_summary_v1",
        "stage": STAGE,
        "decision": "BLOCKED_TRUSTED_REPLAY_RESUMPTION_REQUIRES_EXTERNAL_BWRAP_EVIDENCE",
        "stage12611_summary_sha256": EXPECTED_STAGE12611_SUMMARY,
        "gate_scope": EXPECTED_GATE_SCOPE,
        "trusted_replay_resumption_gate_recorded": True,
        "external_bwrap_execution_required": True,
        "external_bwrap_execution_evidence_present": False,
        "required_external_evidence_file_count": evidence["required_external_evidence_file_count"],
        "present_external_evidence_file_count": evidence["present_external_evidence_file_count"],
        "missing_external_evidence_file_count": evidence["missing_external_evidence_file_count"],
        "resumption_requirement_manifest_sha256": stable_hash(requirements),
        "private_resumption_gate_blocker_sha256": stable_hash(private),
        "downstream_blockers": [
            "external_bwrap_capable_execution_evidence_missing",
            "trusted_replay_raw_evidence_absent",
            "independent_execution_artifact_review_absent",
            "causal_transition_atoms_absent",
            "level3_materialization_forbidden",
            "separate_training_admission_gate_absent",
            "training_admission_forbidden",
            "strict_eval_admission_forbidden",
            "sealed_eval_admission_forbidden",
        ],
        **no_claim_fields(),
    }
    for label, record in (("summary", summary), ("contract", contract)):
        check_false(record, "stage12612_" + label)
        assert_public_sanitized(record, "stage12612_" + label)
    check_false(private, "stage12612_private")
    return summary, contract, private


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    stage12611 = load_stage12611()
    evidence = inspect_external_evidence_root()
    summary, contract, private = build_resumption_gate_packet(stage12611, evidence)
    pointer = {
        "record_type": "stage12612_public_private_trusted_replay_resumption_gate_pointer_v1",
        "stage12611_summary_sha256": EXPECTED_STAGE12611_SUMMARY,
        "private_resumption_gate_blocker_sha256": stable_hash(private),
        "contract_sha256": stable_hash(contract),
        "trusted_replay_resumption_gate_recorded": True,
        "external_bwrap_execution_required": True,
        "external_bwrap_execution_evidence_present": False,
        "required_external_evidence_file_count": evidence["required_external_evidence_file_count"],
        "present_external_evidence_file_count": evidence["present_external_evidence_file_count"],
        "missing_external_evidence_file_count": evidence["missing_external_evidence_file_count"],
        **no_claim_fields(),
    }
    check_false(pointer, "stage12612_pointer")
    assert_public_sanitized(pointer, "stage12612_pointer")
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "private/trusted_replay_resumption_gate_blocker.json", private)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
