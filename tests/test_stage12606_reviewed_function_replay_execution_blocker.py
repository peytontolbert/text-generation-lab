import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12606_reviewed_function_replay_execution_blocker.py"
SPEC = importlib.util.spec_from_file_location("stage12606", SCRIPT)
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


def failed_probe():
    return {
        "command_name": "bwrap",
        "returncode": 1,
        "stdout_sha256": stage.sha256_bytes(b""),
        "stderr_sha256": stage.sha256_bytes(b"bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted\n"),
        "stdout_text": "",
        "stderr_text": "bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted\n",
        "blocker": "BWRAP_LOOPBACK_UNAVAILABLE",
    }


def test_load_stage12605_requires_scoped_gate_only():
    loaded = stage.load_stage12605()
    summary = loaded["summary"]
    pointer = loaded["pointer"]
    private = loaded["private_gate"]
    assert summary["execution_gate_granted"] is True
    assert summary["gate_scope"] == stage.EXPECTED_GATE_SCOPE
    assert summary["stage12606_allowed"] is False
    assert summary["stage12606_reviewed_function_replay_allowed"] is True
    assert pointer["stage12606_allowed"] is False
    assert pointer["stage12606_reviewed_function_replay_allowed"] is True
    assert private["cli_execute_entrypoint_enabled"] is False
    for record in loaded.values():
        assert_false_boundaries(record)


def test_build_blocker_packet_keeps_replay_and_training_false():
    loaded = stage.load_stage12605()
    summary, contract, private = stage.build_blocker_packet(loaded, failed_probe())
    assert summary["decision"] == "BLOCKED_BWRAP_LOOPBACK_UNAVAILABLE"
    assert summary["reviewed_function_execute_path_enabled"] is True
    assert summary["cli_execute_entrypoint_enabled"] is False
    assert summary["stage12606_allowed"] is False
    assert summary["stage12606_reviewed_function_replay_allowed"] is True
    assert summary["attempted_operation"] == "minimal_bwrap_capability_probe_only"
    assert summary["execute_reviewed_slot_called"] is False
    assert summary["replay_slot_count_attempted"] == 0
    assert summary["environment_blocker"] == "BWRAP_LOOPBACK_UNAVAILABLE"
    assert contract["private_probe_sha256"] == stage.stable_hash(private["bwrap_probe"])
    assert private["bwrap_probe"]["stderr_text"].startswith("bwrap: loopback")
    for public_record in (summary, contract):
        assert_public_sanitized(public_record)
    for record in (summary, contract, private):
        assert_false_boundaries(record)


def test_build_writes_only_blocker_artifacts(monkeypatch, tmp_path):
    monkeypatch.setattr(stage, "run_bwrap_probe", failed_probe)
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/reviewed_function_replay_execution_blocker.json",
        "summary.json",
    ]
    assert not any("stdout.raw" in name or "stderr.raw" in name or "pytest" in name for name in emitted)
    assert not any("patches" in name or "future_evidence" in name or "snapshot" in name for name in emitted)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/reviewed_function_replay_execution_blocker.json")
    assert pointer["private_blocker_sha256"] == stage.stable_hash(private)
    assert pointer["contract_sha256"] == stage.stable_hash(contract)
    assert pointer["stage12606_allowed"] is False
    assert pointer["stage12606_reviewed_function_replay_allowed"] is True
    for public_record in (summary, contract, pointer):
        assert_public_sanitized(public_record)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_generated_artifacts_match_current_bwrap_blocker():
    out = stage.OUT
    summary = read_json(out / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/reviewed_function_replay_execution_blocker.json")
    assert summary == external
    assert summary["decision"] == "BLOCKED_BWRAP_LOOPBACK_UNAVAILABLE"
    assert summary["execute_reviewed_slot_called"] is False
    assert summary["replay_slot_count_attempted"] == 0
    assert summary["execution_performed"] is False
    assert summary["raw_replay_evidence_present"] is False
    assert summary["stage12606_allowed"] is False
    assert summary["stage12606_reviewed_function_replay_allowed"] is True
    assert private["bwrap_probe"]["blocker"] == "BWRAP_LOOPBACK_UNAVAILABLE"
    assert "Failed RTM_NEWADDR" in private["bwrap_probe"]["stderr_text"]
    assert "Operation not permitted" in private["bwrap_probe"]["stderr_text"]
    assert pointer["private_blocker_sha256"] == stage.stable_hash(private)
    assert pointer["contract_sha256"] == stage.stable_hash(contract)
    for public_record in (summary, contract, pointer):
        assert_public_sanitized(public_record)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_build_blocker_rejects_available_bwrap_probe():
    good = dict(failed_probe(), returncode=0, stderr_text="", stderr_sha256=stage.sha256_bytes(b""), blocker="NONE")
    with pytest.raises(stage.BlockerError, match="bwrap_probe_unexpectedly_available"):
        stage.build_blocker_packet(stage.load_stage12605(), good)
