import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12605_reviewed_execution_gate.py"
SPEC = importlib.util.spec_from_file_location("stage12605", SCRIPT)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


def read_json(path: Path):
    return json.loads(path.read_text())


def assert_no_replay_boundaries(record):
    for field in (
        "implementation_ready", "stage12595_allowed", "execution_performed", "replay_trustworthy",
        "level_3_materialized", "training_admitted", "strict_eval_admitted", "sealed_eval_admitted",
        "strict_eval_eligible", "sealed_eval_eligible", "admission_allowed", "training_allowed",
        "ranking_allowed", "positive_stop",
    ):
        assert record[field] is False


def assert_public_sanitized(record):
    encoded = json.dumps(record, sort_keys=True)
    for forbidden in stage.PUBLIC_FORBIDDEN_SUBSTRINGS:
        assert forbidden not in encoded


def test_load_stage12604_requires_materials_ready_but_gate_closed():
    loaded = stage.load_stage12604()
    summary = loaded["summary"]
    private = loaded["private_request"]
    manifest = loaded["command_manifest"]
    assert summary["decision"] == "BLOCKED_EXECUTION_GATE_GRANT_REQUIRED"
    assert summary["execution_request_materials_present"] is True
    assert summary["executor_command_manifest_present"] is True
    assert summary["execution_request_ready_count"] == 2
    assert private["execution_request_ready_count"] == 2
    assert summary["execution_gate_granted"] is False
    assert private["execution_gate_granted"] is False
    assert summary["execute_path_enabled"] is False
    assert summary["execution_performed"] is False
    assert summary["raw_replay_evidence_present"] is False
    assert manifest["slot_count"] == 2
    for record in (summary, loaded["contract"], loaded["pointer"], private, loaded["patch_records_file"]):
        assert_no_replay_boundaries(record)


def test_build_gate_packet_grants_only_reviewed_function_path():
    stage12604 = stage.load_stage12604()
    summary, contract, private = stage.build_gate_packet(stage12604)
    assert summary["decision"] == "EXECUTION_GATE_GRANTED_REPLAY_NOT_RUN"
    assert summary["reviewed_execution_capable_source_present"] is True
    assert summary["independent_execution_capable_source_review_passed"] is True
    assert summary["execution_request_materials_present"] is True
    assert summary["execution_request_ready_count"] == 2
    assert summary["execution_gate_granted"] is True
    assert summary["authorizes_execution"] is True
    assert summary["execution_allowed"] is True
    assert summary["reviewed_function_execute_path_enabled"] is True
    assert summary["cli_execute_entrypoint_enabled"] is False
    assert summary["manual_invocation_required"] is True
    assert summary["this_stage_runs_replay"] is False
    assert summary["execution_performed"] is False
    assert summary["raw_replay_evidence_present"] is False
    assert summary["replay_trustworthy"] is False
    assert summary["stage12606_allowed"] is False
    assert summary["stage12606_reviewed_function_replay_allowed"] is True
    assert "manual_replay_execution_not_performed" in summary["downstream_blockers"]
    assert summary["gate_scope"] == "reviewed_stage12602_execute_reviewed_slot_function_only"
    assert summary["claim_boundary"]["gate_scope"] == "reviewed_function_path_only"
    assert contract["authorizes_execution"] is True
    assert contract["gate_scope"] == "reviewed_stage12602_execute_reviewed_slot_function_only"
    assert contract["claim_boundary"]["cli_execute"] == "still_disabled"
    assert private["gate_scope"] == "reviewed_stage12602_execute_reviewed_slot_function_only"
    for record in (summary, contract, private):
        assert_no_replay_boundaries(record)
    for public_record in (summary, contract):
        assert_public_sanitized(public_record)


def test_build_writes_gate_without_replay_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/reviewed_execution_gate.json",
        "summary.json",
    ]
    assert not any("stdout.raw" in name or "stderr.raw" in name or "pytest" in name for name in emitted)
    assert not any("patches" in name or "future_evidence" in name or "snapshot" in name for name in emitted)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/reviewed_execution_gate.json")
    assert pointer["private_reviewed_execution_gate_sha256"] == stage.stable_hash(private)
    assert pointer["execution_gate_granted"] is True
    assert pointer["authorizes_execution"] is True
    assert pointer["execution_allowed"] is True
    assert pointer["execution_performed"] is False
    assert pointer["gate_scope"] == "reviewed_stage12602_execute_reviewed_slot_function_only"
    assert pointer["stage12606_allowed"] is False
    assert pointer["stage12606_reviewed_function_replay_allowed"] is True
    assert summary["execution_gate_granted"] is True
    assert summary["this_stage_runs_replay"] is False
    for public_record in (summary, contract, pointer):
        assert_public_sanitized(public_record)
    for record in (summary, contract, pointer, private):
        assert_no_replay_boundaries(record)


def test_generated_stage12605_artifacts_match_current_gate_boundary():
    out = stage.OUT
    summary = read_json(out / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/reviewed_execution_gate.json")
    assert summary == external
    assert summary["decision"] == "EXECUTION_GATE_GRANTED_REPLAY_NOT_RUN"
    assert summary["execution_gate_granted"] is True
    assert summary["authorizes_execution"] is True
    assert summary["execution_allowed"] is True
    assert summary["reviewed_function_execute_path_enabled"] is True
    assert summary["cli_execute_entrypoint_enabled"] is False
    assert summary["execution_request_ready_count"] == 2
    assert summary["this_stage_runs_replay"] is False
    assert summary["execution_performed"] is False
    assert summary["raw_replay_evidence_present"] is False
    assert summary["replay_trustworthy"] is False
    assert summary["stage12606_allowed"] is False
    assert summary["stage12606_reviewed_function_replay_allowed"] is True
    assert pointer["private_reviewed_execution_gate_sha256"] == stage.stable_hash(private)
    assert contract["execution_gate_granted"] is True
    assert private["manual_invocation_required"] is True
    for public_record in (summary, contract, pointer):
        assert_public_sanitized(public_record)
    for record in (summary, contract, pointer, private):
        assert_no_replay_boundaries(record)


def test_stage12605_rejects_public_private_leaks():
    leaked = {"production_path": "networkx/readwrite/pajek.py", **stage.no_replay_claim_fields()}
    leaked["authorizes_execution"] = True
    leaked["execution_allowed"] = True
    with pytest.raises(stage.GateError, match="public_leak"):
        stage.assert_public_sanitized(leaked, "leaked")
