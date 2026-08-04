#!/usr/bin/env python3
"""Build Stage12608 bwrap-capable execution artifact intake preflight.

Stage12607 prepared a private, reviewed-function-only handoff for a future
bwrap-capable environment. This stage does not run replay. It checks whether
that future private evidence exists and blocks cleanly when it is absent.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12608_bwrap_capable_execution_artifact_intake_preflight"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
S12607 = ROOT / "runs/local/artifacts/stage12607_bwrap_capable_reviewed_function_replay_handoff"
S12607_EXTERNAL = ROOT / "runs/summaries/stage12607_bwrap_capable_reviewed_function_replay_handoff.json"
EXPECTED_STAGE12607_SUMMARY = "066d276462ff5ad607136e7f0273081835bbfcde7fe3658e13d92263aea8eecf"
EXPECTED_STAGE12607_CONTRACT = "9365a2334c2765e50e9ff84a63d233d1a6f275eb2d1c6592dd92c82bd08d69f2"
EXPECTED_STAGE12607_POINTER = "c937b6ffe39f9a9b2c7758dde5041d771e0b60ad924013bd16b176eeccad82a2"
EXPECTED_STAGE12607_PRIVATE = "8de96f407135c8aa8b9b456ee93e261cafbf3f8d608df6e159d6721420bb39df"
EXPECTED_GATE_SCOPE = "reviewed_stage12602_execute_reviewed_slot_function_only"
FALSE_FIELDS = (
    "implementation_ready", "stage12595_allowed", "execution_performed", "replay_trustworthy",
    "level_3_materialized", "training_admitted", "strict_eval_admitted", "sealed_eval_admitted",
    "strict_eval_eligible", "sealed_eval_eligible", "admission_allowed", "training_allowed",
    "ranking_allowed", "positive_stop", "raw_replay_evidence_present",
)
PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "selector", "raw_stream", "stdout.raw", "stderr.raw", "before_commit_oid",
    "after_commit_oid", "production_path", "production_patch_sha256", "manual_executor_slot_contracts",
    "slot_1.patch", "slot_2.patch", "future_evidence", "repository_root", "patch_path", "snapshot",
)
PHASES = ("initial", "patched", "final")


class IntakeError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def stable_hash(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise IntakeError("json_object_required:" + path.name)
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True).encode("ascii") + b"\n"
    with path.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def no_replay_claim_fields() -> dict[str, Any]:
    return {
        "implementation_ready": False,
        "stage12595_allowed": False,
        "execution_performed": False,
        "replay_trustworthy": False,
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
        "raw_replay_evidence_present": False,
    }


def check_false(record: Mapping[str, Any], label: str) -> None:
    for field in FALSE_FIELDS:
        if record.get(field) is not False:
            raise IntakeError(f"{label}_gate_drift:{field}")


def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise IntakeError(f"{label}_public_leak:{needle}")


def load_stage12607() -> dict[str, Any]:
    summary = read_json(S12607 / "summary.json")
    external = read_json(S12607_EXTERNAL)
    contract = read_json(S12607 / "contract.json")
    pointer = read_json(S12607 / "digest_pointer.json")
    private = read_json(S12607 / "private/bwrap_capable_reviewed_function_replay_handoff.json")
    if summary != external:
        raise IntakeError("stage12607_external_summary_mismatch")
    expected = (
        (stable_hash(summary), EXPECTED_STAGE12607_SUMMARY, "summary"),
        (stable_hash(contract), EXPECTED_STAGE12607_CONTRACT, "contract"),
        (stable_hash(pointer), EXPECTED_STAGE12607_POINTER, "pointer"),
        (stable_hash(private), EXPECTED_STAGE12607_PRIVATE, "private"),
    )
    for actual, expected_hash, label in expected:
        if actual != expected_hash:
            raise IntakeError("stage12607_pin_drift:" + label)
    if summary.get("handoff_ready_for_bwrap_capable_environment") is not True:
        raise IntakeError("stage12607_handoff_not_ready")
    if summary.get("execution_handoff_runs_replay") is not False:
        raise IntakeError("stage12607_execution_drift")
    if summary.get("stage12608_allowed") is not False:
        raise IntakeError("stage12607_broad_stage12608_drift")
    if summary.get("stage12608_bwrap_capable_function_execution_review_allowed") is not True:
        raise IntakeError("stage12607_scoped_stage12608_missing")
    if private.get("gate_scope") != EXPECTED_GATE_SCOPE:
        raise IntakeError("stage12607_private_scope_drift")
    if private.get("slot_count") != 2 or len(private.get("private_slot_invocations", [])) != 2:
        raise IntakeError("stage12607_private_slot_count_drift")
    for label, record in (("summary", summary), ("contract", contract), ("pointer", pointer), ("private", private)):
        check_false(record, "stage12607_" + label)
    return {"summary": summary, "contract": contract, "pointer": pointer, "private": private}


def required_relative_evidence(invocation: Mapping[str, Any]) -> list[str]:
    slot = f"slot_{invocation['slot_ordinal']}"
    files = [f"{slot}/reviewed_slot_execution_result.json"]
    for phase in PHASES:
        files.append(f"{slot}/{phase}.stdout.raw")
        files.append(f"{slot}/{phase}.stderr.raw")
    return files


def inspect_future_evidence(private_handoff: Mapping[str, Any]) -> dict[str, Any]:
    invocations = private_handoff.get("private_slot_invocations", [])
    roots = sorted({str(item["future_private_evidence_root"]) for item in invocations})
    if len(roots) != 1:
        raise IntakeError("future_evidence_root_mismatch")
    root = Path(roots[0])
    required = []
    for item in invocations:
        required.extend(required_relative_evidence(item))
    present = []
    missing = []
    for relative in required:
        candidate = root / relative
        if candidate.is_file():
            present.append(relative)
        else:
            missing.append(relative)
    return {
        "future_private_evidence_root": str(root),
        "future_private_evidence_root_exists": root.exists(),
        "required_file_count": len(required),
        "present_file_count": len(present),
        "missing_file_count": len(missing),
        "required_relative_files": required,
        "present_relative_files": present,
        "missing_relative_files": missing,
        "all_required_evidence_present": not missing,
    }


def build_intake_packet(stage12607: Mapping[str, Any], evidence: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if evidence.get("all_required_evidence_present") is True:
        raise IntakeError("unexpected_future_execution_evidence_present")
    private = {
        "record_type": "stage12608_private_bwrap_capable_execution_artifact_intake_blocker_v1",
        "stage12607_summary_sha256": EXPECTED_STAGE12607_SUMMARY,
        "stage12607_private_handoff_sha256": EXPECTED_STAGE12607_PRIVATE,
        "gate_scope": EXPECTED_GATE_SCOPE,
        "reviewed_function_name": "execute_reviewed_slot",
        "intake_performed": True,
        "external_bwrap_capable_execution_artifacts_present": False,
        "required_evidence_schema": {
            "slot_result_manifest": "slot_N/reviewed_slot_execution_result.json",
            "raw_streams": ["slot_N/initial.stdout.raw", "slot_N/initial.stderr.raw", "slot_N/patched.stdout.raw", "slot_N/patched.stderr.raw", "slot_N/final.stdout.raw", "slot_N/final.stderr.raw"],
            "source": "stage12607_private_slot_invocations",
        },
        "future_evidence_inspection": dict(evidence),
        "decision": "BLOCKED_EXTERNAL_BWRAP_CAPABLE_EXECUTION_ARTIFACTS_MISSING",
        "stage12609_allowed": False,
        "causal_transition_atoms_allowed": False,
        **no_replay_claim_fields(),
    }
    contract = {
        "record_type": "stage12608_public_bwrap_capable_execution_artifact_intake_contract_v1",
        "stage12607_summary_sha256": EXPECTED_STAGE12607_SUMMARY,
        "stage12607_contract_sha256": EXPECTED_STAGE12607_CONTRACT,
        "stage12607_private_handoff_sha256": EXPECTED_STAGE12607_PRIVATE,
        "gate_scope": EXPECTED_GATE_SCOPE,
        "reviewed_function_name": "execute_reviewed_slot",
        "intake_performed": True,
        "external_bwrap_capable_execution_artifacts_present": False,
        "required_evidence_slot_count": stage12607["private"]["slot_count"],
        "required_evidence_file_count": evidence["required_file_count"],
        "present_evidence_file_count": evidence["present_file_count"],
        "missing_evidence_file_count": evidence["missing_file_count"],
        "private_intake_blocker_sha256": stable_hash(private),
        "stage12609_allowed": False,
        "causal_transition_atoms_allowed": False,
        "claim_boundary": {
            "raw_replay_evidence": "absent_until_external_bwrap_capable_execution_artifacts_are_present",
            "replay_success_claim": "forbidden",
            "level3_claim": "forbidden_until_independent_execution_review_and_causal_provenance",
            "training_admission": "separate_future_gate_required",
        },
        **no_replay_claim_fields(),
    }
    summary = {
        "record_type": "stage12608_public_bwrap_capable_execution_artifact_intake_preflight_summary_v1",
        "stage": STAGE,
        "decision": "BLOCKED_EXTERNAL_BWRAP_CAPABLE_EXECUTION_ARTIFACTS_MISSING",
        "stage12607_summary_sha256": EXPECTED_STAGE12607_SUMMARY,
        "gate_scope": EXPECTED_GATE_SCOPE,
        "reviewed_function_name": "execute_reviewed_slot",
        "intake_performed": True,
        "external_bwrap_capable_execution_artifacts_present": False,
        "required_evidence_slot_count": stage12607["private"]["slot_count"],
        "required_evidence_file_count": evidence["required_file_count"],
        "present_evidence_file_count": evidence["present_file_count"],
        "missing_evidence_file_count": evidence["missing_file_count"],
        "private_intake_blocker_sha256": stable_hash(private),
        "stage12609_allowed": False,
        "causal_transition_atoms_allowed": False,
        "downstream_blockers": [
            "external_bwrap_capable_execution_artifacts_missing",
            "reviewed_function_replay_not_executed_on_trusted_capable_host",
            "trusted_replay_raw_evidence_absent",
            "independent_execution_artifact_review_absent",
            "causally_committed_pre_outcome_candidate_set_absent",
            "observed_stop_continue_decision_absent",
            "level3_materialization_forbidden",
            "training_admission_forbidden",
            "strict_eval_admission_forbidden",
            "sealed_eval_admission_forbidden",
        ],
        **no_replay_claim_fields(),
    }
    for label, record in (("summary", summary), ("contract", contract)):
        check_false(record, "stage12608_" + label)
        assert_public_sanitized(record, "stage12608_" + label)
    check_false(private, "stage12608_private")
    return summary, contract, private


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    stage12607 = load_stage12607()
    evidence = inspect_future_evidence(stage12607["private"])
    summary, contract, private = build_intake_packet(stage12607, evidence)
    pointer = {
        "record_type": "stage12608_public_private_bwrap_capable_execution_artifact_intake_pointer_v1",
        "stage12607_summary_sha256": EXPECTED_STAGE12607_SUMMARY,
        "private_intake_blocker_sha256": stable_hash(private),
        "contract_sha256": stable_hash(contract),
        "intake_performed": True,
        "external_bwrap_capable_execution_artifacts_present": False,
        "required_evidence_file_count": evidence["required_file_count"],
        "present_evidence_file_count": evidence["present_file_count"],
        "missing_evidence_file_count": evidence["missing_file_count"],
        "stage12609_allowed": False,
        "causal_transition_atoms_allowed": False,
        "execution_performed": False,
        "raw_replay_evidence_present": False,
        "replay_trustworthy": False,
        "level_3_materialized": False,
        "training_admitted": False,
        "strict_eval_admitted": False,
        "sealed_eval_admitted": False,
        **no_replay_claim_fields(),
    }
    check_false(pointer, "stage12608_pointer")
    assert_public_sanitized(pointer, "stage12608_pointer")
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "private/execution_artifact_intake_blocker.json", private)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
