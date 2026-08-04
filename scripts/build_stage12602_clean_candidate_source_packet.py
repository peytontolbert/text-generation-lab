#!/usr/bin/env python3
"""Build Stage12602 clean candidate source packet.

This stage introduces a clean successor runner source after Stage12601 blocked the
Stage12600 source-review attempt on duplicate-definition ambiguity. It does not
execute replay, does not pass independent review, and does not grant execution.
"""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12602_clean_candidate_source_packet"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
RUNNER = ROOT / "scripts/run_stage12602_clean_manual_replay_executor.py"
S12601 = ROOT / "runs/local/artifacts/stage12601_candidate_source_review_blocker"
S12601_EXTERNAL = ROOT / "runs/summaries/stage12601_candidate_source_review_blocker.json"
EXPECTED_STAGE12602_RUNNER = "d1ded97530116a515fdf41db5fd5ab42ff725a14ef570c6d6de18ef93c286e19"
EXPECTED_STAGE12601_SUMMARY = "d82cc046c7bda44df87978e88990c4540e7e47108077718b4d8cc00981ed45fe"
EXPECTED_STAGE12601_CONTRACT = "5c3e6b1d972427d01bb403172f2375ebfcbe27768806328e00a28d7240422adf"
EXPECTED_STAGE12601_POINTER = "c2fde83108d64105da5f0472c6db491dcfa591829e6fbece93a444b3db8cba54"
EXPECTED_STAGE12601_PRIVATE = "f823b84a378a819d3cf6d1f6e4ac99127db21fe253e97c6bb4644a1004b8330b"
FALSE_FIELDS = (
    "implementation_ready", "stage12595_allowed", "authorizes_execution", "execution_allowed",
    "execution_performed", "replay_trustworthy", "level_3_materialized", "training_admitted",
    "strict_eval_admitted", "sealed_eval_admitted", "strict_eval_eligible", "sealed_eval_eligible",
    "admission_allowed", "training_allowed", "ranking_allowed", "positive_stop", "stage12603_allowed",
)
PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "selector", "raw_stream", "stdout.raw", "stderr.raw", "before_commit_oid",
    "after_commit_oid", "production_path", "production_patch_sha256", "manual_executor_slot_contracts",
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


def load_stage12601(root: Path = S12601, external_path: Path = S12601_EXTERNAL) -> dict[str, Any]:
    summary = read_json(root / "summary.json")
    external = read_json(external_path)
    contract = read_json(root / "contract.json")
    pointer = read_json(root / "digest_pointer.json")
    private = read_json(root / "private/candidate_source_review_blocker.json")
    if summary != external:
        raise GateError("stage12601_external_summary_mismatch")
    expected = (
        (stable_hash(summary), EXPECTED_STAGE12601_SUMMARY, "summary"),
        (stable_hash(contract), EXPECTED_STAGE12601_CONTRACT, "contract"),
        (stable_hash(pointer), EXPECTED_STAGE12601_POINTER, "pointer"),
        (stable_hash(private), EXPECTED_STAGE12601_PRIVATE, "private"),
    )
    for actual, expected_hash, label in expected:
        if actual != expected_hash:
            raise GateError("stage12601_pin_drift:" + label)
    if summary.get("decision") != "BLOCKED_SOURCE_CLEANUP_REQUIRED_BEFORE_INDEPENDENT_REVIEW":
        raise GateError("stage12601_decision_drift")
    if summary.get("source_ambiguity_blocker_present") is not True:
        raise GateError("stage12601_ambiguity_blocker_missing")
    if private.get("execute_reviewed_slot_definition_count") != 2:
        raise GateError("stage12601_duplicate_count_drift")
    for label, record in (("summary", summary), ("contract", contract), ("pointer", pointer), ("private", private)):
        check_false(record, "stage12601_" + label)
    return {"summary": summary, "contract": contract, "pointer": pointer, "private": private}


