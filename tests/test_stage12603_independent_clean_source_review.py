import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12603_independent_clean_source_review.py"
SPEC = importlib.util.spec_from_file_location("stage12603", SCRIPT)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


def read_json(path: Path):
    return json.loads(path.read_text())


def assert_false_boundaries(record, require_all=True):
    for field in (
        "implementation_ready", "stage12595_allowed", "authorizes_execution", "execution_allowed",
        "execution_performed", "replay_trustworthy", "level_3_materialized", "training_admitted",
        "strict_eval_admitted", "sealed_eval_admitted", "strict_eval_eligible", "sealed_eval_eligible",
        "admission_allowed", "training_allowed", "ranking_allowed", "positive_stop",
    ):
        if require_all or field in record:
            assert record[field] is False


def assert_public_sanitized(record):
    encoded = json.dumps(record, sort_keys=True)
    for forbidden in stage.PUBLIC_FORBIDDEN_SUBSTRINGS:
        assert forbidden not in encoded


def test_load_stage12602_pins_clean_review_request_packet():
    loaded = stage.load_stage12602()
    summary = loaded["summary"]
    contract = loaded["contract"]
    pointer = loaded["pointer"]
    private = loaded["private"]
    assert summary["decision"] == "BLOCKED_INDEPENDENT_EXECUTION_CAPABLE_SOURCE_REVIEW_REQUIRED"
    assert summary["source_review_request_ready"] is True
    assert summary["duplicate_definition_ambiguity_present"] is False
    assert summary["execute_reviewed_slot_definition_count"] == 1
    assert summary["implemented_reviewable_functions_assignment_count"] == 1
    assert summary["reviewed_execution_capable_source_present"] is False
    assert summary["independent_execution_capable_source_review_present"] is False
    assert summary["execute_path_enabled"] is False
    assert summary["execution_gate_granted"] is False
    assert summary["execution_request_ready_count"] == 0
    assert summary["this_stage_runs_replay"] is False
    assert summary["executor_command_manifest_present"] is False
    assert summary["raw_replay_evidence_present"] is False
    assert pointer["private_clean_candidate_source_packet_sha256"] == stage.stable_hash(private)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_load_review_transcript_is_independent_source_review_not_execution():
    transcript = stage.load_review_transcript()
    assert transcript["review_result"] == "PASS_NO_BLOCKER_FOR_CLEAN_CANDIDATE_SOURCE_PACKET"
    assert transcript["review_scope"] == "stage12602_clean_candidate_source_packet_only_no_execution_authorization"
    assert transcript["review_edits_performed"] is False
    assert transcript["review_execution_performed"] is False
    assert transcript["independent_execution_capable_source_review_present"] is True
    assert transcript["independent_execution_capable_source_review_passed"] is True
    assert transcript["reviewed_execution_capable_source_present"] is True
    assert transcript["authorizes_execution"] is False
    assert transcript["execution_allowed"] is False
    assert transcript["execution_performed"] is False
    assert_false_boundaries(transcript, require_all=False)


def test_build_review_packet_advances_source_review_only():
    stage12602 = stage.load_stage12602()
    transcript = stage.load_review_transcript()
    summary, contract, private = stage.build_review_packet(stage12602, transcript)
    assert summary["decision"] == "BLOCKED_EXECUTION_GATE_REQUIRED"
    assert summary["source_cleanup_successor_reviewed"] is True
    assert summary["reviewed_execution_capable_source_present"] is True
    assert summary["independent_execution_capable_source_review_present"] is True
    assert summary["independent_execution_capable_source_review_passed"] is True
    assert summary["execute_path_enabled"] is False
    assert summary["execution_gate_granted"] is False
    assert summary["execution_request_ready_count"] == 0
    assert summary["this_stage_runs_replay"] is False
    assert summary["executor_command_manifest_present"] is False
    assert summary["raw_replay_evidence_present"] is False
    assert summary["stage12604_allowed"] is False
    assert "execution_gate_not_granted_for_reviewed_source" in summary["downstream_blockers"]
    assert "execution_request_materials_absent" in summary["downstream_blockers"]
    assert contract["independent_execution_capable_source_review_passed"] is True
    assert private["review_result"] == "PASS_NO_BLOCKER_FOR_CLEAN_CANDIDATE_SOURCE_PACKET"
    assert private["review_execution_performed"] is False
    for record in (summary, contract, private):
        assert_false_boundaries(record)
    for public_record in (summary, contract):
        assert_public_sanitized(public_record)


def test_build_writes_only_independent_review_packet(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/independent_clean_source_review.json",
        "summary.json",
    ]
    assert not any("stdout.raw" in name or "stderr.raw" in name or "pytest" in name for name in emitted)
    assert not any("clone" in name or "repo" in name or "command" in name for name in emitted)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/independent_clean_source_review.json")
    assert pointer["private_independent_clean_source_review_sha256"] == stage.stable_hash(private)
    assert pointer["review_transcript_sha256"] == stage.EXPECTED_REVIEW_TRANSCRIPT
    for public_record in (summary, contract, pointer):
        assert_public_sanitized(public_record)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_generated_stage12603_artifacts_match_review_boundary():
    out = stage.OUT
    summary = read_json(out / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/independent_clean_source_review.json")
    assert summary == external
    assert summary["decision"] == "BLOCKED_EXECUTION_GATE_REQUIRED"
    assert summary["reviewed_execution_capable_source_present"] is True
    assert summary["independent_execution_capable_source_review_present"] is True
    assert summary["independent_execution_capable_source_review_passed"] is True
    assert summary["execute_path_enabled"] is False
    assert summary["execution_gate_granted"] is False
    assert summary["execution_request_ready_count"] == 0
    assert summary["this_stage_runs_replay"] is False
    assert summary["executor_command_manifest_present"] is False
    assert summary["raw_replay_evidence_present"] is False
    assert summary["stage12604_allowed"] is False
    assert pointer["private_independent_clean_source_review_sha256"] == stage.stable_hash(private)
    assert contract["independent_execution_capable_source_review_passed"] is True
    assert private["review_execution_performed"] is False
    for public_record in (summary, contract, pointer):
        assert_public_sanitized(public_record)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_stage12603_rejects_transcript_that_authorizes_execution(tmp_path):
    transcript = stage.load_review_transcript()
    drifted = dict(transcript)
    drifted["authorizes_execution"] = True
    path = tmp_path / "transcript.json"
    path.write_text(json.dumps(drifted, sort_keys=True), encoding="utf-8")
    with pytest.raises(stage.GateError, match="stage12603_review_transcript_pin_drift"):
        stage.load_review_transcript(path)
