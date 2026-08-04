import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12602_clean_candidate_source_packet.py"
RUNNER = ROOT / "scripts/run_stage12602_clean_manual_replay_executor.py"
SPEC = importlib.util.spec_from_file_location("stage12602", SCRIPT)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)
RUNNER_SPEC = importlib.util.spec_from_file_location("stage12602_runner", RUNNER)
assert RUNNER_SPEC and RUNNER_SPEC.loader
runner = importlib.util.module_from_spec(RUNNER_SPEC)
RUNNER_SPEC.loader.exec_module(runner)


def read_json(path: Path):
    return json.loads(path.read_text())


def tree_hashes(root: Path):
    hashes = {}
    for path in root.rglob("*"):
        if path.is_file():
            hashes[path.relative_to(root).as_posix()] = runner.sha256_file(path)
    return hashes


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


def test_stage12602_runner_source_is_clean_successor():
    analysis = stage.analyze_runner_source()
    assert analysis["runner_sha256"] == stage.EXPECTED_STAGE12602_RUNNER
    assert analysis["duplicate_definition_ambiguity_present"] is False
    assert analysis["execute_reviewed_slot_definition_count"] == 1
    assert analysis["implemented_reviewable_functions_assignment_count"] == 1
    assert "apply_exact_production_patch" in analysis["execute_reviewed_slot_calls"]
    assert "assert_final_reverts_initial" in analysis["execute_reviewed_slot_calls"]
    assert "publish_private_raw_evidence_after_public_leak_scan" in analysis["execute_reviewed_slot_calls"]
    assert_false_boundaries(analysis)