def analyze_runner_source(path: Path = RUNNER) -> dict[str, Any]:
    if sha256_file(path) != EXPECTED_STAGE12602_RUNNER:
        raise GateError("stage12602_runner_source_pin_drift")
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=path.name)
    execute_defs = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "execute_reviewed_slot"]
    registry_assignments = [
        node for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "IMPLEMENTED_REVIEWABLE_FUNCTIONS" for target in node.targets)
    ]
    call_names: set[str] = set()
    if execute_defs:
        for node in ast.walk(execute_defs[0]):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name):
                    call_names.add(func.id)
                elif isinstance(func, ast.Attribute):
                    call_names.add(func.attr)
    return {
        "record_type": "stage12602_private_clean_candidate_source_static_analysis_v1",
        "runner_sha256": EXPECTED_STAGE12602_RUNNER,
        "execute_reviewed_slot_definition_count": len(execute_defs),
        "execute_reviewed_slot_definition_lines": [node.lineno for node in execute_defs],
        "implemented_reviewable_functions_assignment_count": len(registry_assignments),
        "implemented_reviewable_functions_assignment_lines": [node.lineno for node in registry_assignments],
        "duplicate_definition_ambiguity_present": len(execute_defs) != 1 or len(registry_assignments) != 1,
        "execute_reviewed_slot_calls": sorted(call_names),
        **no_claim_fields(),
    }


