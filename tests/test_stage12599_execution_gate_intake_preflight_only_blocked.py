import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12599_execution_gate_intake_preflight_only_blocked.py"
SPEC = importlib.util.spec_from_file_location("stage12599", SCRIPT)
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


def copy_stage12598(tmp_path: Path):
    root = tmp_path / "stage12598"
    copy_tree(stage.S12598, root)
    external = tmp_path / "stage12598_summary.json"
    external.write_bytes(stage.S12598_EXTERNAL.read_bytes())
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


def test_load_stage12598_pins_transcript_backed_source_review():
    loaded = stage.load_stage12598()
    assert loaded["summary"]["decision"] == "BLOCKED_EXECUTION_GATE_REQUIRED"
    assert loaded["summary"]["bounded_independent_agent_source_review_result"] == "PASS_NO_BLOCKER_FOR_PREFLIGHT_ONLY_SOURCE"
    assert loaded["summary"]["source_review_transcript_sha256"] == stage.EXPECTED_STAGE12598_TRANSCRIPT_CANONICAL
    assert loaded["summary"]["execute_path_enabled"] is False
    assert loaded["summary"]["execution_request_ready_count"] == 0
    assert_false_boundaries(loaded["summary"])
    assert_false_boundaries(loaded["contract"])


def test_load_stage12598_rejects_pin_drift(tmp_path):
    root, external = copy_stage12598(tmp_path)
    summary = read_json(root / "summary.json")
    summary["execute_path_enabled"] = True
    (root / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    external.write_text(json.dumps(summary), encoding="utf-8")
    with pytest.raises(stage.GateError, match="stage12598_summary_pin_drift"):
        stage.load_stage12598(root, external)


def test_build_gate_packet_denies_execution_for_preflight_only_source():
    loaded = stage.load_stage12598()
    summary, contract, intake = stage.build_gate_packet(loaded)
    assert summary["decision"] == "BLOCKED_EXECUTION_CAPABLE_SOURCE_REQUIRED"
    assert summary["execution_gate_requested"] is True
    assert summary["execution_gate_granted"] is False
    assert summary["gate_request_result"] == "denied_preflight_only_source"
    assert summary["execution_capable_source_present"] is False
    assert summary["independent_execution_capable_source_review_present"] is False
    assert summary["execute_path_enabled"] is False
    assert summary["this_stage_runs_replay"] is False
    assert summary["executor_command_manifest_present"] is False
    assert summary["raw_replay_evidence_present"] is False
    assert summary["execution_request_ready_count"] == 0
    assert summary["stage12600_allowed"] is False
    assert "execution_capable_manual_runner_source_absent" in summary["downstream_blockers"]
    assert "independent_execution_capable_source_review_absent" in summary["downstream_blockers"]
    assert "manual_replay_execution_not_performed" in summary["downstream_blockers"]
    assert contract["execution_gate_granted"] is False
    assert contract["claim_boundary"]["training_admission"] == "separate_future_gate_required"
    assert intake["gate_request_result"] == "denied_preflight_only_source"
    assert intake["required_next_source_step"] == "implement_execution_capable_manual_runner_source_as_separate_stage"
    assert intake["required_next_review_step"] == "independent_review_of_execution_capable_source_before_any_execute_path"
    for record in (summary, contract, intake):
        assert_false_boundaries(record)
    for public_record in (summary, contract):
        assert_public_sanitized(public_record)


def test_build_writes_blocked_gate_intake_without_execution_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/execution_gate_intake.json",
        "summary.json",
    ]
    assert not any("stdout.raw" in name or "stderr.raw" in name or "pytest" in name for name in emitted)
    assert not any("clone" in name or "repo" in name or "command" in name for name in emitted)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    intake = read_json(out / "private/execution_gate_intake.json")
    assert pointer["private_execution_gate_intake_sha256"] == stage.stable_hash(intake)
    assert pointer["stage12598_summary_sha256"] == stage.EXPECTED_STAGE12598_SUMMARY
    assert pointer["stage12598_pointer_sha256"] == stage.EXPECTED_STAGE12598_POINTER
    assert intake["execution_request_ready_count"] == 0
    assert intake["execute_path_enabled"] is False
    for public_record in (summary, contract, pointer):
        assert_public_sanitized(public_record)
    for record in (summary, contract, pointer, intake):
        assert_false_boundaries(record)


def test_stage12599_generated_artifacts_match_current_private_gate_digest():
    out = stage.OUT
    summary = read_json(out / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    intake = read_json(out / "private/execution_gate_intake.json")
    assert summary == external
    assert pointer["private_execution_gate_intake_sha256"] == stage.stable_hash(intake)
    assert summary["decision"] == "BLOCKED_EXECUTION_CAPABLE_SOURCE_REQUIRED"
    assert summary["execution_gate_granted"] is False
    assert summary["execution_capable_source_present"] is False
    assert summary["independent_execution_capable_source_review_present"] is False
    assert summary["execute_path_enabled"] is False
    assert summary["this_stage_runs_replay"] is False
    assert summary["executor_command_manifest_present"] is False
    assert summary["raw_replay_evidence_present"] is False
    assert summary["execution_request_ready_count"] == 0
    assert contract["execution_gate_granted"] is False
    assert contract["execution_capable_source_present"] is False
    assert contract["independent_execution_capable_source_review_present"] is False
    assert contract["execute_path_enabled"] is False
    assert contract["this_stage_runs_replay"] is False
    assert contract["executor_command_manifest_present"] is False
    assert contract["raw_replay_evidence_present"] is False
    assert contract["execution_request_ready_count"] == 0
    for public_record in (summary, contract, pointer):
        assert_public_sanitized(public_record)
    for record in (summary, contract, pointer, intake):
        assert_false_boundaries(record)
