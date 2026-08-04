import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12598_independent_agent_executor_source_review.py"
SPEC = importlib.util.spec_from_file_location("stage12598", SCRIPT)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


def read_json(path: Path):
    return json.loads(path.read_text())


def copy_tree(src: Path, dst: Path):
    for path in src.rglob("*"):
        if path.is_file():
            target = dst / path.relative_to(src)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())


def copy_stage12597(tmp_path: Path):
    root = tmp_path / "stage12597"
    copy_tree(stage.S12597, root)
    external = tmp_path / "stage12597_summary.json"
    external.write_bytes(stage.S12597_EXTERNAL.read_bytes())
    return root, external


def assert_false_boundaries(record):
    for field in (
        "authorizes_execution", "execution_allowed", "execution_performed", "replay_trustworthy",
        "level_3_materialized", "training_admitted", "strict_eval_admitted", "sealed_eval_admitted",
        "strict_eval_eligible", "sealed_eval_eligible", "admission_allowed", "training_allowed",
        "ranking_allowed", "positive_stop",
    ):
        assert record[field] is False


def assert_public_sanitized(record):
    encoded = json.dumps(record, sort_keys=True)
    for forbidden in stage.PUBLIC_FORBIDDEN_SUBSTRINGS:
        assert forbidden not in encoded


def test_load_stage12597_requires_current_source_and_generated_artifact_pins():
    loaded = stage.load_stage12597()
    assert loaded["summary"]["decision"] == "BLOCKED_EXECUTOR_SOURCE_REVIEW_REQUIRED"
    assert loaded["summary"]["manual_executor_preflight_source_sha256"] == stage.EXPECTED_STAGE12597_RUNNER
    assert loaded["pointer"]["private_source_review_intake_sha256"] == stage.EXPECTED_STAGE12597_REVIEW_INTAKE
    assert loaded["summary"]["execute_path_enabled"] is False
    assert loaded["summary"]["independent_executor_source_review_present"] is False
    assert_false_boundaries(loaded["summary"])
    assert_false_boundaries(loaded["contract"])


def test_load_stage12597_rejects_artifact_pin_drift(tmp_path):
    root, external = copy_stage12597(tmp_path)
    summary = read_json(root / "summary.json")
    summary["manual_executor_preflight_source_sha256"] = "0" * 64
    (root / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    external.write_text(json.dumps(summary), encoding="utf-8")
    with pytest.raises(stage.GateError, match="stage12597_summary_pin_drift"):
        stage.load_stage12597(root, external)


def test_load_review_transcript_requires_pinned_hypatia_result(tmp_path):
    transcript = stage.load_review_transcript()
    assert transcript["reviewer_agent_id"] == stage.REVIEW_AGENT_ID
    assert transcript["review_result"] == stage.REVIEW_RESULT
    assert transcript["reviewed_runner_sha256"] == stage.EXPECTED_STAGE12597_RUNNER
    drifted = tmp_path / "review.json"
    drifted.write_text(json.dumps({**transcript, "review_result": "BLOCKER"}), encoding="utf-8")
    with pytest.raises(stage.GateError, match="stage12598_review_transcript_pin_drift"):
        stage.load_review_transcript(drifted)


def test_build_review_packet_records_bounded_agent_review_without_execution_authority():
    loaded = stage.load_stage12597()
    transcript = stage.load_review_transcript()
    summary, contract, private_review = stage.build_review_packet(loaded, transcript)
    assert summary["decision"] == "BLOCKED_EXECUTION_GATE_REQUIRED"
    assert summary["bounded_independent_agent_source_review_present"] is True
    assert summary["bounded_independent_agent_source_review_result"] == stage.REVIEW_RESULT
    assert summary["source_review_scope"] == "preflight_only_source_review_not_execution_authorization"
    assert summary["execute_path_enabled"] is False
    assert summary["this_stage_runs_replay"] is False
    assert summary["executor_command_manifest_present"] is False
    assert summary["raw_replay_evidence_present"] is False
    assert summary["execution_request_ready_count"] == 0
    assert summary["stage12599_allowed"] is False
    assert "independent_executor_source_review_absent" not in summary["downstream_blockers"]
    assert "execute_path_disabled_pending_execution_gate" in summary["downstream_blockers"]
    assert contract["bounded_independent_agent_source_review_result"] == stage.REVIEW_RESULT
    assert contract["claim_boundary"]["training_admission"] == "separate_future_gate_required"
    assert private_review["source_review_transcript_sha256"] == stage.EXPECTED_REVIEW_TRANSCRIPT
    assert private_review["reviewer_agent_id"] == stage.REVIEW_AGENT_ID
    assert private_review["review_result"] == stage.REVIEW_RESULT
    assert "bounded_agent_review_not_external_security_audit" in private_review["review_limits"]
    assert "preflight_only_source_review_not_execution_authorization" in private_review["review_limits"]
    for record in (summary, contract, private_review):
        assert_false_boundaries(record)
    for public_record in (summary, contract):
        assert_public_sanitized(public_record)


def test_build_writes_current_review_artifacts_and_pointer(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/bounded_independent_agent_source_review.json",
        "summary.json",
    ]
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private_review = read_json(out / "private/bounded_independent_agent_source_review.json")
    assert pointer["source_review_transcript_sha256"] == stage.EXPECTED_REVIEW_TRANSCRIPT
    assert pointer["private_source_review_sha256"] == stage.stable_hash(private_review)
    assert pointer["manual_executor_preflight_source_sha256"] == stage.EXPECTED_STAGE12597_RUNNER
    assert pointer["stage12597_summary_sha256"] == stage.EXPECTED_STAGE12597_SUMMARY
    assert pointer["stage12597_pointer_sha256"] == stage.EXPECTED_STAGE12597_POINTER
    assert summary["bounded_independent_agent_source_review_result"] == stage.REVIEW_RESULT
    assert private_review["review_result"] == stage.REVIEW_RESULT
    for public_record in (summary, contract, pointer):
        assert_public_sanitized(public_record)
    for record in (summary, contract, pointer, private_review):
        assert_false_boundaries(record)


def test_stage12598_generated_artifacts_match_current_private_review_digest():
    out = stage.OUT
    summary = read_json(out / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private_review = read_json(out / "private/bounded_independent_agent_source_review.json")
    assert summary == external
    assert pointer["source_review_transcript_sha256"] == stage.EXPECTED_REVIEW_TRANSCRIPT
    assert pointer["private_source_review_sha256"] == stage.stable_hash(private_review)
    assert pointer["manual_executor_preflight_source_sha256"] == stage.EXPECTED_STAGE12597_RUNNER
    assert summary["decision"] == "BLOCKED_EXECUTION_GATE_REQUIRED"
    assert summary["bounded_independent_agent_source_review_present"] is True
    assert summary["execute_path_enabled"] is False
    assert summary["this_stage_runs_replay"] is False
    assert summary["executor_command_manifest_present"] is False
    assert summary["raw_replay_evidence_present"] is False
    assert summary["execution_request_ready_count"] == 0
    for public_record in (summary, contract, pointer):
        assert_public_sanitized(public_record)
    for record in (summary, contract, pointer, private_review):
        assert_false_boundaries(record)
