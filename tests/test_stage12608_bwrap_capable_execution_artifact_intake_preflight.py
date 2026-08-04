import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12608_bwrap_capable_execution_artifact_intake_preflight.py"
SPEC = importlib.util.spec_from_file_location("stage12608", SCRIPT)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


def read_json(path: Path):
    return json.loads(path.read_text())


def assert_false_boundaries(record):
    for field in (
        "implementation_ready", "stage12595_allowed", "execution_performed", "replay_trustworthy",
        "level_3_materialized", "training_admitted", "strict_eval_admitted", "sealed_eval_admitted",
        "strict_eval_eligible", "sealed_eval_eligible", "admission_allowed", "training_allowed",
        "ranking_allowed", "positive_stop", "raw_replay_evidence_present",
    ):
        assert record[field] is False


def assert_public_sanitized(record):
    encoded = json.dumps(record, sort_keys=True)
    for forbidden in stage.PUBLIC_FORBIDDEN_SUBSTRINGS:
        assert forbidden not in encoded


def test_load_stage12607_requires_nonexecuting_handoff():
    loaded = stage.load_stage12607()
    summary = loaded["summary"]
    private = loaded["private"]
    assert summary["decision"] == "BWRAP_CAPABLE_REVIEWED_FUNCTION_REPLAY_HANDOFF_READY_EXECUTION_NOT_RUN"
    assert summary["execution_handoff_runs_replay"] is False
    assert summary["stage12608_allowed"] is False
    assert summary["stage12608_bwrap_capable_function_execution_review_allowed"] is True
    assert private["slot_count"] == 2
    assert private["gate_scope"] == stage.EXPECTED_GATE_SCOPE
    for record in loaded.values():
        assert_false_boundaries(record)


def test_required_relative_evidence_schema():
    item = {"slot_ordinal": 3}
    assert stage.required_relative_evidence(item) == [
        "slot_3/reviewed_slot_execution_result.json",
        "slot_3/initial.stdout.raw",
        "slot_3/initial.stderr.raw",
        "slot_3/patched.stdout.raw",
        "slot_3/patched.stderr.raw",
        "slot_3/final.stdout.raw",
        "slot_3/final.stderr.raw",
    ]


def test_inspect_future_evidence_reports_missing_current_root():
    private = stage.load_stage12607()["private"]
    evidence = stage.inspect_future_evidence(private)
    assert evidence["future_private_evidence_root_exists"] is False
    assert evidence["required_file_count"] == 14
    assert evidence["present_file_count"] == 0
    assert evidence["missing_file_count"] == 14
    assert evidence["all_required_evidence_present"] is False
    assert "slot_1/initial.stdout.raw" in evidence["missing_relative_files"]
    assert "slot_2/reviewed_slot_execution_result.json" in evidence["missing_relative_files"]


def test_build_intake_packet_blocks_missing_external_evidence():
    stage12607 = stage.load_stage12607()
    evidence = stage.inspect_future_evidence(stage12607["private"])
    summary, contract, private = stage.build_intake_packet(stage12607, evidence)
    assert summary["decision"] == "BLOCKED_EXTERNAL_BWRAP_CAPABLE_EXECUTION_ARTIFACTS_MISSING"
    assert summary["external_bwrap_capable_execution_artifacts_present"] is False
    assert summary["required_evidence_slot_count"] == 2
    assert summary["required_evidence_file_count"] == 14
    assert summary["present_evidence_file_count"] == 0
    assert summary["missing_evidence_file_count"] == 14
    assert summary["stage12609_allowed"] is False
    assert summary["causal_transition_atoms_allowed"] is False
    assert contract["private_intake_blocker_sha256"] == stage.stable_hash(private)
    assert private["required_evidence_schema"]["slot_result_manifest"] == "slot_N/reviewed_slot_execution_result.json"
    for public_record in (summary, contract):
        assert_public_sanitized(public_record)
    for record in (summary, contract, private):
        assert_false_boundaries(record)


def test_build_writes_only_intake_blocker_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/execution_artifact_intake_blocker.json",
        "summary.json",
    ]
    assert not any("stdout.raw" in name or "stderr.raw" in name or "pytest" in name for name in emitted)
    assert not any("patches" in name or "future_evidence" in name or "snapshot" in name for name in emitted)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/execution_artifact_intake_blocker.json")
    assert pointer["private_intake_blocker_sha256"] == stage.stable_hash(private)
    assert pointer["contract_sha256"] == stage.stable_hash(contract)
    assert pointer["stage12609_allowed"] is False
    for public_record in (summary, contract, pointer):
        assert_public_sanitized(public_record)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_generated_artifacts_match_current_intake_blocker():
    out = stage.OUT
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/execution_artifact_intake_blocker.json",
        "summary.json",
    ]
    assert not any("stdout.raw" in name or "stderr.raw" in name or "pytest" in name for name in emitted)
    assert not any("patches" in name or "future_evidence" in name or "snapshot" in name for name in emitted)
    summary = read_json(out / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/execution_artifact_intake_blocker.json")
    assert summary == external
    assert summary["decision"] == "BLOCKED_EXTERNAL_BWRAP_CAPABLE_EXECUTION_ARTIFACTS_MISSING"
    assert summary["execution_performed"] is False
    assert summary["raw_replay_evidence_present"] is False
    assert summary["replay_trustworthy"] is False
    assert summary["level_3_materialized"] is False
    assert summary["training_admitted"] is False
    assert pointer["private_intake_blocker_sha256"] == stage.stable_hash(private)
    assert pointer["contract_sha256"] == stage.stable_hash(contract)
    assert private["future_evidence_inspection"]["all_required_evidence_present"] is False
    for public_record in (summary, contract, pointer):
        assert_public_sanitized(public_record)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_build_intake_packet_rejects_complete_future_evidence():
    loaded = stage.load_stage12607()
    evidence = {
        "future_private_evidence_root": "/data/agentkernel-seq2seq-text-lab/runs/local/private/stage12608_bwrap_capable_reviewed_function_replay_execution",
        "future_private_evidence_root_exists": True,
        "required_file_count": 14,
        "present_file_count": 14,
        "missing_file_count": 0,
        "required_relative_files": [],
        "present_relative_files": [],
        "missing_relative_files": [],
        "all_required_evidence_present": True,
    }
    with pytest.raises(stage.IntakeError, match="unexpected_future_execution_evidence_present"):
        stage.build_intake_packet(loaded, evidence)


def test_public_leak_scan_rejects_private_evidence_root():
    leaked = {"future_evidence": "/data/agentkernel-seq2seq-text-lab/runs/local/private/stage12608", **stage.no_replay_claim_fields()}
    with pytest.raises(stage.IntakeError, match="public_leak"):
        stage.assert_public_sanitized(leaked, "leaked")
