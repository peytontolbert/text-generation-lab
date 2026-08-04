#!/usr/bin/env python3
"""Build Stage12601 candidate source review blocker packet.

This stage does not execute replay and does not pass independent review. It pins
Stage12600 and records that the candidate runner still has duplicate
execute_reviewed_slot definitions, so the source must be cleaned before a pass
review or execution gate can be truthful.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12601_candidate_source_review_blocker"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
RUNNER = ROOT / "scripts/run_stage12600_candidate_manual_replay_executor.py"
BUILDER = ROOT / "scripts/build_stage12600_candidate_execution_capable_source_packet.py"
TESTS = ROOT / "tests/test_stage12600_candidate_execution_capable_source_packet.py"
S12600 = ROOT / "runs/local/artifacts/stage12600_candidate_execution_capable_source_packet"
S12600_EXTERNAL = ROOT / "runs/summaries/stage12600_candidate_execution_capable_source_packet.json"
EXPECTED_STAGE12600_RUNNER = "569e2d4bee5c9c3786cfaea0cee8ab123f50ae2ba22138e9064f3a06267bd39a"
EXPECTED_STAGE12600_BUILDER = "0e3b0e917e3d772971429c51412ce36c5d394c044c1a6480b46e61e18a9f0a51"
EXPECTED_STAGE12600_TESTS = "bf576ab84cd69dc0ac9905e0697090ec54139a47075572f59523b55443f013e9"
EXPECTED_STAGE12600_SUMMARY = "c9c5f8b965668a1ef834adbe8bd932ac02a2772614c1a589510fa60713c3665f"
EXPECTED_STAGE12600_CONTRACT = "38168afd3f10d187536a7638d45b786ed98ae7cbb59d762d1e7650185a577246"
EXPECTED_STAGE12600_POINTER = "c410fd88ead3936090bc3ac2c7ff97571aa774d0af131e372c82bdd528ef4514"
EXPECTED_STAGE12600_PRIVATE = "7734efd6b3afb380af2c64ff4afd1c0eb68e04c009be29f3c980d70017132d57"
FALSE_FIELDS = (
    "implementation_ready", "stage12595_allowed", "authorizes_execution", "execution_allowed",
    "execution_performed", "replay_trustworthy", "level_3_materialized", "training_admitted",
    "strict_eval_admitted", "sealed_eval_admitted", "strict_eval_eligible", "sealed_eval_eligible",
    "admission_allowed", "training_allowed", "ranking_allowed", "positive_stop", "stage12602_allowed",
)
PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "selector", "raw_stream", "stdout.raw", "stderr.raw", "before_commit_oid",
    "after_commit_oid", "production_path", "production_patch_sha256", "manual_executor_slot_contracts",
)
REQUIRED_STAGE12600_FALSE = (
    "implementation_ready", "stage12595_allowed", "authorizes_execution", "execution_allowed",
    "execution_performed", "replay_trustworthy", "level_3_materialized", "training_admitted",
    "strict_eval_admitted", "sealed_eval_admitted", "strict_eval_eligible", "sealed_eval_eligible",
    "training_allowed", "ranking_allowed", "positive_stop", "stage12601_allowed",
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


def load_stage12600() -> dict[str, Any]:
    summary = read_json(S12600 / "summary.json")
    external = read_json(S12600_EXTERNAL)
    contract = read_json(S12600 / "contract.json")
    pointer = read_json(S12600 / "digest_pointer.json")
    private = read_json(S12600 / "private/candidate_execution_capable_source_packet.json")
    if summary != external:
        raise GateError("stage12600_external_summary_mismatch")
    expected = (
        (sha256_file(RUNNER), EXPECTED_STAGE12600_RUNNER, "runner"),
        (sha256_file(BUILDER), EXPECTED_STAGE12600_BUILDER, "builder"),
        (sha256_file(TESTS), EXPECTED_STAGE12600_TESTS, "tests"),
        (stable_hash(summary), EXPECTED_STAGE12600_SUMMARY, "summary"),
        (stable_hash(contract), EXPECTED_STAGE12600_CONTRACT, "contract"),
        (stable_hash(pointer), EXPECTED_STAGE12600_POINTER, "pointer"),
        (stable_hash(private), EXPECTED_STAGE12600_PRIVATE, "private"),
    )
    for actual, expected_hash, label in expected:
        if actual != expected_hash:
            raise GateError("stage12600_pin_drift:" + label)
    if summary.get("decision") != "BLOCKED_INDEPENDENT_EXECUTION_CAPABLE_SOURCE_REVIEW_REQUIRED":
        raise GateError("stage12600_decision_drift")
    if summary.get("candidate_execution_capable_source_present") is not True:
        raise GateError("stage12600_candidate_source_missing")
    if summary.get("candidate_execution_implementation_present") is not True:
        raise GateError("stage12600_candidate_implementation_missing")
    for field in REQUIRED_STAGE12600_FALSE:
        if summary.get(field) is not False:
            raise GateError("stage12600_false_gate_drift:" + field)
    for field in ("reviewed_execution_capable_source_present", "independent_execution_capable_source_review_present",
                  "execute_path_enabled", "execution_gate_granted", "this_stage_runs_replay",
                  "executor_command_manifest_present", "raw_replay_evidence_present"):
        if summary.get(field) is not False or contract.get(field) is not False:
            raise GateError("stage12600_boundary_drift:" + field)
    if summary.get("execution_request_ready_count") != 0 or contract.get("execution_request_ready_count") != 0:
        raise GateError("stage12600_execution_request_count_drift")
    for label, record in (("summary", summary), ("contract", contract), ("pointer", pointer), ("private", private)):
        check_false(record, "stage12600_" + label)
    return {"summary": summary, "contract": contract, "pointer": pointer, "private": private}


def analyze_runner_source(path: Path = RUNNER) -> dict[str, Any]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=path.name)
    defs = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "execute_reviewed_slot"]
    implemented_tuple_assignments = [
        node for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "IMPLEMENTED_REVIEWABLE_FUNCTIONS" for target in node.targets)
    ]
    call_names: set[str] = set()
    if defs:
        for node in ast.walk(defs[-1]):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name):
                    call_names.add(func.id)
                elif isinstance(func, ast.Attribute):
                    call_names.add(func.attr)
    return {
        "record_type": "stage12601_private_candidate_source_static_review_v1",
        "runner_sha256": sha256_file(path),
        "execute_reviewed_slot_definition_count": len(defs),
        "execute_reviewed_slot_definition_lines": [node.lineno for node in defs],
        "implemented_reviewable_functions_assignment_count": len(implemented_tuple_assignments),
        "implemented_reviewable_functions_assignment_lines": [node.lineno for node in implemented_tuple_assignments],
        "last_execute_reviewed_slot_calls": sorted(call_names),
        "duplicate_definition_ambiguity_present": len(defs) != 1,
        "review_blocker": "duplicate_execute_reviewed_slot_definitions" if len(defs) != 1 else "none",
        **no_claim_fields(),
    }


def build_review_packet(stage12600: Mapping[str, Any], source_review: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    blocker_present = source_review.get("duplicate_definition_ambiguity_present") is True
    if not blocker_present:
        raise GateError("stage12601_expected_duplicate_definition_blocker_missing")
    private_review = {
        "record_type": "stage12601_private_candidate_source_review_blocker_v1",
        "stage12600_runner_sha256": EXPECTED_STAGE12600_RUNNER,
        "stage12600_summary_sha256": EXPECTED_STAGE12600_SUMMARY,
        "review_result": "BLOCKED_DUPLICATE_EXECUTE_REVIEWED_SLOT_DEFINITIONS",
        "independent_review_passed": False,
        "source_cleanup_required_before_independent_review": True,
        "duplicate_definition_ambiguity_present": True,
        "execute_reviewed_slot_definition_count": source_review["execute_reviewed_slot_definition_count"],
        "execute_reviewed_slot_definition_lines": source_review["execute_reviewed_slot_definition_lines"],
        "implemented_reviewable_functions_assignment_count": source_review["implemented_reviewable_functions_assignment_count"],
        "implemented_reviewable_functions_assignment_lines": source_review["implemented_reviewable_functions_assignment_lines"],
        "last_execute_reviewed_slot_calls": source_review["last_execute_reviewed_slot_calls"],
        "review_scope": "candidate_source_static_review_only_no_execution",
        **no_claim_fields(),
    }
    public_contract = {
        "record_type": "stage12601_public_candidate_source_review_blocker_contract_v1",
        "stage12600_runner_sha256": EXPECTED_STAGE12600_RUNNER,
        "stage12600_summary_sha256": EXPECTED_STAGE12600_SUMMARY,
        "candidate_execution_capable_source_present": True,
        "candidate_execution_implementation_present": True,
        "source_review_attempted": True,
        "source_cleanup_required_before_independent_review": True,
        "source_ambiguity_blocker_present": True,
        "reviewed_execution_capable_source_present": False,
        "independent_execution_capable_source_review_present": False,
        "independent_execution_capable_source_review_passed": False,
        "execute_path_enabled": False,
        "execution_gate_granted": False,
        "execution_request_ready_count": 0,
        "this_stage_runs_replay": False,
        "executor_command_manifest_present": False,
        "raw_replay_evidence_present": False,
        "review_blocker_sha256": stable_hash(private_review),
        **no_claim_fields(),
    }
    summary = {
        "record_type": "stage12601_public_candidate_source_review_blocker_summary_v1",
        "stage": STAGE,
        "decision": "BLOCKED_SOURCE_CLEANUP_REQUIRED_BEFORE_INDEPENDENT_REVIEW",
        "stage12600_runner_sha256": EXPECTED_STAGE12600_RUNNER,
        "stage12600_summary_sha256": EXPECTED_STAGE12600_SUMMARY,
        "candidate_execution_capable_source_present": True,
        "candidate_execution_implementation_present": True,
        "source_review_attempted": True,
        "source_cleanup_required_before_independent_review": True,
        "source_ambiguity_blocker_present": True,
        "reviewed_execution_capable_source_present": False,
        "independent_execution_capable_source_review_present": False,
        "independent_execution_capable_source_review_passed": False,
        "execute_path_enabled": False,
        "execution_gate_granted": False,
        "execution_request_ready_count": 0,
        "this_stage_runs_replay": False,
        "executor_command_manifest_present": False,
        "raw_replay_evidence_present": False,
        "stage12602_allowed": False,
        "level3_atom_count": 0,
        "downstream_blockers": [
            "source_cleanup_required_before_independent_review",
            "duplicate_execute_reviewed_slot_definition_ambiguity",
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
        check_false(record, "stage12601_" + label)
        assert_public_sanitized(record, "stage12601_" + label)
    check_false(private_review, "stage12601_private_review")
    return summary, public_contract, private_review


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    stage12600 = load_stage12600()
    source_review = analyze_runner_source()
    summary, public_contract, private_review = build_review_packet(stage12600, source_review)
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "contract.json", public_contract)
    write_json(out / "private/candidate_source_review_blocker.json", private_review)
    pointer = {
        "record_type": "stage12601_public_private_review_blocker_pointer_v1",
        "stage12600_runner_sha256": EXPECTED_STAGE12600_RUNNER,
        "private_candidate_source_review_blocker_sha256": stable_hash(private_review),
        "source_review_static_analysis_sha256": stable_hash(source_review),
        **no_claim_fields(),
    }
    check_false(pointer, "stage12601_pointer")
    assert_public_sanitized(pointer, "stage12601_pointer")
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
