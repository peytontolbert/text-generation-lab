import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12600_candidate_execution_capable_source_packet.py"
RUNNER = ROOT / "scripts/run_stage12600_candidate_manual_replay_executor.py"
SPEC = importlib.util.spec_from_file_location("stage12600", SCRIPT)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)
RUNNER_SPEC = importlib.util.spec_from_file_location("stage12600_runner", RUNNER)
assert RUNNER_SPEC and RUNNER_SPEC.loader
runner = importlib.util.module_from_spec(RUNNER_SPEC)
RUNNER_SPEC.loader.exec_module(runner)


def read_json(path: Path):
    return json.loads(path.read_text())


def copy_tree(src: Path, dst: Path):
    for path in src.rglob("*"):
        if path.is_file():
            target = dst / path.relative_to(src)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())


def copy_stage12599(tmp_path: Path):
    root = tmp_path / "stage12599"
    copy_tree(stage.S12599, root)
    external = tmp_path / "stage12599_summary.json"
    external.write_bytes(stage.S12599_EXTERNAL.read_bytes())
    return root, external


def tree_hashes(root: Path):
    hashes = {}
    for path in root.rglob("*"):
        if path.is_file():
            hashes[path.relative_to(root).as_posix()] = runner.sha256_file(path)
    return hashes


def assert_false_boundaries(record, require_all=True):
    for field in (
        "implementation_ready", "stage12595_allowed", "authorizes_execution",
        "execution_allowed", "execution_performed", "replay_trustworthy",
        "level_3_materialized", "training_admitted", "strict_eval_admitted", "sealed_eval_admitted",
        "strict_eval_eligible", "sealed_eval_eligible", "admission_allowed", "training_allowed",
        "ranking_allowed", "positive_stop",
    ):
        if require_all or field in record:
            assert record[field] is False


def assert_public_sanitized(record):
    encoded = json.dumps(record, sort_keys=True)
    for forbidden in stage.PUBLIC_FORBIDDEN_SUBSTRINGS:
        assert forbidden not in encoded


