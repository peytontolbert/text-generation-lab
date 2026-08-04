#!/usr/bin/env python3
"""Build Stage12600 candidate execution-capable source packet.

This stage introduces a candidate manual replay runner source for later review.
It does not authorize or run replay, and the candidate --execute path remains
hard-disabled pending independent review.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12600_candidate_execution_capable_source_packet"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
RUNNER = ROOT / "scripts/run_stage12600_candidate_manual_replay_executor.py"
S12599 = ROOT / "runs/local/artifacts/stage12599_execution_gate_intake_preflight_only_blocked"
S12599_EXTERNAL = ROOT / "runs/summaries/stage12599_execution_gate_intake_preflight_only_blocked.json"
EXPECTED_STAGE12599_SUMMARY = "6a5ed072fc33aced1288ea43b300fe20c496c562dfa537ba1f6bebe316f89f8e"
EXPECTED_STAGE12599_CONTRACT = "59f62adaa3a86533e43da6447db2ab0a84613b2d5348aa9574271f95975e14c5"
EXPECTED_STAGE12599_POINTER = "2a34e0d27e891046fe3c389e355f0dbd5d3784b9b5d0c26b18dedde2f2e2530e"
EXPECTED_STAGE12599_GATE_INTAKE = "92de5529cc55773d0413f108e2d4683fa1f47efa04901b0b8087b14157ccde35"
EXPECTED_STAGE12600_RUNNER = "569e2d4bee5c9c3786cfaea0cee8ab123f50ae2ba22138e9064f3a06267bd39a"
FALSE_FIELDS = (
    "implementation_ready", "stage12595_allowed", "authorizes_execution",
    "execution_allowed", "execution_performed", "replay_trustworthy",
    "level_3_materialized", "training_admitted", "strict_eval_admitted", "sealed_eval_admitted",
    "strict_eval_eligible", "sealed_eval_eligible", "admission_allowed", "training_allowed",
    "ranking_allowed", "positive_stop", "stage12601_allowed",
)
PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "selector", "raw_stream", "stdout.raw", "stderr.raw", "before_commit_oid",
    "after_commit_oid", "production_path", "production_patch_sha256", "manual_executor_slot_contracts",
)
REQUIRED_STAGE12599_BLOCKERS = (
    "execution_capable_manual_runner_source_absent",
    "independent_execution_capable_source_review_absent",
    "execute_path_disabled_pending_execution_capable_source_review",
    "manual_replay_execution_not_performed",
    "trusted_replay_raw_evidence_absent",
    "causally_committed_pre_outcome_candidate_set_absent_even_after_future_replay",
    "observed_stop_continue_decision_absent_even_after_future_replay",
    "level3_materialization_forbidden",
    "training_admission_forbidden",
    "strict_eval_admission_forbidden",
    "sealed_eval_admission_forbidden",
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


def no_claim_fields() -> dict[str, Any]:
    return {
        "implementation_ready": False,
        "stage12595_allowed": False,
        "authorizes_execution": False,
        "execution_allowed": False,
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


def load_stage12599(root: Path = S12599, external_path: Path = S12599_EXTERNAL) -> dict[str, Any]:
    summary = read_json(root / "summary.json")
    external = read_json(external_path)
    contract = read_json(root / "contract.json")
    pointer = read_json(root / "digest_pointer.json")
    gate_intake = read_json(root / "private/execution_gate_intake.json")
    if summary != external:
        raise GateError("stage12599_external_summary_mismatch")
    if stable_hash(summary) != EXPECTED_STAGE12599_SUMMARY:
        raise GateError("stage12599_summary_pin_drift")
    if stable_hash(contract) != EXPECTED_STAGE12599_CONTRACT:
        raise GateError("stage12599_contract_pin_drift")
    if stable_hash(pointer) != EXPECTED_STAGE12599_POINTER:
        raise GateError("stage12599_pointer_pin_drift")
    if stable_hash(gate_intake) != EXPECTED_STAGE12599_GATE_INTAKE:
        raise GateError("stage12599_gate_intake_pin_drift")
    if summary.get("decision") != "BLOCKED_EXECUTION_CAPABLE_SOURCE_REQUIRED":
        raise GateError("stage12599_decision_mismatch")
    if sorted(summary.get("downstream_blockers", [])) != sorted(REQUIRED_STAGE12599_BLOCKERS):
        raise GateError("stage12599_blocker_set_mismatch")
    for field in ("execution_gate_granted", "execution_capable_source_present",
                  "independent_execution_capable_source_review_present", "execute_path_enabled",
                  "this_stage_runs_replay", "executor_command_manifest_present", "raw_replay_evidence_present"):
        if summary.get(field) is not False or contract.get(field) is not False:
            raise GateError("stage12599_boundary_drift:" + field)
    if summary.get("execution_request_ready_count") != 0 or contract.get("execution_request_ready_count") != 0:
        raise GateError("stage12599_execution_request_count_drift")
    for label, record in (("summary", summary), ("contract", contract), ("pointer", pointer), ("gate_intake", gate_intake)):
        check_false(record, "stage12599_" + label)
    return {"summary": summary, "contract": contract, "pointer": pointer, "gate_intake": gate_intake}


def load_runner(path: Path = RUNNER):
    if sha256_file(path) != EXPECTED_STAGE12600_RUNNER:
        raise GateError("stage12600_runner_source_pin_drift")
    spec = importlib.util.spec_from_file_location("stage12600_runner", path)
    if spec is None or spec.loader is None:
        raise GateError("stage12600_runner_import_failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_cli(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)


def validate_candidate_runner(runner_path: Path = RUNNER, stage12599_root: Path = S12599) -> tuple[dict[str, Any], dict[str, Any]]:
    stage12599 = load_stage12599(stage12599_root, S12599_EXTERNAL)
    runner = load_runner(runner_path)
    descriptor = runner.build_candidate_source_descriptor(runner.load_stage12599(stage12599_root))
    cli = run_cli([sys.executable, str(runner_path), "--stage12599-root", str(stage12599_root), "--describe-only"])
    if cli.returncode != 0:
        raise GateError("stage12600_describe_cli_failed")
    if json.loads(cli.stdout) != descriptor:
        raise GateError("stage12600_describe_cli_mismatch")
    execute = run_cli([sys.executable, str(runner_path), "--stage12599-root", str(stage12599_root), "--execute"])
    if execute.returncode == 0 or "execution_disabled_pending_independent_execution_capable_source_review" not in execute.stderr:
        raise GateError("stage12600_execute_not_rejected")
    if descriptor.get("candidate_execution_capable_source_present") is not True:
        raise GateError("stage12600_candidate_source_missing")
    if descriptor.get("candidate_execution_implementation_present") is not True:
        raise GateError("stage12600_candidate_implementation_missing")
    if descriptor.get("patch_material_required_before_execution") is not True:
        raise GateError("stage12600_patch_material_requirement_missing")
    if descriptor.get("required_future_gate") != "independent_execution_capable_source_review_before_execute_path_enablement":
        raise GateError("stage12600_future_gate_drift")
    for field in ("reviewed_execution_capable_source_present", "independent_execution_capable_source_review_present",
                  "execute_path_enabled", "execution_gate_granted", "this_stage_runs_replay",
                  "executor_command_manifest_present", "raw_replay_evidence_present"):
        if descriptor.get(field) is not False:
            raise GateError("stage12600_descriptor_boundary_drift:" + field)
    if descriptor.get("execution_request_ready_count") != 0:
        raise GateError("stage12600_execution_request_count_drift")
    check_false(descriptor, "stage12600_descriptor")
    return stage12599, descriptor


def build_source_packet(stage12599: Mapping[str, Any], descriptor: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    private_source_packet = {
        "record_type": "stage12600_private_candidate_execution_capable_source_packet_v1",
        "candidate_runner_sha256": EXPECTED_STAGE12600_RUNNER,
        "stage12599_summary_sha256": EXPECTED_STAGE12599_SUMMARY,
        "candidate_descriptor_sha256": stable_hash(descriptor),
        "candidate_execution_capable_source_present": True,
        "candidate_execution_implementation_present": True,
        "reviewed_execution_capable_source_present": False,
        "independent_execution_capable_source_review_present": False,
        "execute_entrypoint_declared": True,
        "execute_path_enabled": False,
        "execution_gate_granted": False,
        "execution_request_ready_count": 0,
        "this_stage_runs_replay": False,
        "executor_command_manifest_present": False,
        "raw_replay_evidence_present": False,
        "patch_material_required_before_execution": True,
        "future_patch_digest_enforcement": "slot_patch_file_sha256_must_equal_stage12595_production_patch_sha256",
        "required_controls": list(descriptor["required_controls"]),
        "implemented_reviewable_functions": list(descriptor["implemented_reviewable_functions"]),
        "review_required_before_use": "independent_execution_capable_source_review_before_execute_path_enablement",
        **no_claim_fields(),
    }
    public_contract = {
        "record_type": "stage12600_public_candidate_execution_capable_source_contract_v1",
        "stage12594_publication_generation_id": descriptor["stage12594_publication_generation_id"],
        "stage12594_publication_manifest_sha256": descriptor["stage12594_publication_manifest_sha256"],
        "stage12595_slots_sha256": descriptor["stage12595_slots_sha256"],
        "candidate_runner_sha256": EXPECTED_STAGE12600_RUNNER,
        "candidate_execution_capable_source_present": True,
        "candidate_execution_implementation_present": True,
        "reviewed_execution_capable_source_present": False,
        "independent_execution_capable_source_review_present": False,
        "execute_entrypoint_declared": True,
        "execute_path_enabled": False,
        "execution_gate_granted": False,
        "execution_request_ready_count": 0,
        "this_stage_runs_replay": False,
        "executor_command_manifest_present": False,
        "raw_replay_evidence_present": False,
        "patch_material_required_before_execution": True,
        "future_patch_digest_enforcement": "slot_patch_file_digest_must_match_pinned_stage12595_patch_digest",
        "required_future_gate": "independent_execution_capable_source_review_before_execute_path_enablement",
        "required_controls_sha256": stable_hash(descriptor["required_controls"]),
        "implemented_reviewable_functions_sha256": stable_hash(descriptor["implemented_reviewable_functions"]),
        "claim_boundary": {
            "replay_success_claim": "forbidden_until_manual_executor_raw_artifacts_exist",
            "level3_claim": "forbidden_until_causal_candidate_and_stop_continue_provenance_exist",
            "training_admission": "separate_future_gate_required",
        },
        **no_claim_fields(),
    }
    summary = {
        "record_type": "stage12600_public_candidate_execution_capable_source_summary_v1",
        "stage": STAGE,
        "decision": "BLOCKED_INDEPENDENT_EXECUTION_CAPABLE_SOURCE_REVIEW_REQUIRED",
        "stage12594_publication_generation_id": descriptor["stage12594_publication_generation_id"],
        "stage12594_publication_manifest_sha256": descriptor["stage12594_publication_manifest_sha256"],
        "stage12595_slots_sha256": descriptor["stage12595_slots_sha256"],
        "stage12599_summary_sha256": EXPECTED_STAGE12599_SUMMARY,
        "candidate_runner_sha256": EXPECTED_STAGE12600_RUNNER,
        "candidate_execution_capable_source_present": True,
        "candidate_execution_implementation_present": True,
        "reviewed_execution_capable_source_present": False,
        "independent_execution_capable_source_review_present": False,
        "execute_entrypoint_declared": True,
        "execute_path_enabled": False,
        "execution_gate_granted": False,
        "manual_replay_slot_count": descriptor["manual_replay_slot_count"],
        "execution_request_ready_count": 0,
        "this_stage_runs_replay": False,
        "executor_command_manifest_present": False,
        "raw_replay_evidence_present": False,
        "patch_material_required_before_execution": True,
        "future_patch_digest_enforcement": "slot_patch_file_digest_must_match_pinned_stage12595_patch_digest",
        "required_future_gate": "independent_execution_capable_source_review_before_execute_path_enablement",
        "required_controls_sha256": stable_hash(descriptor["required_controls"]),
        "implemented_reviewable_functions_sha256": stable_hash(descriptor["implemented_reviewable_functions"]),
        "stage12601_allowed": False,
        "level3_atom_count": 0,
        "downstream_blockers": [
            "independent_execution_capable_source_review_absent",
            "execute_path_disabled_pending_execution_capable_source_review",
            "execution_gate_not_granted_for_candidate_source",
            "manual_replay_execution_not_performed",
            "trusted_replay_raw_evidence_absent",
            "causally_committed_pre_outcome_candidate_set_absent_even_after_future_replay",
            "observed_stop_continue_decision_absent_even_after_future_replay",
            "level3_materialization_forbidden",
            "training_admission_forbidden",
            "strict_eval_admission_forbidden",
            "sealed_eval_admission_forbidden",
        ],
        **no_claim_fields(),
    }
    for label, record in (("summary", summary), ("public_contract", public_contract)):
        check_false(record, "stage12600_" + label)
        assert_public_sanitized(record, "stage12600_" + label)
    check_false(private_source_packet, "stage12600_private_packet")
    return summary, public_contract, private_source_packet


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    stage12599, descriptor = validate_candidate_runner()
    summary, public_contract, private_source_packet = build_source_packet(stage12599, descriptor)
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "contract.json", public_contract)
    write_json(out / "private/candidate_execution_capable_source_packet.json", private_source_packet)
    pointer = {
        "record_type": "stage12600_public_private_candidate_source_pointer_v1",
        "candidate_runner_sha256": EXPECTED_STAGE12600_RUNNER,
        "private_candidate_source_packet_sha256": stable_hash(private_source_packet),
        "stage12599_summary_sha256": EXPECTED_STAGE12599_SUMMARY,
        **no_claim_fields(),
    }
    check_false(pointer, "stage12600_pointer")
    assert_public_sanitized(pointer, "stage12600_pointer")
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