def test_stage12602_runner_describes_clean_candidate_and_rejects_execution():
    watched_before = {
        "stage12601": tree_hashes(runner.S12601),
        "stage12594": tree_hashes(runner.S12594),
        "stage12595": tree_hashes(runner.S12595),
    }
    result = subprocess.run(
        [sys.executable, str(RUNNER), "--describe-only"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
    )
    assert result.returncode == 0
    descriptor = json.loads(result.stdout)
    assert descriptor["source_cleanup_successor_to_stage12601"] is True
    assert descriptor["duplicate_definition_ambiguity_present"] is False
    assert descriptor["execute_reviewed_slot_definition_count"] == 1
    assert descriptor["implemented_reviewable_functions_assignment_count"] == 1
    assert descriptor["candidate_execution_capable_source_present"] is True
    assert descriptor["candidate_execution_implementation_present"] is True
    assert descriptor["reviewed_execution_capable_source_present"] is False
    assert descriptor["independent_execution_capable_source_review_present"] is False
    assert descriptor["execute_path_enabled"] is False
    assert descriptor["execution_gate_granted"] is False
    assert descriptor["execution_request_ready_count"] == 0
    assert descriptor["this_stage_runs_replay"] is False
    assert descriptor["executor_command_manifest_present"] is False
    assert descriptor["raw_replay_evidence_present"] is False
    assert descriptor["required_phase_sequence"] == ["initial", "patched", "final"]
    assert descriptor["required_controls"] == list(runner.REQUIRED_CONTROLS)
    assert descriptor["implemented_reviewable_functions"] == list(runner.IMPLEMENTED_REVIEWABLE_FUNCTIONS)
    assert_false_boundaries(descriptor)
    execute = subprocess.run(
        [sys.executable, str(RUNNER), "--execute"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
    )
    assert execute.returncode != 0
    assert "execution_disabled_pending_independent_execution_capable_source_review" in execute.stderr
    default = subprocess.run(
        [sys.executable, str(RUNNER)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
    )
    assert default.returncode != 0
    assert "describe_only_flag_required" in default.stderr
    watched_after = {
        "stage12601": tree_hashes(runner.S12601),
        "stage12594": tree_hashes(runner.S12594),
        "stage12595": tree_hashes(runner.S12595),
    }
    assert watched_after == watched_before


def test_stage12602_loads_stage12601_blocker_before_successor_source():
    loaded = stage.load_stage12601()
    assert loaded["summary"]["decision"] == "BLOCKED_SOURCE_CLEANUP_REQUIRED_BEFORE_INDEPENDENT_REVIEW"
    assert loaded["summary"]["source_ambiguity_blocker_present"] is True
    assert loaded["private"]["review_result"] == "BLOCKED_DUPLICATE_EXECUTE_REVIEWED_SLOT_DEFINITIONS"
    assert loaded["private"]["execute_reviewed_slot_definition_count"] == 2
    for record in (loaded["summary"], loaded["contract"], loaded["pointer"], loaded["private"]):
        assert_false_boundaries(record, require_all=False)


@pytest.mark.parametrize("bad_path", ["", ".", "..", "/abs.py", "a//b.py", "a/b/", "a\\b.py", "a/../b.py", "nul\x00x"])
def test_stage12602_runner_rejects_non_descriptor_safe_production_paths(bad_path):
    with pytest.raises(runner.GateError):
        runner.validate_production_path(bad_path)


def test_stage12602_runner_reviewable_manifest_and_guards(monkeypatch, tmp_path):
    patch = tmp_path / "slot_1.patch"
    patch.write_text("diff --git a/pkg/file.py b/pkg/file.py\n", encoding="utf-8")
    patch_hash = runner.sha256_file(patch)
    slot = {
        "slot_ordinal": 1,
        "binding_payload_sha256": "a" * 64,
        "before_commit_oid": "b" * 40,
        "after_commit_oid": "c" * 40,
        "production_path": "pkg/file.py",
        "production_patch_sha256": patch_hash,
        "namespace_input_manifest_sha256": "d" * 64,
    }
    blueprint = {
        "binding_ref": "binding_" + slot["binding_payload_sha256"][:24],
        "protocol": [
            {"action": "run_initial_verifier", "expected_node_ids_sha256": "e" * 64},
            {"action": "run_patched_verifier", "expected_node_ids_sha256": "e" * 64},
            {"action": "run_final_verifier", "expected_node_ids_sha256": "e" * 64},
        ],
    }
    manifest = runner.build_execution_command_manifest(
        {"blueprints": [blueprint]}, {"slots": [slot]}, tmp_path, tmp_path / "evidence",
    )
    assert manifest["slot_count"] == 1
    assert manifest["slots"][0]["phase_sequence"] == ["initial", "patched", "final"]
    assert all(command[0] == "bwrap" for command in manifest["slots"][0]["phase_commands"].values())
    snapshot = {"binding_snapshots": [{"binding_payload_sha256": "a" * 64, "namespace_input_manifest_sha256": "d" * 64}]}
    runner.rerun_namespace_manifest_match(slot, snapshot)
    monkeypatch.setattr(runner, "git_changed_paths", lambda root: ["pkg/file.py"])
    runner.assert_patched_only_changes_bound_production_path(tmp_path, slot)
    monkeypatch.setattr(runner, "git_changed_paths", lambda root: ["pkg/file.py", "tests/test_file.py"])
    with pytest.raises(runner.GateError, match="patched_state_not_bound_to_production_path"):
        runner.assert_patched_only_changes_bound_production_path(tmp_path, slot)
    runner.assert_final_reverts_initial("abc", "abc")
    with pytest.raises(runner.GateError, match="final_filesystem_digest_mismatch"):
        runner.assert_final_reverts_initial("abc", "def")
    patch.write_text("tampered", encoding="utf-8")
    with pytest.raises(runner.GateError, match="patch_artifact_digest_mismatch"):
        runner.verify_patch_artifact(slot, patch)


def test_stage12602_execution_function_requires_future_gate_before_side_effects(tmp_path):
    slot = {"slot_ordinal": 1, "production_patch_sha256": "0" * 64, "production_path": "pkg/file.py"}
    blueprint = {"protocol": []}
    gate = {"execution_gate_granted": False}
    with pytest.raises(runner.GateError, match="independent_execution_capable_source_review_required"):
        runner.execute_reviewed_slot(slot, blueprint, tmp_path / "repo", tmp_path / "patch.diff", tmp_path / "evidence", gate)
    assert not (tmp_path / "evidence").exists()


def test_stage12602_private_publication_requires_public_leak_scan():
    public_record = {"record_type": "stage12602_candidate_slot_public_execution_boundary_v1", "slot_ordinal": 1}
    private_record = {"production_path": "pkg/file.py", "production_patch_sha256": "a" * 64}
    manifest = runner.publish_private_raw_evidence_after_public_leak_scan(public_record, private_record)
    assert manifest["private_evidence_publishable"] is True
    leaked_public = dict(public_record, production_path="pkg/file.py")
    with pytest.raises(runner.GateError, match="public_leak_before_private_evidence_publish"):
        runner.publish_private_raw_evidence_after_public_leak_scan(leaked_public, private_record)


def test_stage12602_build_source_packet_keeps_review_and_execution_blocked():
    stage12601, analysis, descriptor = stage.validate_clean_runner()
    summary, contract, private = stage.build_source_packet(stage12601, analysis, descriptor)
    assert summary["decision"] == "BLOCKED_INDEPENDENT_EXECUTION_CAPABLE_SOURCE_REVIEW_REQUIRED"
    assert summary["source_cleanup_applied"] is True
    assert summary["duplicate_definition_ambiguity_present"] is False
    assert summary["source_review_request_ready"] is True
    assert summary["candidate_execution_capable_source_present"] is True
    assert summary["candidate_execution_implementation_present"] is True
    assert summary["reviewed_execution_capable_source_present"] is False
    assert summary["independent_execution_capable_source_review_present"] is False
    assert summary["independent_execution_capable_source_review_passed"] is False
    assert summary["execute_path_enabled"] is False
    assert summary["execution_gate_granted"] is False
    assert summary["execution_request_ready_count"] == 0
    assert summary["this_stage_runs_replay"] is False
    assert summary["executor_command_manifest_present"] is False
    assert summary["raw_replay_evidence_present"] is False
    assert summary["stage12603_allowed"] is False
    assert contract["source_review_request_ready"] is True
    assert private["required_controls"] == list(runner.REQUIRED_CONTROLS)
    assert private["implemented_reviewable_functions"] == list(runner.IMPLEMENTED_REVIEWABLE_FUNCTIONS)
    assert summary["required_controls_sha256"] == stage.stable_hash(private["required_controls"])
    assert summary["implemented_reviewable_functions_sha256"] == stage.stable_hash(private["implemented_reviewable_functions"])
    for record in (summary, contract, private):
        assert_false_boundaries(record)
    for public_record in (summary, contract):
        assert_public_sanitized(public_record)


def test_stage12602_build_writes_only_clean_candidate_packet(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/clean_candidate_source_packet.json",
        "summary.json",
    ]
    assert not any("stdout.raw" in name or "stderr.raw" in name or "pytest" in name for name in emitted)
    assert not any("clone" in name or "repo" in name or "command" in name for name in emitted)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/clean_candidate_source_packet.json")
    assert pointer["private_clean_candidate_source_packet_sha256"] == stage.stable_hash(private)
    assert pointer["source_static_analysis_sha256"] == stage.stable_hash(stage.analyze_runner_source())
    for public_record in (summary, contract, pointer):
        assert_public_sanitized(public_record)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_stage12602_generated_artifacts_match_current_clean_source_state():
    out = stage.OUT
    summary = read_json(out / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/clean_candidate_source_packet.json")
    analysis = stage.analyze_runner_source()
    assert summary == external
    assert pointer["candidate_runner_sha256"] == stage.sha256_file(RUNNER)
    assert summary["candidate_runner_sha256"] == pointer["candidate_runner_sha256"]
    assert pointer["private_clean_candidate_source_packet_sha256"] == stage.stable_hash(private)
    assert pointer["source_static_analysis_sha256"] == stage.stable_hash(analysis)
    assert summary["source_cleanup_applied"] is True
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
    assert private["required_controls"] == list(runner.REQUIRED_CONTROLS)
    assert private["implemented_reviewable_functions"] == list(runner.IMPLEMENTED_REVIEWABLE_FUNCTIONS)
    for public_record in (summary, contract, pointer):
        assert_public_sanitized(public_record)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)