def test_stage12600_candidate_runner_describes_reviewable_source_and_rejects_execution():
    watched_before = {
        "stage12594": tree_hashes(runner.S12594),
        "stage12595": tree_hashes(runner.S12595),
        "stage12599": tree_hashes(runner.S12599),
    }
    result = subprocess.run(
        [sys.executable, str(RUNNER), "--stage12599-root", str(runner.S12599), "--describe-only"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
    )
    assert result.returncode == 0
    descriptor = json.loads(result.stdout)
    assert descriptor["candidate_execution_capable_source_present"] is True
    assert descriptor["candidate_execution_implementation_present"] is True
    assert descriptor["reviewed_execution_capable_source_present"] is False
    assert descriptor["independent_execution_capable_source_review_present"] is False
    assert descriptor["execute_entrypoint_declared"] is True
    assert descriptor["execute_path_enabled"] is False
    assert descriptor["execution_gate_granted"] is False
    assert descriptor["execution_request_ready_count"] == 0
    assert descriptor["this_stage_runs_replay"] is False
    assert descriptor["executor_command_manifest_present"] is False
    assert descriptor["raw_replay_evidence_present"] is False
    assert descriptor["patch_material_required_before_execution"] is True
    assert descriptor["required_phase_sequence"] == ["initial", "patched", "final"]
    assert descriptor["required_controls"] == list(runner.REQUIRED_CONTROLS)
    assert descriptor["required_future_gate"] == "independent_execution_capable_source_review_before_execute_path_enablement"
    assert set(descriptor["implemented_reviewable_functions"]) == set(runner.IMPLEMENTED_REVIEWABLE_FUNCTIONS)
    assert_false_boundaries(descriptor)
    execute = subprocess.run(
        [sys.executable, str(RUNNER), "--stage12599-root", str(runner.S12599), "--execute"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
    )
    assert execute.returncode != 0
    assert "execution_disabled_pending_independent_execution_capable_source_review" in execute.stderr
    default = subprocess.run(
        [sys.executable, str(RUNNER), "--stage12599-root", str(runner.S12599)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
    )
    assert default.returncode != 0
    assert "describe_only_flag_required" in default.stderr
    watched_after = {
        "stage12594": tree_hashes(runner.S12594),
        "stage12595": tree_hashes(runner.S12595),
        "stage12599": tree_hashes(runner.S12599),
    }
    assert watched_after == watched_before


def test_runner_loads_current_stage12594_and_stage12595_pins():
    snapshot = runner.load_stage12594_snapshot_contract()
    handoff = runner.load_stage12595_manual_slots()
    assert snapshot["manifest"]["manifest_sha256"] == runner.EXPECTED_STAGE12594_MANIFEST
    assert snapshot["snapshot"]["binding_count"] == 2
    assert len(snapshot["blueprints"]) == 2
    assert handoff["handoff"]["manual_executor_review_required"] is True
    assert len(handoff["slots"]) == 2
    assert [slot["slot_ordinal"] for slot in handoff["slots"]] == [1, 2]


@pytest.mark.parametrize("bad_path", ["", ".", "..", "/abs.py", "a//b.py", "a/b/", "a\\b.py", "a/../b.py", "nul\x00x"])
def test_runner_rejects_non_descriptor_safe_production_paths(bad_path):
    with pytest.raises(runner.GateError):
        runner.validate_production_path(bad_path)


def test_runner_patch_digest_and_command_manifest_are_reviewable_but_not_published(tmp_path):
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
    assert runner.verify_patch_artifact(slot, patch)["production_patch_sha256"] == patch_hash
    manifest = runner.build_execution_command_manifest(
        {"blueprints": [blueprint]}, {"slots": [slot]}, tmp_path, tmp_path / "evidence",
    )
    assert manifest["slot_count"] == 1
    assert manifest["slots"][0]["phase_sequence"] == ["initial", "patched", "final"]
    assert set(manifest["slots"][0]["phase_commands"]) == {"initial", "patched", "final"}
    assert all(command[0] == "bwrap" for command in manifest["slots"][0]["phase_commands"].values())
    patch.write_text("tampered", encoding="utf-8")
    with pytest.raises(runner.GateError, match="patch_artifact_digest_mismatch"):
        runner.verify_patch_artifact(slot, patch)


def test_runner_execution_function_requires_future_gate_before_side_effects(tmp_path):
    slot = {"slot_ordinal": 1, "production_patch_sha256": "0" * 64, "production_path": "pkg/file.py"}
    blueprint = {"protocol": []}
    gate = {"execution_gate_granted": False}
    with pytest.raises(runner.GateError, match="independent_execution_capable_source_review_required"):
        runner.execute_reviewed_slot(slot, blueprint, tmp_path / "repo", tmp_path / "patch.diff", tmp_path / "evidence", gate)
    assert not (tmp_path / "evidence").exists()


def test_load_stage12599_requires_current_denied_gate_pins():
    loaded = stage.load_stage12599()
    assert loaded["summary"]["decision"] == "BLOCKED_EXECUTION_CAPABLE_SOURCE_REQUIRED"
    assert loaded["summary"]["execution_gate_granted"] is False
    assert loaded["summary"]["execution_capable_source_present"] is False
    assert loaded["summary"]["execution_request_ready_count"] == 0
    assert_false_boundaries(loaded["summary"], require_all=False)
    assert_false_boundaries(loaded["contract"], require_all=False)


def test_load_stage12599_rejects_pin_drift(tmp_path):
    root, external = copy_stage12599(tmp_path)
    summary = read_json(root / "summary.json")
    summary["execution_gate_granted"] = True
    (root / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    external.write_text(json.dumps(summary), encoding="utf-8")
    with pytest.raises(stage.GateError, match="stage12599_summary_pin_drift"):
        stage.load_stage12599(root, external)


def test_build_source_packet_keeps_candidate_unreviewed_and_nonexecuting():
    stage12599, descriptor = stage.validate_candidate_runner()
    summary, contract, private_packet = stage.build_source_packet(stage12599, descriptor)
    assert summary["decision"] == "BLOCKED_INDEPENDENT_EXECUTION_CAPABLE_SOURCE_REVIEW_REQUIRED"
    assert summary["candidate_execution_capable_source_present"] is True
    assert summary["candidate_execution_implementation_present"] is True
    assert summary["reviewed_execution_capable_source_present"] is False
    assert summary["independent_execution_capable_source_review_present"] is False
    assert summary["execute_entrypoint_declared"] is True
    assert summary["execute_path_enabled"] is False
    assert summary["execution_gate_granted"] is False
    assert summary["execution_request_ready_count"] == 0
    assert summary["this_stage_runs_replay"] is False
    assert summary["executor_command_manifest_present"] is False
    assert summary["raw_replay_evidence_present"] is False
    assert summary["stage12601_allowed"] is False
    assert summary["required_controls_sha256"] == stage.stable_hash(descriptor["required_controls"])
    assert summary["implemented_reviewable_functions_sha256"] == stage.stable_hash(descriptor["implemented_reviewable_functions"])
    assert "independent_execution_capable_source_review_absent" in summary["downstream_blockers"]
    assert "manual_replay_execution_not_performed" in summary["downstream_blockers"]
    assert contract["candidate_execution_capable_source_present"] is True
    assert contract["candidate_execution_implementation_present"] is True
    assert contract["reviewed_execution_capable_source_present"] is False
    assert contract["required_controls_sha256"] == summary["required_controls_sha256"]
    assert private_packet["required_controls"] == list(runner.REQUIRED_CONTROLS)
    assert private_packet["implemented_reviewable_functions"] == list(runner.IMPLEMENTED_REVIEWABLE_FUNCTIONS)
    assert private_packet["review_required_before_use"] == "independent_execution_capable_source_review_before_execute_path_enablement"
    for record in (summary, contract, private_packet):
        assert_false_boundaries(record)
    for public_record in (summary, contract):
        assert_public_sanitized(public_record)


def test_build_writes_candidate_source_packet_without_execution_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/candidate_execution_capable_source_packet.json",
        "summary.json",
    ]
    assert not any("stdout.raw" in name or "stderr.raw" in name or "pytest" in name for name in emitted)
    assert not any("clone" in name or "repo" in name or "command" in name for name in emitted)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private_packet = read_json(out / "private/candidate_execution_capable_source_packet.json")
    assert pointer["private_candidate_source_packet_sha256"] == stage.stable_hash(private_packet)
    assert pointer["candidate_runner_sha256"] == stage.EXPECTED_STAGE12600_RUNNER
    assert summary["execute_path_enabled"] is False
    assert contract["execute_path_enabled"] is False
    assert private_packet["required_controls"] == list(runner.REQUIRED_CONTROLS)
    for public_record in (summary, contract, pointer):
        assert_public_sanitized(public_record)
    for record in (summary, contract, pointer, private_packet):
        assert_false_boundaries(record)


def test_stage12600_generated_artifacts_match_current_candidate_source_digest():
    out = stage.OUT
    summary = read_json(out / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private_packet = read_json(out / "private/candidate_execution_capable_source_packet.json")
    assert summary == external
    assert pointer["candidate_runner_sha256"] == stage.sha256_file(RUNNER)
    assert pointer["private_candidate_source_packet_sha256"] == stage.stable_hash(private_packet)
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
    assert contract["reviewed_execution_capable_source_present"] is False
    assert contract["execute_path_enabled"] is False
    assert private_packet["required_controls"] == list(runner.REQUIRED_CONTROLS)
    assert private_packet["implemented_reviewable_functions"] == list(runner.IMPLEMENTED_REVIEWABLE_FUNCTIONS)
    for public_record in (summary, contract, pointer):
        assert_public_sanitized(public_record)
    for record in (summary, contract, pointer, private_packet):
        assert_false_boundaries(record)



def test_runner_wires_namespace_manifest_match_before_execution_materials():
    slot = {"binding_payload_sha256": "a" * 64, "namespace_input_manifest_sha256": "n" * 64}
    snapshot = {"binding_snapshots": [{"binding_payload_sha256": "a" * 64, "namespace_input_manifest_sha256": "n" * 64}]}
    runner.rerun_namespace_manifest_match(slot, snapshot)
    drifted = {"binding_snapshots": [{"binding_payload_sha256": "a" * 64, "namespace_input_manifest_sha256": "x" * 64}]}
    with pytest.raises(runner.GateError, match="namespace_manifest_match_failed"):
        runner.rerun_namespace_manifest_match(slot, drifted)


def test_runner_patched_only_and_final_revert_guards(monkeypatch, tmp_path):
    slot = {"production_path": "pkg/file.py"}
    monkeypatch.setattr(runner, "git_changed_paths", lambda root: ["pkg/file.py"])
    runner.assert_patched_only_changes_bound_production_path(tmp_path, slot)
    monkeypatch.setattr(runner, "git_changed_paths", lambda root: ["pkg/file.py", "tests/test_file.py"])
    with pytest.raises(runner.GateError, match="patched_state_not_bound_to_production_path"):
        runner.assert_patched_only_changes_bound_production_path(tmp_path, slot)
    runner.assert_final_reverts_initial("abc", "abc")
    with pytest.raises(runner.GateError, match="final_filesystem_digest_mismatch"):
        runner.assert_final_reverts_initial("abc", "def")


def test_runner_private_publication_requires_public_leak_scan():
    public_record = {
        "record_type": "stage12600_candidate_slot_public_execution_boundary_v1",
        "slot_ordinal": 1,
        "phase_sequence": ["initial", "patched", "final"],
    }
    private_record = {"production_path": "pkg/file.py", "production_patch_sha256": "a" * 64}
    manifest = runner.publish_private_raw_evidence_after_public_leak_scan(public_record, private_record)
    assert manifest["private_evidence_publishable"] is True
    leaked_public = dict(public_record, production_path="pkg/file.py")
    with pytest.raises(runner.GateError, match="public_leak_before_private_evidence_publish"):
        runner.publish_private_raw_evidence_after_public_leak_scan(leaked_public, private_record)


def test_execute_reviewed_slot_source_mentions_required_control_functions():
    source = RUNNER.read_text(encoding="utf-8")
    body = source[source.rfind("def execute_reviewed_slot("):source.find("\ndef build_candidate_source_descriptor", source.rfind("def execute_reviewed_slot("))]
    for required_call in (
        "require_authorized_execution_gate",
        "rerun_namespace_manifest_match",
        "verify_patch_artifact",
        "create_detached_snapshot",
        "filesystem_state_digest",
        "run_pytest_phase_inside_hardened_bwrap",
        "apply_exact_production_patch",
        "assert_patched_only_changes_bound_production_path",
        "revert_exact_production_patch",
        "assert_final_reverts_initial",
        "publish_private_raw_evidence_after_public_leak_scan",
    ):
        assert required_call in body