def load_runner(path: Path = RUNNER):
    if sha256_file(path) != EXPECTED_STAGE12602_RUNNER:
        raise GateError("stage12602_runner_source_pin_drift")
    spec = importlib.util.spec_from_file_location("stage12602_runner", path)
    if spec is None or spec.loader is None:
        raise GateError("stage12602_runner_import_failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_cli(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)


def validate_clean_runner(runner_path: Path = RUNNER) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    stage12601 = load_stage12601()
    source_analysis = analyze_runner_source(runner_path)
    if source_analysis["duplicate_definition_ambiguity_present"] is not False:
        raise GateError("stage12602_duplicate_definition_ambiguity_present")
    if source_analysis["execute_reviewed_slot_definition_count"] != 1:
        raise GateError("stage12602_execute_definition_count_mismatch")
    if source_analysis["implemented_reviewable_functions_assignment_count"] != 1:
        raise GateError("stage12602_registry_assignment_count_mismatch")
    runner = load_runner(runner_path)
    descriptor = runner.describe()
    cli = run_cli([sys.executable, str(runner_path), "--describe-only"])
    if cli.returncode != 0:
        raise GateError("stage12602_describe_cli_failed")
    if json.loads(cli.stdout) != descriptor:
        raise GateError("stage12602_describe_cli_mismatch")
    execute = run_cli([sys.executable, str(runner_path), "--execute"])
    if execute.returncode == 0 or "execution_disabled_pending_independent_execution_capable_source_review" not in execute.stderr:
        raise GateError("stage12602_execute_not_rejected")
    if descriptor.get("duplicate_definition_ambiguity_present") is not False:
        raise GateError("stage12602_descriptor_ambiguity_drift")
    if descriptor.get("source_cleanup_successor_to_stage12601") is not True:
        raise GateError("stage12602_cleanup_successor_missing")
    if descriptor.get("candidate_execution_capable_source_present") is not True:
        raise GateError("stage12602_candidate_source_missing")
    if descriptor.get("candidate_execution_implementation_present") is not True:
        raise GateError("stage12602_candidate_implementation_missing")
    for field in ("reviewed_execution_capable_source_present", "independent_execution_capable_source_review_present",
                  "execute_path_enabled", "execution_gate_granted", "this_stage_runs_replay",
                  "executor_command_manifest_present", "raw_replay_evidence_present"):
        if descriptor.get(field) is not False:
            raise GateError("stage12602_descriptor_boundary_drift:" + field)
    if descriptor.get("execution_request_ready_count") != 0:
        raise GateError("stage12602_execution_request_count_drift")
    check_false(descriptor, "stage12602_descriptor")
    return stage12601, source_analysis, descriptor


def build_source_packet(stage12601: Mapping[str, Any], source_analysis: Mapping[str, Any], descriptor: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    private_packet = {
        "record_type": "stage12602_private_clean_candidate_source_packet_v1",
        "stage12601_summary_sha256": EXPECTED_STAGE12601_SUMMARY,
        "stage12601_private_review_blocker_sha256": EXPECTED_STAGE12601_PRIVATE,
        "candidate_runner_sha256": EXPECTED_STAGE12602_RUNNER,
        "candidate_descriptor_sha256": stable_hash(descriptor),
        "source_static_analysis_sha256": stable_hash(source_analysis),
        "source_cleanup_successor_to_stage12601": True,
        "duplicate_definition_ambiguity_present": False,
        "execute_reviewed_slot_definition_count": source_analysis["execute_reviewed_slot_definition_count"],
        "implemented_reviewable_functions_assignment_count": source_analysis["implemented_reviewable_functions_assignment_count"],
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
        "required_controls": list(descriptor["required_controls"]),
        "implemented_reviewable_functions": list(descriptor["implemented_reviewable_functions"]),
        "required_future_gate": "independent_execution_capable_source_review_before_execute_path_enablement",
        **no_claim_fields(),
    }
    public_contract = {
        "record_type": "stage12602_public_clean_candidate_source_contract_v1",
        "stage12601_summary_sha256": EXPECTED_STAGE12601_SUMMARY,
        "candidate_runner_sha256": EXPECTED_STAGE12602_RUNNER,
        "source_cleanup_successor_to_stage12601": True,
        "source_cleanup_applied": True,
        "duplicate_definition_ambiguity_present": False,
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
        "source_review_request_ready": True,
        "required_controls_sha256": stable_hash(descriptor["required_controls"]),
        "implemented_reviewable_functions_sha256": stable_hash(descriptor["implemented_reviewable_functions"]),
        "claim_boundary": {
            "independent_source_review": "not_passed_in_this_stage",
            "replay_success_claim": "forbidden_until_manual_executor_raw_artifacts_exist",
            "level3_claim": "forbidden_until_causal_candidate_and_stop_continue_provenance_exist",
            "training_admission": "separate_future_gate_required",
        },
        **no_claim_fields(),
    }
    summary = {
        "record_type": "stage12602_public_clean_candidate_source_summary_v1",
        "stage": STAGE,
        "decision": "BLOCKED_INDEPENDENT_EXECUTION_CAPABLE_SOURCE_REVIEW_REQUIRED",
        "stage12601_summary_sha256": EXPECTED_STAGE12601_SUMMARY,
        "candidate_runner_sha256": EXPECTED_STAGE12602_RUNNER,
        "source_cleanup_successor_to_stage12601": True,
        "source_cleanup_applied": True,
        "duplicate_definition_ambiguity_present": False,
        "execute_reviewed_slot_definition_count": source_analysis["execute_reviewed_slot_definition_count"],
        "implemented_reviewable_functions_assignment_count": source_analysis["implemented_reviewable_functions_assignment_count"],
        "candidate_execution_capable_source_present": True,
        "candidate_execution_implementation_present": True,
        "reviewed_execution_capable_source_present": False,
        "independent_execution_capable_source_review_present": False,
        "independent_execution_capable_source_review_passed": False,
        "execute_entrypoint_declared": True,
        "execute_path_enabled": False,
        "execution_gate_granted": False,
        "manual_replay_slot_count": descriptor["manual_replay_slot_count"],
        "execution_request_ready_count": 0,
        "this_stage_runs_replay": False,
        "executor_command_manifest_present": False,
        "raw_replay_evidence_present": False,
        "source_review_request_ready": True,
        "stage12603_allowed": False,
        "level3_atom_count": 0,
        "required_controls_sha256": stable_hash(descriptor["required_controls"]),
        "implemented_reviewable_functions_sha256": stable_hash(descriptor["implemented_reviewable_functions"]),
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
    for label, record in (("summary", summary), ("contract", public_contract)):
        check_false(record, "stage12602_" + label)
        assert_public_sanitized(record, "stage12602_" + label)
    check_false(private_packet, "stage12602_private_packet")
    return summary, public_contract, private_packet


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    stage12601, source_analysis, descriptor = validate_clean_runner()
    summary, public_contract, private_packet = build_source_packet(stage12601, source_analysis, descriptor)
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "contract.json", public_contract)
    write_json(out / "private/clean_candidate_source_packet.json", private_packet)
    pointer = {
        "record_type": "stage12602_public_private_clean_candidate_source_pointer_v1",
        "candidate_runner_sha256": EXPECTED_STAGE12602_RUNNER,
        "private_clean_candidate_source_packet_sha256": stable_hash(private_packet),
        "source_static_analysis_sha256": stable_hash(source_analysis),
        "stage12601_summary_sha256": EXPECTED_STAGE12601_SUMMARY,
        **no_claim_fields(),
    }
    check_false(pointer, "stage12602_pointer")
    assert_public_sanitized(pointer, "stage12602_pointer")
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
