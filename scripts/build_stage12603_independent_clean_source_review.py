#!/usr/bin/env python3
"""Build Stage12603 independent clean-source review packet.

This stage ingests the bounded independent review transcript for the Stage12602
clean candidate runner. It passes source review only; it does not enable the
execute path, grant an execution gate, emit a command manifest, run replay,
materialize Level-3, or admit training/eval.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12603_independent_clean_source_review"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
S12602 = ROOT / "runs/local/artifacts/stage12602_clean_candidate_source_packet"
S12602_EXTERNAL = ROOT / "runs/summaries/stage12602_clean_candidate_source_packet.json"
TRANSCRIPT = ROOT / "runs/local/private/stage12603_sartre_clean_source_review_transcript.json"
EXPECTED_STAGE12602_RUNNER = "d1ded97530116a515fdf41db5fd5ab42ff725a14ef570c6d6de18ef93c286e19"
EXPECTED_STAGE12602_BUILDER = "45a339f1eb15733e7d2cc3a8dd1f8750122ce9ea4b592417f13f747f375bf2a2"
EXPECTED_STAGE12602_TESTS = "dd94d92bb46a37b19358ea34f05998ef0bdc226723a7ecb6875877318373a8a3"
EXPECTED_STAGE12602_SUMMARY = "93d8729d8741c7bff4b5d67cd2b3e910abf1bac4041d85778cf08c95ec0ccaec"
EXPECTED_STAGE12602_CONTRACT = "497c9b4db8841ec2a05033f8414ba913efe8ae26a1e8ef043799550f13acceee"
EXPECTED_STAGE12602_POINTER = "0a974f7e02c84eab6f183c0ac201c2907470ec4c00382712e621e4d2e5381799"
EXPECTED_STAGE12602_PRIVATE = "2c8cd98c13d0618f19bcdedcf5a620a1e187bdefb680a0858d555863d94c571a"
EXPECTED_REVIEW_TRANSCRIPT = "ca2137b75bf55cdeb0a7fb1925a10e44cb18a2bdfdf2f0af1eac3c5f34cd383f"
FALSE_FIELDS = (
    "implementation_ready", "stage12595_allowed", "authorizes_execution", "execution_allowed",
    "execution_performed", "replay_trustworthy", "level_3_materialized", "training_admitted",
    "strict_eval_admitted", "sealed_eval_admitted", "strict_eval_eligible", "sealed_eval_eligible",
    "admission_allowed", "training_allowed", "ranking_allowed", "positive_stop", "stage12604_allowed",
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


def load_stage12602() -> dict[str, Any]:
    summary = read_json(S12602 / "summary.json")
    external = read_json(S12602_EXTERNAL)
    contract = read_json(S12602 / "contract.json")
    pointer = read_json(S12602 / "digest_pointer.json")
    private = read_json(S12602 / "private/clean_candidate_source_packet.json")
    if summary != external:
        raise GateError("stage12602_external_summary_mismatch")
    expected = (
        (sha256_file(ROOT / "scripts/run_stage12602_clean_manual_replay_executor.py"), EXPECTED_STAGE12602_RUNNER, "runner"),
        (sha256_file(ROOT / "scripts/build_stage12602_clean_candidate_source_packet.py"), EXPECTED_STAGE12602_BUILDER, "builder"),
        (sha256_file(ROOT / "tests/test_stage12602_clean_candidate_source_packet.py"), EXPECTED_STAGE12602_TESTS, "tests"),
        (stable_hash(summary), EXPECTED_STAGE12602_SUMMARY, "summary"),
        (stable_hash(contract), EXPECTED_STAGE12602_CONTRACT, "contract"),
        (stable_hash(pointer), EXPECTED_STAGE12602_POINTER, "pointer"),
        (stable_hash(private), EXPECTED_STAGE12602_PRIVATE, "private"),
    )
    for actual, expected_hash, label in expected:
        if actual != expected_hash:
            raise GateError("stage12602_pin_drift:" + label)
    if summary.get("decision") != "BLOCKED_INDEPENDENT_EXECUTION_CAPABLE_SOURCE_REVIEW_REQUIRED":
        raise GateError("stage12602_decision_drift")
    if summary.get("source_review_request_ready") is not True:
        raise GateError("stage12602_review_request_not_ready")
    if summary.get("duplicate_definition_ambiguity_present") is not False:
        raise GateError("stage12602_duplicate_ambiguity_drift")
    if summary.get("execute_reviewed_slot_definition_count") != 1:
        raise GateError("stage12602_execute_definition_count_drift")
    for field in ("reviewed_execution_capable_source_present", "independent_execution_capable_source_review_present",
                  "execute_path_enabled", "execution_gate_granted", "this_stage_runs_replay",
                  "executor_command_manifest_present", "raw_replay_evidence_present"):
        if summary.get(field) is not False or contract.get(field) is not False:
            raise GateError("stage12602_boundary_drift:" + field)
    if summary.get("execution_request_ready_count") != 0 or contract.get("execution_request_ready_count") != 0:
        raise GateError("stage12602_execution_request_count_drift")
    for label, record in (("summary", summary), ("contract", contract), ("pointer", pointer), ("private", private)):
        check_false(record, "stage12602_" + label)
    return {"summary": summary, "contract": contract, "pointer": pointer, "private": private}


def load_review_transcript(path: Path = TRANSCRIPT) -> dict[str, Any]:
    transcript = read_json(path)
    if stable_hash(transcript) != EXPECTED_REVIEW_TRANSCRIPT:
        raise GateError("stage12603_review_transcript_pin_drift")
    if transcript.get("review_result") != "PASS_NO_BLOCKER_FOR_CLEAN_CANDIDATE_SOURCE_PACKET":
        raise GateError("stage12603_review_result_drift")
    if transcript.get("review_scope") != "stage12602_clean_candidate_source_packet_only_no_execution_authorization":
        raise GateError("stage12603_review_scope_drift")
    if transcript.get("review_execution_performed") is not False or transcript.get("review_edits_performed") is not False:
        raise GateError("stage12603_review_side_effect_drift")
    if transcript.get("candidate_runner_sha256") != EXPECTED_STAGE12602_RUNNER:
        raise GateError("stage12603_runner_review_pin_drift")
    if transcript.get("stage12602_summary_sha256") != EXPECTED_STAGE12602_SUMMARY:
        raise GateError("stage12603_summary_review_pin_drift")
    if transcript.get("independent_execution_capable_source_review_present") is not True:
        raise GateError("stage12603_review_presence_missing")
    if transcript.get("independent_execution_capable_source_review_passed") is not True:
        raise GateError("stage12603_review_pass_missing")
    if transcript.get("reviewed_execution_capable_source_present") is not True:
        raise GateError("stage12603_reviewed_source_missing")
    check_false(transcript, "stage12603_transcript")
    return transcript


def build_review_packet(stage12602: Mapping[str, Any], transcript: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    private_review = {
        "record_type": "stage12603_private_independent_clean_source_review_v1",
        "stage12602_runner_sha256": EXPECTED_STAGE12602_RUNNER,
        "stage12602_summary_sha256": EXPECTED_STAGE12602_SUMMARY,
        "review_transcript_sha256": EXPECTED_REVIEW_TRANSCRIPT,
        "review_result": transcript["review_result"],
        "review_scope": transcript["review_scope"],
        "reviewer_agent_id": transcript["reviewer_agent_id"],
        "reviewer_nickname": transcript["reviewer_nickname"],
        "review_edits_performed": False,
        "review_execution_performed": False,
        "reviewed_execution_capable_source_present": True,
        "independent_execution_capable_source_review_present": True,
        "independent_execution_capable_source_review_passed": True,
        "execute_path_enabled": False,
        "execution_gate_granted": False,
        "execution_request_ready_count": 0,
        "this_stage_runs_replay": False,
        "executor_command_manifest_present": False,
        "raw_replay_evidence_present": False,
        **no_claim_fields(),
    }
    public_contract = {
        "record_type": "stage12603_public_independent_clean_source_review_contract_v1",
        "stage12602_runner_sha256": EXPECTED_STAGE12602_RUNNER,
        "stage12602_summary_sha256": EXPECTED_STAGE12602_SUMMARY,
        "review_transcript_sha256": EXPECTED_REVIEW_TRANSCRIPT,
        "reviewed_execution_capable_source_present": True,
        "independent_execution_capable_source_review_present": True,
        "independent_execution_capable_source_review_passed": True,
        "execute_path_enabled": False,
        "execution_gate_granted": False,
        "execution_request_ready_count": 0,
        "this_stage_runs_replay": False,
        "executor_command_manifest_present": False,
        "raw_replay_evidence_present": False,
        "claim_boundary": {
            "execution_authorization": "separate_execution_gate_required",
            "replay_success_claim": "forbidden_until_manual_executor_raw_artifacts_exist",
            "level3_claim": "forbidden_until_causal_candidate_and_stop_continue_provenance_exist",
            "training_admission": "separate_future_gate_required",
        },
        **no_claim_fields(),
    }
    summary = {
        "record_type": "stage12603_public_independent_clean_source_review_summary_v1",
        "stage": STAGE,
        "decision": "BLOCKED_EXECUTION_GATE_REQUIRED",
        "stage12602_runner_sha256": EXPECTED_STAGE12602_RUNNER,
        "stage12602_summary_sha256": EXPECTED_STAGE12602_SUMMARY,
        "review_transcript_sha256": EXPECTED_REVIEW_TRANSCRIPT,
        "source_cleanup_successor_reviewed": True,
        "reviewed_execution_capable_source_present": True,
        "independent_execution_capable_source_review_present": True,
        "independent_execution_capable_source_review_passed": True,
        "execute_path_enabled": False,
        "execution_gate_granted": False,
        "execution_request_ready_count": 0,
        "this_stage_runs_replay": False,
        "executor_command_manifest_present": False,
        "raw_replay_evidence_present": False,
        "stage12604_allowed": False,
        "level3_atom_count": 0,
        "downstream_blockers": [
            "execution_gate_not_granted_for_reviewed_source",
            "execute_path_disabled_pending_execution_gate",
            "execution_request_materials_absent",
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
        check_false(record, "stage12603_" + label)
        assert_public_sanitized(record, "stage12603_" + label)
    check_false(private_review, "stage12603_private_review")
    return summary, public_contract, private_review


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    stage12602 = load_stage12602()
    transcript = load_review_transcript()
    summary, public_contract, private_review = build_review_packet(stage12602, transcript)
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "contract.json", public_contract)
    write_json(out / "private/independent_clean_source_review.json", private_review)
    pointer = {
        "record_type": "stage12603_public_private_clean_source_review_pointer_v1",
        "stage12602_runner_sha256": EXPECTED_STAGE12602_RUNNER,
        "review_transcript_sha256": EXPECTED_REVIEW_TRANSCRIPT,
        "private_independent_clean_source_review_sha256": stable_hash(private_review),
        **no_claim_fields(),
    }
    check_false(pointer, "stage12603_pointer")
    assert_public_sanitized(pointer, "stage12603_pointer")
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
