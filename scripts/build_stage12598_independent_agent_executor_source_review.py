#!/usr/bin/env python3
"""Build Stage12598 bounded independent-agent source review packet.

This stage records the actual bounded subagent review of the Stage12597
preflight-only executor source. It does not enable execution and does not claim
that replay has run.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12598_independent_agent_executor_source_review"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
S12597 = ROOT / "runs/local/artifacts/stage12597_manual_executor_source_preflight"
S12597_EXTERNAL = ROOT / "runs/summaries/stage12597_manual_executor_source_preflight.json"
RUNNER = ROOT / "scripts/run_stage12597_manual_trusted_replay_executor.py"
BUILDER = ROOT / "scripts/build_stage12597_manual_executor_source_preflight.py"
TESTS = ROOT / "tests/test_stage12597_manual_executor_source_preflight.py"
REVIEW_TRANSCRIPT = ROOT / "runs/local/private/stage12598_hypatia_source_review_transcript.json"
EXPECTED_STAGE12594_GENERATION = "91d0cda6e9acdf2e09c4d04b7d8e00159351bedf1ef0e7f70c4912d48c34475d"
EXPECTED_STAGE12594_MANIFEST = "5f5353b63591f77433a6a0a01141211796906ef13c02c2569c48f65a59c5a856"
EXPECTED_STAGE12595_SLOTS = "8ddfdfb0872c8cb74a46f0041801bced7e674228d74af98b30ce7631afebe3a0"
EXPECTED_STAGE12596_PRIVATE_CONTRACT = "f880781f4462211c29b071941e8105064f138a665647bffc5bb00c90c1d56edc"
EXPECTED_STAGE12597_RUNNER = "1213902efcaa177c6426eae590f1df596c6c59ed43a3caef09983e49ce37f5f8"
EXPECTED_STAGE12597_BUILDER = "16b75a77871714d6a90cd39018a092ea84abdc9fd50b3583622e4baf6b9462e7"
EXPECTED_STAGE12597_TESTS = "4a3c37dcca88da8d4bfeb8fc4560509d55a4dc2f5b30551faa973e791a1ef54b"
EXPECTED_STAGE12597_SUMMARY = "8e84f39babc8d620fa091b9b4969568ec16783073fa288bcf28b91d75272128a"
EXPECTED_STAGE12597_CONTRACT = "a77c512802c87f7d294788eca44d328bc0847b21b50b2cd0add751d2593820e6"
EXPECTED_STAGE12597_POINTER = "355f9cd8b77de4d765b959916acf2309f14a106719c98217870db0586a04d415"
EXPECTED_STAGE12597_REVIEW_INTAKE = "943b26a79a1cde2498a58ccd3a65b131ecebc4e5993b8baeaf8ac3ff886a1cdd"
REVIEW_AGENT_ID = "019f904f-d0fa-7580-aa34-590e3d29ba87"
REVIEW_AGENT_NICKNAME = "Hypatia"
REVIEW_RESULT = "PASS_NO_BLOCKER_FOR_PREFLIGHT_ONLY_SOURCE"
EXPECTED_REVIEW_TRANSCRIPT = "00abcd7749987123c810b76e432f1983ab5dc8b72a6c19a78b24bdff534719f9"
FALSE_FIELDS = (
    "authorizes_execution", "execution_allowed", "execution_performed", "replay_trustworthy",
    "level_3_materialized", "training_admitted", "strict_eval_admitted", "sealed_eval_admitted",
    "strict_eval_eligible", "sealed_eval_eligible", "admission_allowed", "training_allowed",
    "ranking_allowed", "positive_stop", "stage12599_allowed",
)
PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "selector", "raw_stream", "stdout.raw", "stderr.raw", "before_commit_oid",
    "after_commit_oid", "production_path", "production_patch_sha256", "manual_executor_slot_contracts",
)
REQUIRED_STAGE12597_BLOCKERS = (
    "independent_executor_source_review_absent",
    "execute_path_disabled_pending_independent_review",
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


def load_stage12597(
    root: Path = S12597,
    external_path: Path = S12597_EXTERNAL,
    runner_path: Path = RUNNER,
    builder_path: Path = BUILDER,
    tests_path: Path = TESTS,
) -> dict[str, Any]:
    summary = read_json(root / "summary.json")
    external = read_json(external_path)
    contract = read_json(root / "contract.json")
    pointer = read_json(root / "digest_pointer.json")
    review_intake = read_json(root / "private/executor_source_review_intake.json")
    if summary != external:
        raise GateError("stage12597_external_summary_mismatch")
    if stable_hash(summary) != EXPECTED_STAGE12597_SUMMARY:
        raise GateError("stage12597_summary_pin_drift")
    if stable_hash(contract) != EXPECTED_STAGE12597_CONTRACT:
        raise GateError("stage12597_contract_pin_drift")
    if stable_hash(pointer) != EXPECTED_STAGE12597_POINTER:
        raise GateError("stage12597_pointer_pin_drift")
    if stable_hash(review_intake) != EXPECTED_STAGE12597_REVIEW_INTAKE:
        raise GateError("stage12597_review_intake_pin_drift")
    if sha256_file(runner_path) != EXPECTED_STAGE12597_RUNNER:
        raise GateError("stage12597_runner_source_pin_drift")
    if sha256_file(builder_path) != EXPECTED_STAGE12597_BUILDER:
        raise GateError("stage12597_builder_source_pin_drift")
    if sha256_file(tests_path) != EXPECTED_STAGE12597_TESTS:
        raise GateError("stage12597_tests_pin_drift")
    if summary.get("decision") != "BLOCKED_EXECUTOR_SOURCE_REVIEW_REQUIRED":
        raise GateError("stage12597_decision_mismatch")
    if summary.get("stage12594_publication_generation_id") != EXPECTED_STAGE12594_GENERATION:
        raise GateError("stage12597_generation_drift")
    if summary.get("stage12594_publication_manifest_sha256") != EXPECTED_STAGE12594_MANIFEST:
        raise GateError("stage12597_manifest_drift")
    if summary.get("stage12595_slots_sha256") != EXPECTED_STAGE12595_SLOTS:
        raise GateError("stage12597_slots_drift")
    if summary.get("stage12596_private_executor_contract_sha256") != EXPECTED_STAGE12596_PRIVATE_CONTRACT:
        raise GateError("stage12597_stage12596_contract_drift")
    if sorted(summary.get("downstream_blockers", [])) != sorted(REQUIRED_STAGE12597_BLOCKERS):
        raise GateError("stage12597_blocker_set_mismatch")
    for field in ("execute_path_enabled", "this_stage_runs_replay", "executor_command_manifest_present",
                  "raw_replay_evidence_present", "independent_executor_source_review_present"):
        if summary.get(field) is not False or contract.get(field) is not False:
            raise GateError("stage12597_boundary_drift:" + field)
    if summary.get("execution_request_ready_count") != 0 or contract.get("execution_request_ready_count") != 0:
        raise GateError("stage12597_execution_request_count_drift")
    if pointer.get("manual_executor_preflight_source_sha256") != EXPECTED_STAGE12597_RUNNER:
        raise GateError("stage12597_pointer_runner_digest_drift")
    if pointer.get("private_source_review_intake_sha256") != stable_hash(review_intake):
        raise GateError("stage12597_review_intake_digest_mismatch")
    for label, record in (("summary", summary), ("contract", contract), ("pointer", pointer), ("review_intake", review_intake)):
        check_false(record, "stage12597_" + label)
    return {"summary": summary, "contract": contract, "pointer": pointer, "review_intake": review_intake}


def load_review_transcript(path: Path = REVIEW_TRANSCRIPT) -> dict[str, Any]:
    transcript = read_json(path)
    if stable_hash(transcript) != EXPECTED_REVIEW_TRANSCRIPT:
        raise GateError("stage12598_review_transcript_pin_drift")
    expected = {
        "reviewer_agent_id": REVIEW_AGENT_ID,
        "reviewer_nickname": REVIEW_AGENT_NICKNAME,
        "review_result": REVIEW_RESULT,
        "review_scope": "stage12597_preflight_only_executor_source_and_artifacts",
        "reviewed_runner_sha256": EXPECTED_STAGE12597_RUNNER,
        "reviewed_builder_sha256": EXPECTED_STAGE12597_BUILDER,
        "reviewed_tests_sha256": EXPECTED_STAGE12597_TESTS,
        "reviewed_stage12597_summary_sha256": EXPECTED_STAGE12597_SUMMARY,
        "reviewed_stage12597_contract_sha256": EXPECTED_STAGE12597_CONTRACT,
        "reviewed_stage12597_pointer_sha256": EXPECTED_STAGE12597_POINTER,
        "reviewed_stage12597_review_intake_sha256": EXPECTED_STAGE12597_REVIEW_INTAKE,
    }
    for field, value in expected.items():
        if transcript.get(field) != value:
            raise GateError("stage12598_review_transcript_field_drift:" + field)
    evidence = transcript.get("evidence_inspected")
    limits = transcript.get("review_limits")
    if not isinstance(evidence, list) or len(evidence) < 5:
        raise GateError("stage12598_review_transcript_evidence_missing")
    required_limits = {
        "bounded_agent_review_not_external_security_audit",
        "preflight_only_source_review_not_execution_authorization",
        "execute_path_remains_disabled",
        "trusted_replay_not_executed",
        "raw_replay_evidence_absent",
    }
    if not isinstance(limits, list) or set(limits) != required_limits:
        raise GateError("stage12598_review_transcript_limits_mismatch")
    return transcript


def build_review_packet(
    stage12597: Mapping[str, Any],
    review_transcript: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    private_review = {
        "record_type": "stage12598_private_bounded_independent_agent_source_review_v1",
        "review_result": review_transcript["review_result"],
        "reviewer_agent_id": review_transcript["reviewer_agent_id"],
        "reviewer_nickname": review_transcript["reviewer_nickname"],
        "source_review_transcript_sha256": EXPECTED_REVIEW_TRANSCRIPT,
        "review_scope": review_transcript["review_scope"],
        "reviewed_runner_sha256": review_transcript["reviewed_runner_sha256"],
        "reviewed_builder_sha256": review_transcript["reviewed_builder_sha256"],
        "reviewed_tests_sha256": review_transcript["reviewed_tests_sha256"],
        "reviewed_stage12597_summary_sha256": review_transcript["reviewed_stage12597_summary_sha256"],
        "reviewed_stage12597_contract_sha256": review_transcript["reviewed_stage12597_contract_sha256"],
        "reviewed_stage12597_pointer_sha256": review_transcript["reviewed_stage12597_pointer_sha256"],
        "reviewed_stage12597_review_intake_sha256": review_transcript["reviewed_stage12597_review_intake_sha256"],
        "review_evidence": list(review_transcript["evidence_inspected"]),
        "review_limits": list(review_transcript["review_limits"]),
        **no_claim_fields(),
    }
    public_contract = {
        "record_type": "stage12598_public_bounded_source_review_contract_v1",
        "stage12594_publication_generation_id": stage12597["summary"]["stage12594_publication_generation_id"],
        "stage12594_publication_manifest_sha256": stage12597["summary"]["stage12594_publication_manifest_sha256"],
        "stage12595_slots_sha256": stage12597["summary"]["stage12595_slots_sha256"],
        "stage12596_private_executor_contract_sha256": stage12597["summary"]["stage12596_private_executor_contract_sha256"],
        "manual_executor_preflight_source_sha256": EXPECTED_STAGE12597_RUNNER,
        "source_review_transcript_sha256": EXPECTED_REVIEW_TRANSCRIPT,
        "bounded_independent_agent_source_review_present": True,
        "bounded_independent_agent_source_review_result": review_transcript["review_result"],
        "source_review_scope": "preflight_only_source_review_not_execution_authorization",
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
        "record_type": "stage12598_public_bounded_source_review_summary_v1",
        "stage": STAGE,
        "decision": "BLOCKED_EXECUTION_GATE_REQUIRED",
        "stage12594_publication_generation_id": stage12597["summary"]["stage12594_publication_generation_id"],
        "stage12594_publication_manifest_sha256": stage12597["summary"]["stage12594_publication_manifest_sha256"],
        "stage12595_slots_sha256": stage12597["summary"]["stage12595_slots_sha256"],
        "stage12596_private_executor_contract_sha256": stage12597["summary"]["stage12596_private_executor_contract_sha256"],
        "manual_executor_preflight_source_sha256": EXPECTED_STAGE12597_RUNNER,
        "source_review_transcript_sha256": EXPECTED_REVIEW_TRANSCRIPT,
        "bounded_independent_agent_source_review_present": True,
        "bounded_independent_agent_source_review_result": review_transcript["review_result"],
        "source_review_scope": "preflight_only_source_review_not_execution_authorization",
        "execute_path_enabled": False,
        "this_stage_runs_replay": False,
        "executor_command_manifest_present": False,
        "raw_replay_evidence_present": False,
        "manual_replay_slot_count": 2,
        "execution_request_ready_count": 0,
        "stage12599_allowed": False,
        "level3_atom_count": 0,
        "downstream_blockers": [
            "execute_path_disabled_pending_execution_gate",
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
        check_false(record, "stage12598_" + label)
        assert_public_sanitized(record, "stage12598_" + label)
    check_false(private_review, "stage12598_private_review")
    return summary, public_contract, private_review


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    stage12597 = load_stage12597()
    review_transcript = load_review_transcript()
    summary, public_contract, private_review = build_review_packet(stage12597, review_transcript)
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "contract.json", public_contract)
    write_json(out / "private/bounded_independent_agent_source_review.json", private_review)
    pointer = {
        "record_type": "stage12598_public_private_source_review_pointer_v1",
        "manual_executor_preflight_source_sha256": EXPECTED_STAGE12597_RUNNER,
        "source_review_transcript_sha256": EXPECTED_REVIEW_TRANSCRIPT,
        "private_source_review_sha256": stable_hash(private_review),
        "stage12597_summary_sha256": EXPECTED_STAGE12597_SUMMARY,
        "stage12597_pointer_sha256": EXPECTED_STAGE12597_POINTER,
        **no_claim_fields(),
    }
    check_false(pointer, "stage12598_pointer")
    assert_public_sanitized(pointer, "stage12598_pointer")
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
