#!/usr/bin/env python3
"""Build Stage12599 execution gate intake for preflight-only source.

This stage evaluates whether the reviewed Stage12597 preflight-only source can
open an execution gate. It cannot: the source has no execute path and was
reviewed only as preflight. This packet does not run replay or authorize it.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12599_execution_gate_intake_preflight_only_blocked"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
S12598 = ROOT / "runs/local/artifacts/stage12598_independent_agent_executor_source_review"
S12598_EXTERNAL = ROOT / "runs/summaries/stage12598_independent_agent_executor_source_review.json"
S12598_SCRIPT = ROOT / "scripts/build_stage12598_independent_agent_executor_source_review.py"
S12598_TESTS = ROOT / "tests/test_stage12598_independent_agent_executor_source_review.py"
S12598_TRANSCRIPT = ROOT / "runs/local/private/stage12598_hypatia_source_review_transcript.json"
EXPECTED_STAGE12594_GENERATION = "91d0cda6e9acdf2e09c4d04b7d8e00159351bedf1ef0e7f70c4912d48c34475d"
EXPECTED_STAGE12594_MANIFEST = "5f5353b63591f77433a6a0a01141211796906ef13c02c2569c48f65a59c5a856"
EXPECTED_STAGE12595_SLOTS = "8ddfdfb0872c8cb74a46f0041801bced7e674228d74af98b30ce7631afebe3a0"
EXPECTED_STAGE12596_PRIVATE_CONTRACT = "f880781f4462211c29b071941e8105064f138a665647bffc5bb00c90c1d56edc"
EXPECTED_STAGE12597_RUNNER = "1213902efcaa177c6426eae590f1df596c6c59ed43a3caef09983e49ce37f5f8"
EXPECTED_STAGE12598_SCRIPT = "474410c5183440424e02fb68c145f6a783e34630b77dc7c4314b369256bb5967"
EXPECTED_STAGE12598_TESTS = "6b990e833931b4f864dab4dd07475450c7fb7c2cc5cfd45e9101da5772e08d2d"
EXPECTED_STAGE12598_TRANSCRIPT_FILE = "25cc37151894107b5323a8322699be22286aa006486995e8a4e566f465933d20"
EXPECTED_STAGE12598_TRANSCRIPT_CANONICAL = "00abcd7749987123c810b76e432f1983ab5dc8b72a6c19a78b24bdff534719f9"
EXPECTED_STAGE12598_SUMMARY = "758f65cfc1c3bfe1bdcb67624ee0310b8915162f6fc060e575567a0f7756a934"
EXPECTED_STAGE12598_CONTRACT = "afa459077dc3fcd2ad9f00ac3c73b048ac6b8ca1fc0fe1c3f0839c94aed6511a"
EXPECTED_STAGE12598_POINTER = "1a47c0006cb3531a055d9c51c2802801e81221122d51891097752f59027a3ccf"
EXPECTED_STAGE12598_PRIVATE_REVIEW = "246f191aa7d7693dd06e2d3eb6f7fae807b9294920cfa98d0fd8863a8204ce60"
REQUIRED_STAGE12598_BLOCKERS = (
    "execute_path_disabled_pending_execution_gate",
    "manual_replay_execution_not_performed",
    "trusted_replay_raw_evidence_absent",
    "causally_committed_pre_outcome_candidate_set_absent_even_after_future_replay",
    "observed_stop_continue_decision_absent_even_after_future_replay",
    "level3_materialization_forbidden",
    "training_admission_forbidden",
    "strict_eval_admission_forbidden",
    "sealed_eval_admission_forbidden",
)
FALSE_FIELDS = (
    "authorizes_execution", "execution_allowed", "execution_performed", "replay_trustworthy",
    "level_3_materialized", "training_admitted", "strict_eval_admitted", "sealed_eval_admitted",
    "strict_eval_eligible", "sealed_eval_eligible", "admission_allowed", "training_allowed",
    "ranking_allowed", "positive_stop", "stage12600_allowed",
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


def load_stage12598(
    root: Path = S12598,
    external_path: Path = S12598_EXTERNAL,
    script_path: Path = S12598_SCRIPT,
    tests_path: Path = S12598_TESTS,
    transcript_path: Path = S12598_TRANSCRIPT,
) -> dict[str, Any]:
    summary = read_json(root / "summary.json")
    external = read_json(external_path)
    contract = read_json(root / "contract.json")
    pointer = read_json(root / "digest_pointer.json")
    private_review = read_json(root / "private/bounded_independent_agent_source_review.json")
    transcript = read_json(transcript_path)
    if summary != external:
        raise GateError("stage12598_external_summary_mismatch")
    if stable_hash(summary) != EXPECTED_STAGE12598_SUMMARY:
        raise GateError("stage12598_summary_pin_drift")
    if stable_hash(contract) != EXPECTED_STAGE12598_CONTRACT:
        raise GateError("stage12598_contract_pin_drift")
    if stable_hash(pointer) != EXPECTED_STAGE12598_POINTER:
        raise GateError("stage12598_pointer_pin_drift")
    if stable_hash(private_review) != EXPECTED_STAGE12598_PRIVATE_REVIEW:
        raise GateError("stage12598_private_review_pin_drift")
    if stable_hash(transcript) != EXPECTED_STAGE12598_TRANSCRIPT_CANONICAL:
        raise GateError("stage12598_transcript_canonical_pin_drift")
    if sha256_file(script_path) != EXPECTED_STAGE12598_SCRIPT:
        raise GateError("stage12598_script_pin_drift")
    if sha256_file(tests_path) != EXPECTED_STAGE12598_TESTS:
        raise GateError("stage12598_tests_pin_drift")
    if sha256_file(transcript_path) != EXPECTED_STAGE12598_TRANSCRIPT_FILE:
        raise GateError("stage12598_transcript_file_pin_drift")
    if summary.get("decision") != "BLOCKED_EXECUTION_GATE_REQUIRED":
        raise GateError("stage12598_decision_mismatch")
    if summary.get("source_review_scope") != "preflight_only_source_review_not_execution_authorization":
        raise GateError("stage12598_source_review_scope_drift")
    if summary.get("bounded_independent_agent_source_review_result") != "PASS_NO_BLOCKER_FOR_PREFLIGHT_ONLY_SOURCE":
        raise GateError("stage12598_review_result_drift")
    if summary.get("manual_executor_preflight_source_sha256") != EXPECTED_STAGE12597_RUNNER:
        raise GateError("stage12598_runner_digest_drift")
    if summary.get("source_review_transcript_sha256") != EXPECTED_STAGE12598_TRANSCRIPT_CANONICAL:
        raise GateError("stage12598_transcript_digest_drift")
    if summary.get("stage12594_publication_generation_id") != EXPECTED_STAGE12594_GENERATION:
        raise GateError("stage12598_generation_drift")
    if summary.get("stage12594_publication_manifest_sha256") != EXPECTED_STAGE12594_MANIFEST:
        raise GateError("stage12598_manifest_drift")
    if summary.get("stage12595_slots_sha256") != EXPECTED_STAGE12595_SLOTS:
        raise GateError("stage12598_slots_drift")
    if summary.get("stage12596_private_executor_contract_sha256") != EXPECTED_STAGE12596_PRIVATE_CONTRACT:
        raise GateError("stage12598_stage12596_contract_drift")
    if sorted(summary.get("downstream_blockers", [])) != sorted(REQUIRED_STAGE12598_BLOCKERS):
        raise GateError("stage12598_blocker_set_mismatch")
    for field in ("execute_path_enabled", "this_stage_runs_replay", "executor_command_manifest_present", "raw_replay_evidence_present"):
        if summary.get(field) is not False or contract.get(field) is not False:
            raise GateError("stage12598_boundary_drift:" + field)
    if summary.get("execution_request_ready_count") != 0 or contract.get("execution_request_ready_count") != 0:
        raise GateError("stage12598_execution_request_count_drift")
    if pointer.get("private_source_review_sha256") != stable_hash(private_review):
        raise GateError("stage12598_private_review_pointer_mismatch")
    if pointer.get("source_review_transcript_sha256") != EXPECTED_STAGE12598_TRANSCRIPT_CANONICAL:
        raise GateError("stage12598_pointer_transcript_digest_drift")
    for label, record in (("summary", summary), ("contract", contract), ("pointer", pointer), ("private_review", private_review)):
        check_false(record, "stage12598_" + label)
    return {"summary": summary, "contract": contract, "pointer": pointer, "private_review": private_review, "transcript": transcript}


def build_gate_packet(stage12598: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    gate_intake = {
        "record_type": "stage12599_private_execution_gate_intake_v1",
        "gate_request_result": "denied_preflight_only_source",
        "stage12598_summary_sha256": EXPECTED_STAGE12598_SUMMARY,
        "stage12598_pointer_sha256": EXPECTED_STAGE12598_POINTER,
        "reviewed_preflight_source_sha256": EXPECTED_STAGE12597_RUNNER,
        "source_review_transcript_sha256": EXPECTED_STAGE12598_TRANSCRIPT_CANONICAL,
        "gate_reason": "reviewed_source_has_no_execute_path_and_review_scope_was_preflight_only",
        "required_next_source_step": "implement_execution_capable_manual_runner_source_as_separate_stage",
        "required_next_review_step": "independent_review_of_execution_capable_source_before_any_execute_path",
        "requested_slots": 2,
        "execution_request_ready_count": 0,
        "execute_path_enabled": False,
        "this_stage_runs_replay": False,
        "executor_command_manifest_present": False,
        "raw_replay_evidence_present": False,
        **no_claim_fields(),
    }
    public_contract = {
        "record_type": "stage12599_public_execution_gate_intake_contract_v1",
        "stage12594_publication_generation_id": stage12598["summary"]["stage12594_publication_generation_id"],
        "stage12594_publication_manifest_sha256": stage12598["summary"]["stage12594_publication_manifest_sha256"],
        "stage12595_slots_sha256": stage12598["summary"]["stage12595_slots_sha256"],
        "manual_executor_preflight_source_sha256": EXPECTED_STAGE12597_RUNNER,
        "source_review_transcript_sha256": EXPECTED_STAGE12598_TRANSCRIPT_CANONICAL,
        "execution_gate_requested": True,
        "execution_gate_granted": False,
        "gate_request_result": "denied_preflight_only_source",
        "execution_capable_source_present": False,
        "independent_execution_capable_source_review_present": False,
        "execute_path_enabled": False,
        "this_stage_runs_replay": False,
        "executor_command_manifest_present": False,
        "raw_replay_evidence_present": False,
        "execution_request_ready_count": 0,
        "claim_boundary": {
            "replay_success_claim": "forbidden_until_manual_executor_raw_artifacts_exist",
            "level3_claim": "forbidden_until_causal_candidate_and_stop_continue_provenance_exist",
            "training_admission": "separate_future_gate_required",
        },
        **no_claim_fields(),
    }
    summary = {
        "record_type": "stage12599_public_execution_gate_intake_summary_v1",
        "stage": STAGE,
        "decision": "BLOCKED_EXECUTION_CAPABLE_SOURCE_REQUIRED",
        "stage12594_publication_generation_id": stage12598["summary"]["stage12594_publication_generation_id"],
        "stage12594_publication_manifest_sha256": stage12598["summary"]["stage12594_publication_manifest_sha256"],
        "stage12595_slots_sha256": stage12598["summary"]["stage12595_slots_sha256"],
        "manual_executor_preflight_source_sha256": EXPECTED_STAGE12597_RUNNER,
        "source_review_transcript_sha256": EXPECTED_STAGE12598_TRANSCRIPT_CANONICAL,
        "execution_gate_requested": True,
        "execution_gate_granted": False,
        "gate_request_result": "denied_preflight_only_source",
        "execution_capable_source_present": False,
        "independent_execution_capable_source_review_present": False,
        "execute_path_enabled": False,
        "this_stage_runs_replay": False,
        "executor_command_manifest_present": False,
        "raw_replay_evidence_present": False,
        "manual_replay_slot_count": 2,
        "execution_request_ready_count": 0,
        "stage12600_allowed": False,
        "level3_atom_count": 0,
        "downstream_blockers": [
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
        ],
        **no_claim_fields(),
    }
    for label, record in (("summary", summary), ("public_contract", public_contract)):
        check_false(record, "stage12599_" + label)
        assert_public_sanitized(record, "stage12599_" + label)
    check_false(gate_intake, "stage12599_gate_intake")
    return summary, public_contract, gate_intake


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    stage12598 = load_stage12598()
    summary, public_contract, gate_intake = build_gate_packet(stage12598)
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "contract.json", public_contract)
    write_json(out / "private/execution_gate_intake.json", gate_intake)
    pointer = {
        "record_type": "stage12599_public_private_execution_gate_pointer_v1",
        "private_execution_gate_intake_sha256": stable_hash(gate_intake),
        "stage12598_summary_sha256": EXPECTED_STAGE12598_SUMMARY,
        "stage12598_pointer_sha256": EXPECTED_STAGE12598_POINTER,
        "source_review_transcript_sha256": EXPECTED_STAGE12598_TRANSCRIPT_CANONICAL,
        **no_claim_fields(),
    }
    check_false(pointer, "stage12599_pointer")
    assert_public_sanitized(pointer, "stage12599_pointer")
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
