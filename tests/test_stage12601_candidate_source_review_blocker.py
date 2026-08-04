import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12601_candidate_source_review_blocker.py"
RUNNER = ROOT / "scripts/run_stage12600_candidate_manual_replay_executor.py"
SPEC = importlib.util.spec_from_file_location("stage12601", SCRIPT)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


def read_json(path: Path):
    return json.loads(path.read_text())


def assert_false_boundaries(record):
    for field in (
        "implementation_ready", "stage12595_allowed", "authorizes_execution", "execution_allowed",
        "execution_performed", "replay_trustworthy", "level_3_materialized", "training_admitted",
        "strict_eval_admitted", "sealed_eval_admitted", "strict_eval_eligible", "sealed_eval_eligible",
        "admission_allowed", "training_allowed", "ranking_allowed", "positive_stop",
    ):
        assert record[field] is False


def assert_public_sanitized(record):
    encoded = json.dumps(record, sort_keys=True)
    for forbidden in stage.PUBLIC_FORBIDDEN_SUBSTRINGS:
        assert forbidden not in encoded


def test_load_stage12600_pins_current_blocked_candidate_packet():
    loaded = stage.load_stage12600()
    summary = loaded["summary"]
    contract = loaded["contract"]
    pointer = loaded["pointer"]
    private = loaded["private"]
    assert summary["decision"] == "BLOCKED_INDEPENDENT_EXECUTION_CAPABLE_SOURCE_REVIEW_REQUIRED"
    assert summary["candidate_execution_capable_source_present"] is True
    assert summary["candidate_execution_implementation_present"] is True
    assert summary["reviewed_execution_capable_source_present"] is False
    assert summary["independent_execution_capable_source_review_present"] is False
    assert summary["execute_path_enabled"] is False
    assert summary["execution_gate_granted"] is False
    assert summary["execution_request_ready_count"] == 0
    assert summary["this_stage_runs_replay"] is False
    assert summary["executor_command_manifest_present"] is False
    assert summary["raw_replay_evidence_present"] is False
    assert pointer["candidate_runner_sha256"] == stage.sha256_file(RUNNER)
    assert pointer["private_candidate_source_packet_sha256"] == stage.stable_hash(private)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_analyze_runner_source_detects_duplicate_execute_reviewed_slot_definitions():
    review = stage.analyze_runner_source()
    assert review["runner_sha256"] == stage.EXPECTED_STAGE12600_RUNNER
    assert review["execute_reviewed_slot_definition_count"] == 2
    assert len(review["execute_reviewed_slot_definition_lines"]) == 2
    assert review["execute_reviewed_slot_definition_lines"] == sorted(review["execute_reviewed_slot_definition_lines"])
    assert review["duplicate_definition_ambiguity_present"] is True
    assert review["review_blocker"] == "duplicate_execute_reviewed_slot_definitions"
    assert "apply_exact_production_patch" in review["last_execute_reviewed_slot_calls"]
    assert "assert_final_reverts_initial" in review["last_execute_reviewed_slot_calls"]
    assert review["implemented_reviewable_functions_assignment_count"] == 2
    assert_false_boundaries(review)


def test_build_review_packet_blocks_independent_review_without_execution():
    stage12600 = stage.load_stage12600()
    source_review = stage.analyze_runner_source()
    summary, contract, private = stage.build_review_packet(stage12600, source_review)
    assert summary["decision"] == "BLOCKED_SOURCE_CLEANUP_REQUIRED_BEFORE_INDEPENDENT_REVIEW"
    assert summary["source_review_attempted"] is True
    assert summary["source_cleanup_required_before_independent_review"] is True
    assert summary["source_ambiguity_blocker_present"] is True
    assert summary["reviewed_execution_capable_source_present"] is False
    assert summary["independent_execution_capable_source_review_present"] is False
    assert summary["independent_execution_capable_source_review_passed"] is False
    assert summary["execute_path_enabled"] is False
    assert summary["execution_gate_granted"] is False
    assert summary["execution_request_ready_count"] == 0
    assert summary["this_stage_runs_replay"] is False
    assert summary["executor_command_manifest_present"] is False
    assert summary["raw_replay_evidence_present"] is False
    assert summary["stage12602_allowed"] is False
    assert "duplicate_execute_reviewed_slot_definition_ambiguity" in summary["downstream_blockers"]
    assert contract["review_blocker_sha256"] == stage.stable_hash(private)
    assert private["review_result"] == "BLOCKED_DUPLICATE_EXECUTE_REVIEWED_SLOT_DEFINITIONS"
    assert private["independent_review_passed"] is False
    assert private["execute_reviewed_slot_definition_count"] == 2
    for record in (summary, contract, private):
        assert_false_boundaries(record)
    for public_record in (summary, contract):
        assert_public_sanitized(public_record)


def test_build_writes_only_review_blocker_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/candidate_source_review_blocker.json",
        "summary.json",
    ]
    assert not any("stdout.raw" in name or "stderr.raw" in name or "pytest" in name for name in emitted)
    assert not any("clone" in name or "repo" in name or "command" in name for name in emitted)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/candidate_source_review_blocker.json")
    assert pointer["private_candidate_source_review_blocker_sha256"] == stage.stable_hash(private)
    assert pointer["source_review_static_analysis_sha256"] == stage.stable_hash(stage.analyze_runner_source())
    assert contract["review_blocker_sha256"] == stage.stable_hash(private)
    for public_record in (summary, contract, pointer):
        assert_public_sanitized(public_record)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_generated_stage12601_artifacts_match_current_blocker_state():
    out = stage.OUT
    summary = read_json(out / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/candidate_source_review_blocker.json")
    assert summary == external
    assert summary["decision"] == "BLOCKED_SOURCE_CLEANUP_REQUIRED_BEFORE_INDEPENDENT_REVIEW"
    assert summary["source_ambiguity_blocker_present"] is True
    assert summary["reviewed_execution_capable_source_present"] is False
    assert summary["independent_execution_capable_source_review_present"] is False
    assert summary["execute_path_enabled"] is False
    assert summary["execution_gate_granted"] is False
    assert summary["execution_request_ready_count"] == 0
    assert summary["this_stage_runs_replay"] is False
    assert summary["executor_command_manifest_present"] is False
    assert summary["raw_replay_evidence_present"] is False
    assert private["execute_reviewed_slot_definition_count"] == 2
    assert pointer["private_candidate_source_review_blocker_sha256"] == stage.stable_hash(private)
    assert contract["review_blocker_sha256"] == stage.stable_hash(private)
    for public_record in (summary, contract, pointer):
        assert_public_sanitized(public_record)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_stage12601_refuses_to_build_if_duplicate_blocker_disappears():
    stage12600 = stage.load_stage12600()
    source_review = stage.analyze_runner_source()
    source_review = dict(source_review)
    source_review["duplicate_definition_ambiguity_present"] = False
    source_review["execute_reviewed_slot_definition_count"] = 1
    with pytest.raises(stage.GateError, match="stage12601_expected_duplicate_definition_blocker_missing"):
        stage.build_review_packet(stage12600, source_review)
