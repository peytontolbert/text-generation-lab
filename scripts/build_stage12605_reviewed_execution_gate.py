#!/usr/bin/env python3
"""Build Stage12605 reviewed execution gate.

This stage grants a narrow execution gate for the reviewed Stage12602 function
path using Stage12604's private request materials. It does not invoke replay,
does not enable the runner CLI --execute, does not emit raw replay evidence,
does not materialize Level-3, and does not admit training/eval.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12605_reviewed_execution_gate"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
S12604 = ROOT / "runs/local/artifacts/stage12604_reviewed_execution_request_materials"
S12604_EXTERNAL = ROOT / "runs/summaries/stage12604_reviewed_execution_request_materials.json"
EXPECTED_STAGE12602_RUNNER = "d1ded97530116a515fdf41db5fd5ab42ff725a14ef570c6d6de18ef93c286e19"
EXPECTED_STAGE12604_SUMMARY = "2a6d3cd5c7fc46319c121082ed24a6ca849a5e08a86e1dbca49248ee3331b2b6"
EXPECTED_STAGE12604_CONTRACT = "de9b696c54d846df25338416aab0498a8334b83b055d408951e85d32c0d5b9ba"
EXPECTED_STAGE12604_POINTER = "9442968614acdefa872bdcc683105415e2399f120baf25f364f3e2a6cf4492ed"
EXPECTED_STAGE12604_PRIVATE_REQUEST = "d2429452c290b517a5858892032fded88fd964e3057e98fc8c64280083081b99"
EXPECTED_STAGE12604_COMMAND_MANIFEST = "92abb4b6f1d6d922c3dd90a93a96cde696e121cfc730f47cec170000404e6911"
EXPECTED_STAGE12604_PATCH_RECORDS_FILE = "294f9c07bf4167b5b73b1e9322e664015620708b9b286903e379f91f38977d02"
EXPECTED_STAGE12604_PATCH_RECORDS = "2fb23cc0d8d87b6875b980cea3822f5f006c8e216dcc459f35b0acbc97b9c9a6"
EXPECTED_SLOT_PATCHES = {
    "slot_1.patch": "59dafa5032f5faf18ed603d96718ab6e1538f9021ba487fe20ac32650400f0dc",
    "slot_2.patch": "dce96a116a9d07f4076c175ce7d2a68a95c5b2cd0f43d03daa23581a12d95029",
}
FALSE_FIELDS = (
    "implementation_ready", "stage12595_allowed", "execution_performed", "replay_trustworthy",
    "level_3_materialized", "training_admitted", "strict_eval_admitted", "sealed_eval_admitted",
    "strict_eval_eligible", "sealed_eval_eligible", "admission_allowed", "training_allowed",
    "ranking_allowed", "positive_stop",
)
PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "selector", "raw_stream", "stdout.raw", "stderr.raw", "before_commit_oid",
    "after_commit_oid", "production_path", "production_patch_sha256", "manual_executor_slot_contracts",
    "slot_1.patch", "slot_2.patch",
)


class GateError(RuntimeError):
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
        raise GateError("json_object_required:" + path.name)
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
    }


def check_false(record: Mapping[str, Any], label: str) -> None:
    for field in FALSE_FIELDS:
        if field in record and record[field] is not False:
            raise GateError(f"{label}_gate_drift:{field}")


def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise GateError(f"{label}_public_leak:{needle}")


def load_stage12604() -> dict[str, Any]:
    summary = read_json(S12604 / "summary.json")
    external = read_json(S12604_EXTERNAL)
    contract = read_json(S12604 / "contract.json")
    pointer = read_json(S12604 / "digest_pointer.json")
    private_request = read_json(S12604 / "private/reviewed_execution_request_materials.json")
    command_manifest = read_json(S12604 / "private/executor_command_manifest.json")
    patch_records_file = read_json(S12604 / "private/patch_material_records.json")
    if summary != external:
        raise GateError("stage12604_external_summary_mismatch")
    expected = (
        (stable_hash(summary), EXPECTED_STAGE12604_SUMMARY, "summary"),
        (stable_hash(contract), EXPECTED_STAGE12604_CONTRACT, "contract"),
        (stable_hash(pointer), EXPECTED_STAGE12604_POINTER, "pointer"),
        (stable_hash(private_request), EXPECTED_STAGE12604_PRIVATE_REQUEST, "private_request"),
        (stable_hash(command_manifest), EXPECTED_STAGE12604_COMMAND_MANIFEST, "command_manifest"),
        (stable_hash(patch_records_file), EXPECTED_STAGE12604_PATCH_RECORDS_FILE, "patch_records_file"),
        (stable_hash(patch_records_file["records"]), EXPECTED_STAGE12604_PATCH_RECORDS, "patch_records"),
    )
    for actual, expected_hash, label in expected:
        if actual != expected_hash:
            raise GateError("stage12604_pin_drift:" + label)
    for patch_name, expected_hash in EXPECTED_SLOT_PATCHES.items():
        if sha256_file(S12604 / "private/patches" / patch_name) != expected_hash:
            raise GateError("stage12604_patch_file_pin_drift:" + patch_name)
    if summary.get("decision") != "BLOCKED_EXECUTION_GATE_GRANT_REQUIRED":
        raise GateError("stage12604_decision_drift")
    if summary.get("execution_request_materials_present") is not True:
        raise GateError("stage12604_materials_missing")
    if summary.get("executor_command_manifest_present") is not True:
        raise GateError("stage12604_command_manifest_missing")
    if summary.get("execution_request_ready_count") != 2 or private_request.get("execution_request_ready_count") != 2:
        raise GateError("stage12604_request_count_drift")
    if summary.get("execution_gate_granted") is not False or private_request.get("execution_gate_granted") is not False:
        raise GateError("stage12604_gate_already_granted")
    if summary.get("execute_path_enabled") is not False or private_request.get("execute_path_enabled") is not False:
        raise GateError("stage12604_execute_path_drift")
    if summary.get("execution_performed") is not False or summary.get("raw_replay_evidence_present") is not False:
        raise GateError("stage12604_execution_drift")
    for label, record in (("summary", summary), ("contract", contract), ("pointer", pointer),
                          ("private_request", private_request), ("patch_records", patch_records_file)):
        check_false(record, "stage12604_" + label)
    return {
        "summary": summary,
        "contract": contract,
        "pointer": pointer,
        "private_request": private_request,
        "command_manifest": command_manifest,
        "patch_records_file": patch_records_file,
    }


def build_gate_packet(stage12604: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    private_gate = {
        "record_type": "stage12605_private_reviewed_execution_gate_v1",
        "stage12602_runner_sha256": EXPECTED_STAGE12602_RUNNER,
        "stage12604_summary_sha256": EXPECTED_STAGE12604_SUMMARY,
        "private_reviewed_execution_request_materials_sha256": EXPECTED_STAGE12604_PRIVATE_REQUEST,
        "private_executor_command_manifest_sha256": EXPECTED_STAGE12604_COMMAND_MANIFEST,
        "private_patch_material_records_sha256": EXPECTED_STAGE12604_PATCH_RECORDS,
        "reviewed_execution_capable_source_present": True,
        "independent_execution_capable_source_review_present": True,
        "independent_execution_capable_source_review_passed": True,
        "execution_request_materials_present": True,
        "execution_request_ready_count": 2,
        "executor_command_manifest_present": True,
        "execution_gate_granted": True,
        "authorizes_execution": True,
        "execution_allowed": True,
        "reviewed_function_execute_path_enabled": True,
        "cli_execute_entrypoint_enabled": False,
        "manual_invocation_required": True,
        "gate_scope": "reviewed_stage12602_execute_reviewed_slot_function_only",
        "this_stage_runs_replay": False,
        "raw_replay_evidence_present": False,
        **no_replay_claim_fields(),
    }
    public_contract = {
        "record_type": "stage12605_public_reviewed_execution_gate_contract_v1",
        "stage12602_runner_sha256": EXPECTED_STAGE12602_RUNNER,
        "stage12604_summary_sha256": EXPECTED_STAGE12604_SUMMARY,
        "reviewed_execution_capable_source_present": True,
        "independent_execution_capable_source_review_present": True,
        "independent_execution_capable_source_review_passed": True,
        "execution_request_materials_present": True,
        "execution_request_ready_count": 2,
        "executor_command_manifest_present": True,
        "execution_gate_granted": True,
        "authorizes_execution": True,
        "execution_allowed": True,
        "reviewed_function_execute_path_enabled": True,
        "cli_execute_entrypoint_enabled": False,
        "manual_invocation_required": True,
        "gate_scope": "reviewed_stage12602_execute_reviewed_slot_function_only",
        "review_gate_scope": {
            "gate_scope": "reviewed_function_path_only",
            "cli_execute": "still_disabled",
            "replay_success_claim": "forbidden_until_manual_executor_raw_artifacts_exist",
            "level3_claim": "forbidden_until_causal_candidate_and_stop_continue_provenance_exist",
            "training_admission": "separate_future_gate_required",
        },
        "this_stage_runs_replay": False,
        "raw_replay_evidence_present": False,
        "claim_boundary": {
            "gate_scope": "reviewed_function_path_only",
            "cli_execute": "still_disabled",
            "replay_success_claim": "forbidden_until_manual_executor_raw_artifacts_exist",
            "level3_claim": "forbidden_until_causal_candidate_and_stop_continue_provenance_exist",
            "training_admission": "separate_future_gate_required",
        },
        **no_replay_claim_fields(),
    }
    summary = {
        "record_type": "stage12605_public_reviewed_execution_gate_summary_v1",
        "stage": STAGE,
        "decision": "EXECUTION_GATE_GRANTED_REPLAY_NOT_RUN",
        "stage12602_runner_sha256": EXPECTED_STAGE12602_RUNNER,
        "stage12604_summary_sha256": EXPECTED_STAGE12604_SUMMARY,
        "reviewed_execution_capable_source_present": True,
        "independent_execution_capable_source_review_present": True,
        "independent_execution_capable_source_review_passed": True,
        "execution_request_materials_present": True,
        "execution_request_ready_count": 2,
        "executor_command_manifest_present": True,
        "execution_gate_granted": True,
        "authorizes_execution": True,
        "execution_allowed": True,
        "reviewed_function_execute_path_enabled": True,
        "cli_execute_entrypoint_enabled": False,
        "manual_invocation_required": True,
        "gate_scope": "reviewed_stage12602_execute_reviewed_slot_function_only",
        "claim_boundary": {
            "gate_scope": "reviewed_function_path_only",
            "cli_execute": "still_disabled",
            "replay_success_claim": "forbidden_until_manual_executor_raw_artifacts_exist",
            "level3_claim": "forbidden_until_causal_candidate_and_stop_continue_provenance_exist",
            "training_admission": "separate_future_gate_required",
        },
        "this_stage_runs_replay": False,
        "execution_performed": False,
        "raw_replay_evidence_present": False,
        "replay_trustworthy": False,
        "stage12606_allowed": False,
        "stage12606_reviewed_function_replay_allowed": True,
        "level3_atom_count": 0,
        "downstream_blockers": [
            "manual_replay_execution_not_performed",
            "trusted_replay_raw_evidence_absent",
            "causally_committed_pre_outcome_candidate_set_absent_even_after_future_replay",
            "observed_stop_continue_decision_absent_even_after_future_replay",
            "level3_materialization_forbidden",
            "training_admission_forbidden",
            "strict_eval_admission_forbidden",
            "sealed_eval_admission_forbidden",
        ],
        **no_replay_claim_fields(),
    }
    for label, record in (("summary", summary), ("contract", public_contract)):
        check_false(record, "stage12605_" + label)
        assert_public_sanitized(record, "stage12605_" + label)
    check_false(private_gate, "stage12605_private_gate")
    return summary, public_contract, private_gate


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    stage12604 = load_stage12604()
    summary, public_contract, private_gate = build_gate_packet(stage12604)
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "contract.json", public_contract)
    write_json(out / "private/reviewed_execution_gate.json", private_gate)
    pointer = {
        "record_type": "stage12605_public_private_execution_gate_pointer_v1",
        "stage12602_runner_sha256": EXPECTED_STAGE12602_RUNNER,
        "stage12604_summary_sha256": EXPECTED_STAGE12604_SUMMARY,
        "private_reviewed_execution_gate_sha256": stable_hash(private_gate),
        "execution_gate_granted": True,
        "authorizes_execution": True,
        "execution_allowed": True,
        "reviewed_function_execute_path_enabled": True,
        "cli_execute_entrypoint_enabled": False,
        "manual_invocation_required": True,
        "gate_scope": "reviewed_stage12602_execute_reviewed_slot_function_only",
        "stage12606_allowed": False,
        "stage12606_reviewed_function_replay_allowed": True,
        "execution_performed": False,
        "raw_replay_evidence_present": False,
        **no_replay_claim_fields(),
    }
    check_false(pointer, "stage12605_pointer")
    assert_public_sanitized(pointer, "stage12605_pointer")
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
