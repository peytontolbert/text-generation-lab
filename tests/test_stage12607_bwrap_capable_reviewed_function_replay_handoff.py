import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12607_bwrap_capable_reviewed_function_replay_handoff.py"
SPEC = importlib.util.spec_from_file_location("stage12607", SCRIPT)
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


def test_load_stage12606_requires_current_bwrap_blocker():
    loaded = stage.load_stage12606()
    assert loaded["summary"]["decision"] == "BLOCKED_BWRAP_LOOPBACK_UNAVAILABLE"
    assert loaded["summary"]["execute_reviewed_slot_called"] is False
    assert loaded["summary"]["raw_replay_evidence_present"] is False
    assert loaded["private"]["bwrap_probe"]["blocker"] == "BWRAP_LOOPBACK_UNAVAILABLE"
    assert "Failed RTM_NEWADDR" in loaded["private"]["bwrap_probe"]["stderr_text"]
    for record in loaded.values():
        assert_false_boundaries(record)


def test_load_private_inputs_pins_reviewed_materials():
    loaded = stage.load_private_inputs()
    manifest = loaded["command_manifest"]
    gate = loaded["private_gate"]
    assert manifest["slot_count"] == 2
    assert gate["gate_scope"] == stage.EXPECTED_GATE_SCOPE
    assert gate["reviewed_function_execute_path_enabled"] is True
    assert gate["cli_execute_entrypoint_enabled"] is False
    assert [slot["slot_ordinal"] for slot in manifest["slots"]] == [1, 2]
    for slot in manifest["slots"]:
        assert slot["binding_payload_sha256"] in stage.REPOSITORY_ROOTS_BY_BINDING


def test_private_invocations_are_function_only_and_exactly_pinned():
    manifest = stage.load_private_inputs()["command_manifest"]
    invocations = stage.build_private_invocations(manifest)
    assert len(invocations) == 2
    assert {item["reviewed_function_name"] for item in invocations} == {"execute_reviewed_slot"}
    assert all(item["cli_execute_entrypoint_forbidden"] is True for item in invocations)
    assert all("--execute" not in json.dumps(item, sort_keys=True) for item in invocations)
    assert {Path(item["repository_root"]).name for item in invocations} == {"pytest", "networkx"}
    assert invocations[0]["patch_file_sha256"] == invocations[0]["production_patch_sha256"]
    assert invocations[1]["patch_file_sha256"] == invocations[1]["production_patch_sha256"]


def test_build_handoff_packet_public_private_boundary():
    stage12606 = stage.load_stage12606()
    inputs = stage.load_private_inputs()
    summary, contract, private = stage.build_handoff_packet(stage12606, inputs)
    assert summary["decision"] == "BWRAP_CAPABLE_REVIEWED_FUNCTION_REPLAY_HANDOFF_READY_EXECUTION_NOT_RUN"
    assert summary["handoff_ready_for_bwrap_capable_environment"] is True
    assert summary["execution_handoff_runs_replay"] is False
    assert summary["stage12608_allowed"] is False
    assert summary["stage12608_bwrap_capable_function_execution_review_allowed"] is True
    assert contract["private_handoff_sha256"] == stage.stable_hash(private)
    assert private["slot_count"] == 2
    assert private["private_slot_invocations"][0]["runner_module_path"].endswith("run_stage12602_clean_manual_replay_executor.py")
    assert private["private_slot_invocations"][0]["future_private_evidence_root"].endswith(
        "stage12608_bwrap_capable_reviewed_function_replay_execution"
    )
    for public_record in (summary, contract):
        assert_public_sanitized(public_record)
    for record in (summary, contract, private):
        assert_false_boundaries(record)


def test_build_writes_only_handoff_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/bwrap_capable_reviewed_function_replay_handoff.json",
        "summary.json",
    ]
    assert not any("stdout.raw" in name or "stderr.raw" in name or "pytest" in name for name in emitted)
    assert not any("patches" in name or "future_evidence" in name for name in emitted)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/bwrap_capable_reviewed_function_replay_handoff.json")
    assert pointer["private_handoff_sha256"] == stage.stable_hash(private)
    assert pointer["contract_sha256"] == stage.stable_hash(contract)
    assert pointer["execution_handoff_runs_replay"] is False
    for public_record in (summary, contract, pointer):
        assert_public_sanitized(public_record)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_generated_artifacts_match_current_handoff():
    out = stage.OUT
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/bwrap_capable_reviewed_function_replay_handoff.json",
        "summary.json",
    ]
    assert not any("stdout.raw" in name or "stderr.raw" in name or "pytest" in name for name in emitted)
    assert not any("patches" in name or "future_evidence" in name or "snapshot" in name for name in emitted)
    summary = read_json(out / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/bwrap_capable_reviewed_function_replay_handoff.json")
    assert summary == external
    assert summary["execution_handoff_runs_replay"] is False
    assert summary["execution_performed"] is False
    assert summary["raw_replay_evidence_present"] is False
    assert summary["replay_trustworthy"] is False
    assert summary["level_3_materialized"] is False
    assert summary["training_admitted"] is False
    assert pointer["private_handoff_sha256"] == stage.stable_hash(private)
    assert pointer["contract_sha256"] == stage.stable_hash(contract)
    assert private["private_slot_invocations"][0]["reviewed_function_name"] == "execute_reviewed_slot"
    assert private["private_slot_invocations"][1]["reviewed_function_name"] == "execute_reviewed_slot"
    for public_record in (summary, contract, pointer):
        assert_public_sanitized(public_record)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_public_leak_scan_rejects_private_paths():
    leaked = {"repository_root": "/arxiv/repositories/pytest", **stage.no_replay_claim_fields()}
    with pytest.raises(stage.HandoffError, match="public_leak"):
        stage.assert_public_sanitized(leaked, "leaked")
