import base64
import importlib.util
import json
import os
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12594_trusted_external_causal_replay_runner_preflight.py"
SPEC = importlib.util.spec_from_file_location("stage12594", SCRIPT)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


def command(*argv, cwd=None):
    result = subprocess.run(argv, cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.stdout


def synthetic_repo(tmp_path):
    repo = tmp_path / "source"
    repo.mkdir()
    command("git", "init", "-q", cwd=repo)
    command("git", "config", "user.email", "test@example.invalid", cwd=repo)
    command("git", "config", "user.name", "Stage Test", cwd=repo)
    (repo / ".gitignore").write_text("*.ignored\n")
    (repo / "prod.py").write_text("VALUE = 0\n")
    (repo / "test_prod.py").write_text("def test_value():\n    assert True\n")
    (repo / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")
    command("git", "add", ".", cwd=repo)
    command("git", "commit", "-qm", "before", cwd=repo)
    before = command("git", "rev-parse", "HEAD", cwd=repo).decode().strip()
    before_bytes = (repo / "prod.py").read_bytes()
    (repo / "prod.py").write_text("VALUE = 1\n")
    (repo / "test_prod.py").write_text("def test_value():\n    assert 1 == 1\n")
    command("git", "add", ".", cwd=repo)
    command("git", "commit", "-qm", "after", cwd=repo)
    after = command("git", "rev-parse", "HEAD", cwd=repo).decode().strip()
    after_bytes = (repo / "prod.py").read_bytes()
    return repo, before, after, before_bytes, after_bytes




def make_material(path, before_bytes, after_bytes):
    return {
        "path": path,
        "before_bytes": before_bytes,
        "after_bytes": after_bytes,
        "before_sha256": stage.sha256_bytes(before_bytes),
        "after_sha256": stage.sha256_bytes(after_bytes),
    }

def fake_binding(repo, before, after):
    path = "prod.py"
    before_oid = command("git", "rev-parse", f"{before}:{path}", cwd=repo).decode().strip()
    after_oid = command("git", "rev-parse", f"{after}:{path}", cwd=repo).decode().strip()
    patch = command("git", "diff", "--binary", before, after, "--", path, cwd=repo)
    payload = {
        "schema": "stage12593_canonical_immutable_binding_payload_v2",
        "repository": {"path": str(repo), "name": "secret-repo", "before_commit_oid": before, "after_commit_oid": after},
        "production_patch": {
            "path": path, "sha256": stage.sha256_bytes(patch),
            "before_blob": ["100644", "blob", before_oid], "after_blob": ["100644", "blob", after_oid],
        },
        "fixture": {"source_path": "test_prod.py"},
        "selector": "secret-selector",
        "namespace_clearance": {"clear": True, "namespace_input_manifest_sha256": "a" * 64},
    }
    return {"binding_ref": "binding_secret", "binding_payload_sha256": stage.stable_hash(payload), "binding_payload": payload}


def run_report(tmp_path, name, source):
    phase = tmp_path / name
    phase.mkdir()
    test_file = phase / "test_sample.py"
    test_file.write_text(source)
    plugin = phase / "stage12594_plugin.py"
    stage.write_trusted_pytest_plugin(plugin)
    report = phase / "report.jsonl"
    env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(phase),
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "STAGE12594_REPORT_PATH": str(report),
    }
    capture = stage.run_captured(
        [str(stage.PYTHON), "-m", "pytest", "-p", "stage12594_plugin", "-p", "no:cacheprovider", "-q", "test_sample.py"],
        phase, env, phase / "stdout.raw", phase / "stderr.raw",
    )
    parsed = stage.parse_pytest_report(report, phase, capture["return_code"])
    return capture, parsed, report


def assert_boundaries_false(record):
    for field in (
        "replay_trustworthy", "level_3_materialized", "training_admitted",
        "strict_eval_admitted", "sealed_eval_admitted", "strict_eval_eligible",
        "sealed_eval_eligible", "execution_allowed", "execution_performed",
        "admission_allowed", "training_allowed", "ranking_allowed",
    ):
        assert record[field] is False


def test_detached_clone_is_fresh_no_hardlinks_and_exact_revert(tmp_path):
    source, before, _, before_bytes, after_bytes = synthetic_repo(tmp_path)
    clone = tmp_path / "clone"
    lifecycle = stage.detached_clone(source, clone, before)
    assert lifecycle["detached"] is True
    assert lifecycle["shared_regular_inode_count"] == 0
    initial = stage.capture_state(clone)
    stage.assert_initial_state(initial, before)
    material = make_material("prod.py", before_bytes, after_bytes)
    stage.replace_production_blob(clone, material, True)
    patched = stage.capture_state(clone)
    stage.assert_patched_state(initial, patched, "prod.py", material["before_sha256"], material["after_sha256"])
    stage.replace_production_blob(clone, material, False)
    stage.assert_reverted_state(initial, stage.capture_state(clone))



@pytest.mark.parametrize("bad_path", [
    "", ".", "..", "/prod.py", "dir//prod.py", "prod.py/",
    "dir\\prod.py", "bad\x00name", "dir/../prod.py", "dir/./prod.py",
])
def test_descriptor_safe_production_path_rejects_noncanonical(tmp_path, bad_path):
    source, before, _, before_bytes, after_bytes = synthetic_repo(tmp_path)
    clone = tmp_path / "clone"
    stage.detached_clone(source, clone, before)
    with pytest.raises(stage.GateError, match="production_path"):
        stage.replace_production_blob(clone, make_material(bad_path, before_bytes, after_bytes), True)


def test_descriptor_safe_production_path_rejects_symlink_parent(tmp_path):
    source, before, _, before_bytes, after_bytes = synthetic_repo(tmp_path)
    clone = tmp_path / "clone"
    stage.detached_clone(source, clone, before)
    (clone / "real").mkdir()
    (clone / "real" / "prod.py").write_bytes(before_bytes)
    os.symlink("real", clone / "linkdir")
    with pytest.raises(stage.GateError, match="production_parent_open_failed"):
        stage.replace_production_blob(clone, make_material("linkdir/prod.py", before_bytes, after_bytes), True)


def test_descriptor_safe_production_path_rejects_symlink_leaf(tmp_path):
    source, before, _, before_bytes, after_bytes = synthetic_repo(tmp_path)
    clone = tmp_path / "clone"
    stage.detached_clone(source, clone, before)
    target = clone / "target.py"
    target.write_bytes(before_bytes)
    (clone / "prod.py").unlink()
    os.symlink("target.py", clone / "prod.py")
    with pytest.raises(stage.GateError, match="production_leaf_open_failed"):
        stage.replace_production_blob(clone, make_material("prod.py", before_bytes, after_bytes), True)
    assert target.read_bytes() == before_bytes


def test_descriptor_safe_production_path_rejects_temporary_collision(tmp_path):
    source, before, _, before_bytes, after_bytes = synthetic_repo(tmp_path)
    clone = tmp_path / "clone"
    stage.detached_clone(source, clone, before)
    collision = clone / ".prod.py.stage12594.tmp"
    collision.write_text("occupied")
    with pytest.raises(stage.GateError, match="production_temporary_collision"):
        stage.replace_production_blob(clone, make_material("prod.py", before_bytes, after_bytes), True)
    assert (clone / "prod.py").read_bytes() == before_bytes
    assert collision.read_text() == "occupied"


def test_descriptor_safe_production_path_rejects_leaf_inode_race(monkeypatch, tmp_path):
    source, before, _, before_bytes, after_bytes = synthetic_repo(tmp_path)
    clone = tmp_path / "clone"
    stage.detached_clone(source, clone, before)
    original_open = stage.os.open
    leaf_open_count = 0

    def racing_open(path, flags, mode=0o777, *, dir_fd=None):
        nonlocal leaf_open_count
        if path == "prod.py" and dir_fd is not None and flags & stage.os.O_NOFOLLOW:
            leaf_open_count += 1
            if leaf_open_count == 2:
                attacker = clone / "attacker.py"
                attacker.write_bytes(before_bytes)
                os.replace(attacker, clone / "prod.py")
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(stage.os, "open", racing_open)
    with pytest.raises(stage.GateError, match="production_leaf_identity_changed"):
        stage.replace_production_blob(clone, make_material("prod.py", before_bytes, after_bytes), True)
    assert leaf_open_count == 2
    assert not (clone / ".prod.py.stage12594.tmp").exists()


def test_descriptor_safe_production_path_rejects_digest_mismatch(tmp_path):
    source, before, _, before_bytes, after_bytes = synthetic_repo(tmp_path)
    clone = tmp_path / "clone"
    stage.detached_clone(source, clone, before)
    material = make_material("prod.py", before_bytes, after_bytes)
    material["before_sha256"] = "0" * 64
    with pytest.raises(stage.GateError, match="production_transition_source_mismatch"):
        stage.replace_production_blob(clone, material, True)
    assert (clone / "prod.py").read_bytes() == before_bytes


def test_descriptor_safe_production_patch_preserves_mode(tmp_path):
    source, before, _, before_bytes, after_bytes = synthetic_repo(tmp_path)
    clone = tmp_path / "clone"
    stage.detached_clone(source, clone, before)
    target = clone / "prod.py"
    os.chmod(target, 0o640)
    material = make_material("prod.py", before_bytes, after_bytes)
    stage.replace_production_blob(clone, material, True)
    assert target.read_bytes() == after_bytes
    assert stat.S_IMODE(target.stat().st_mode) == 0o640
    stage.replace_production_blob(clone, material, False)
    assert target.read_bytes() == before_bytes
    assert stat.S_IMODE(target.stat().st_mode) == 0o640

def test_live_manifest_uses_lstat_path_bytes_and_detects_transient_file(tmp_path):
    root = tmp_path / "tree"
    root.mkdir()
    (root / "data").write_bytes(b"x")
    os.symlink("data", root / "link")
    first = stage.filesystem_manifest(root)
    rows = {row["path"]: row for row in first["entries"]}
    assert rows["link"]["type"] == "symlink"
    assert base64.b64decode(rows["data"]["path_bytes_b64"]) == b"data"
    (root / "transient.tmp").write_text("residue")
    assert stage.filesystem_manifest(root)["manifest_sha256"] != first["manifest_sha256"]


def test_exact_patched_state_rejects_extra_transient(tmp_path):
    source, before, _, before_bytes, after_bytes = synthetic_repo(tmp_path)
    clone = tmp_path / "clone"
    stage.detached_clone(source, clone, before)
    initial = stage.capture_state(clone)
    (clone / "prod.py").write_bytes(after_bytes)
    (clone / "transient").write_text("bad")
    with pytest.raises(stage.GateError, match="patched_path_set_changed"):
        stage.assert_patched_state(initial, stage.capture_state(clone), "prod.py", stage.sha256_bytes(before_bytes), stage.sha256_bytes(after_bytes))


def test_measured_test_config_fixture_checkpoint_rejects_mutation(tmp_path):
    source, before, _, _, _ = synthetic_repo(tmp_path)
    clone = tmp_path / "clone"
    stage.detached_clone(source, clone, before)
    fixture = tmp_path / "fixture.py"
    fixture.write_text("FIXTURE = 1\n")
    paths = stage.immutable_input_paths(clone, [fixture])
    baseline = stage.immutable_checkpoint(paths)
    (clone / "test_prod.py").write_text("tampered\n")
    with pytest.raises(stage.GateError, match="test_config_fixture_mutation"):
        stage.assert_checkpoint_unchanged(baseline, stage.immutable_checkpoint(paths))


def test_pytest_plugin_full_reports_stream_hash_and_matching_fail_pass_fail(tmp_path):
    failure = "def test_behavior():\n    assert 1 == 2\n"
    passing = "def test_behavior():\n    assert 1 == 1\n"
    first_capture, first, first_raw = run_report(tmp_path, "initial", failure)
    patched_capture, patched, _ = run_report(tmp_path, "patched", passing)
    final_capture, final, final_raw = run_report(tmp_path, "final", failure)
    stage.validate_phase_reports(first, patched, final, ["test_sample.py::test_behavior"])
    assert {row["when"] for row in first["reports"]} == {"setup", "call", "teardown"}
    assert first["failure_fingerprint_payload"]["failures"][0]["exception_type"] == "AssertionError"
    assert first_capture["stdout"]["sha256"] == stage.sha256_file(tmp_path / "initial/stdout.raw")
    assert final_capture["stderr"]["sha256"] == stage.sha256_file(tmp_path / "final/stderr.raw")
    assert first["raw_report_sha256"] == stage.sha256_file(first_raw)
    assert final["raw_report_sha256"] == stage.sha256_file(final_raw)
    assert patched_capture["return_code"] == 0


@pytest.mark.parametrize("source,error", [
    ("import pytest\ndef test_behavior():\n    pytest.skip('no')\n", "patched_nonbehavioral_outcome"),
    ("import pytest\n@pytest.mark.xfail\ndef test_behavior():\n    assert False\n", "patched_nonbehavioral_outcome"),
])
def test_skip_and_xfail_are_rejected(tmp_path, source, error):
    failure = "def test_behavior():\n    assert 1 == 2\n"
    _, initial, _ = run_report(tmp_path, "initial", failure)
    _, report, _ = run_report(tmp_path, "phase", source)
    final = dict(initial)
    with pytest.raises(stage.GateError, match=error):
        stage.validate_phase_reports(initial, report, final, ["test_sample.py::test_behavior"])


def test_collection_error_is_recorded_and_rejected(tmp_path):
    _, report, _ = run_report(tmp_path, "phase", "def broken(:\n")
    assert report["collection_errors"]
    with pytest.raises(stage.GateError):
        stage.validate_phase_reports(report, report, report, [])


def test_mismatched_final_failure_is_rejected(tmp_path):
    _, initial, _ = run_report(tmp_path, "initial", "def test_behavior():\n    assert 1 == 2\n")
    _, final, _ = run_report(tmp_path, "final", "def test_behavior():\n    raise ValueError('different')\n")
    _, patched, _ = run_report(tmp_path, "patched", "def test_behavior():\n    assert True\n")
    with pytest.raises(stage.GateError, match="mismatched_final_failure"):
        stage.validate_phase_reports(initial, patched, final, ["test_sample.py::test_behavior"])


def test_namespace_drift_fails_before_patch_material_read(monkeypatch, tmp_path):
    repo, before, after, _, _ = synthetic_repo(tmp_path)
    binding = fake_binding(repo, before, after)
    called = False

    def forbidden_git(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("patch bytes read")

    monkeypatch.setattr(stage, "git", forbidden_git)
    with pytest.raises(stage.GateError, match="namespace_drift"):
        stage.recompute_clearance_then_patch_material(binding, lambda _: {"clear": True, "namespace_input_manifest_sha256": "x" * 64})
    assert called is False


def test_live_patch_material_is_derived_only_after_clearance(tmp_path):
    repo, before, after, before_bytes, after_bytes = synthetic_repo(tmp_path)
    binding = fake_binding(repo, before, after)
    material = stage.recompute_clearance_then_patch_material(
        binding, lambda _: {"clear": True, "namespace_input_manifest_sha256": "a" * 64}
    )
    assert material["before_bytes"] == before_bytes
    assert material["after_bytes"] == after_bytes
    assert material["clearance_recomputed_immediately"] is True


def test_pinned_snapshot_contract_records_materialization_order_and_residual_trust(tmp_path):
    repo, before, after, _, _ = synthetic_repo(tmp_path)
    binding = fake_binding(repo, before, after)
    pins = {"files": [], "manifest_sha256": "4" * 64}
    contract = stage.build_pinned_snapshot_contract([binding], pins)
    assert contract["record_type"] == "stage12594_private_pinned_snapshot_contract_v1"
    assert contract["snapshot_requirements"]["detached_git_snapshot"] == "required_before_any_future_replay"
    assert contract["snapshot_requirements"]["mutable_live_repository_tree_is_not_authority"] is True
    assert contract["snapshot_requirements"]["descriptor_safe_patch_write"] is True
    snapshot = contract["binding_snapshots"][0]
    assert snapshot["production_path"] == "prod.py"
    assert snapshot["namespace_input_manifest_sha256"] == "a" * 64
    assert snapshot["materialization_order"][:3] == [
        "validate_stage12593_pins",
        "recompute_namespace_clearance_from_live_inputs",
        "match_recomputed_namespace_manifest_to_pinned_manifest",
    ]
    assert "this_contract_does_not_make_replay_trustworthy_without_independent_security_review" in contract["residual_trust_assumptions"]
    assert contract["replay_trustworthy"] is False
    assert contract["training_admitted"] is False
    assert stage.HEX64.fullmatch(contract["contract_sha256"])


def test_pinned_snapshot_contract_rejects_bad_namespace_or_path(tmp_path):
    repo, before, after, _, _ = synthetic_repo(tmp_path)
    binding = fake_binding(repo, before, after)
    binding["binding_payload"]["production_patch"]["path"] = "../prod.py"
    with pytest.raises(stage.GateError, match="production_path_noncanonical"):
        stage.build_pinned_snapshot_contract([binding], {"manifest_sha256": "4" * 64})
    binding = fake_binding(repo, before, after)
    binding["binding_payload"]["namespace_clearance"]["namespace_input_manifest_sha256"] = "bad"
    with pytest.raises(stage.GateError, match="snapshot_namespace_manifest_invalid"):
        stage.build_pinned_snapshot_contract([binding], {"manifest_sha256": "4" * 64})


def test_stale_binding_pin_is_rejected(tmp_path):
    paths = {}
    pins = {}
    for name, source in {
        "stage12593_implementation": stage.S12593,
        "stage12593_private_bindings": stage.S12593_PRIVATE,
        "stage12593_summary": stage.S12593_SUMMARY,
        "stage12593_contract": stage.S12593_CONTRACT,
    }.items():
        target = tmp_path / source.name
        target.write_bytes(source.read_bytes())
        paths[name] = target
        pins[name] = stage.sha256_file(target)
    paths["stage12593_summary"].write_bytes(paths["stage12593_summary"].read_bytes() + b" ")
    with pytest.raises(stage.GateError, match="stale_binding"):
        stage.load_pinned_bindings(paths, pins)


def test_phase_isolation_bwrap_contract_and_writable_leakage(tmp_path):
    worktree = tmp_path / "worktree"
    fixture = tmp_path / "fixture"
    worktree.mkdir()
    fixture.mkdir()
    writable = stage.phase_directories(tmp_path / "phases", "initial")
    runtime_a = tmp_path / "runtime-a"
    runtime_b = tmp_path / "runtime-b"
    runtime_a.mkdir()
    runtime_b.mkdir()
    argv = stage.build_bwrap_argv(
        Path("/usr/bin/bwrap"), worktree, fixture, writable, ["python", "-V"],
        [runtime_a, runtime_b],
    )
    assert "--unshare-net" in argv and "--clearenv" in argv and "--tmpfs" in argv
    assert ["--ro-bind", "/", "/"] != argv[argv.index("--tmpfs") + 2:argv.index("--tmpfs") + 5]
    assert not any(argv[i:i + 3] == ["--ro-bind", "/", "/"] for i in range(len(argv) - 2))
    assert argv.count("--ro-bind") == 4 and argv.count("--bind") == 3
    before = stage.filesystem_manifest(worktree)
    (worktree / "leak").write_text("bad")
    with pytest.raises(stage.GateError, match="writable_state_leakage"):
        stage.assert_no_writable_leakage(before, stage.filesystem_manifest(worktree), list(writable.values()))


def test_public_leak_scan_catches_any_private_string_or_hash(tmp_path):
    export = tmp_path / "export"
    export.mkdir()
    for name in stage.PUBLIC_ALLOWLIST:
        (export / name).write_text("{}\n")
    secret_hash = "a" * 64
    (export / "summary.json").write_text(json.dumps({"leak": secret_hash}))
    report = stage.scan_public_tree(export, ["private-name", secret_hash])
    assert report["passed"] is False
    assert any("private_value" in leak for leak in report["leaks"])


def test_publish_is_nonexecuting_ordinal_only_and_boundary_blocked(tmp_path):
    repo, before, after, _, _ = synthetic_repo(tmp_path)
    first = fake_binding(repo, before, after)
    second = fake_binding(repo, before, after)
    first["binding_ref"] = "binding_secret_1"
    second["binding_ref"] = "binding_secret_2"
    bindings = [first, second]
    pins = {"files": [{"name": "private-pin", "sha256": "3" * 64}], "manifest_sha256": "4" * 64}
    out = tmp_path / "artifacts" / stage.STAGE
    external = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.publish_preflight(bindings, pins, out, external)
    pointers = [json.loads(line) for line in (out / "digest_pointers.jsonl").read_text().splitlines()]
    rendered = json.dumps(pointers, sort_keys=True)
    assert len(pointers) == 1
    assert pointers[0]["artifact_ref"] == "aggregate_private_replay_preflight"
    assert "binding_secret" not in rendered and "1" * 64 not in rendered and "2" * 64 not in rendered
    assert stage.HEX64.fullmatch(pointers[0]["aggregate_private_artifact_sha256"])
    assert_boundaries_false(summary)
    contract = json.loads((out / "contract.json").read_text())
    assert contract["downstream_boundary"]["causally_committed_pre_outcome_candidate_set"] == "absent_even_after_future_replay"
    assert contract["downstream_boundary"]["observed_stop_continue_decision"] == "absent_even_after_future_replay"
    assert contract["generic_attestation_authority"] is False
    assert "canonical_path_openat_hardening_deferred" not in summary["downstream_blockers"]
    assert "descriptor_safe_production_path_openat_no_symlink_traversal" in contract["filesystem_invariants"]
    assert "namespace_snapshot_and_materialization_toctou_hardening_deferred" not in summary["downstream_blockers"]
    assert "transactional_generation_publication_hardening_deferred" not in summary["downstream_blockers"]
    assert "independent_security_review_required" not in summary["downstream_blockers"]
    assert summary["decision"] == "BLOCKED_TRUSTED_REPLAY_NOT_EXECUTED"
    assert contract["pinned_snapshot_contract"] == "private_only_required_for_any_future_replay"
    assert contract["transactional_publication"] == "generation_manifest_committed_last_required"
    assert contract["independent_security_review"] == "private_review_passed_for_publication_generation"
    assert "pinned_namespace_manifest_matched_before_material_read" in contract["filesystem_invariants"]
    assert "publication_generation_manifest_committed_last" in contract["filesystem_invariants"]
    manifest = stage.assert_publication_generation(out, external)
    assert manifest["transactional_generation_publication"] is True
    assert manifest["commit_protocol"] == "atomic_file_replace_manifest_last_v1"
    assert summary["publication_generation_id"] == contract["publication_generation_id"]
    pointers_row = json.loads((out / "digest_pointers.jsonl").read_text().splitlines()[0])
    assert pointers_row["publication_generation_id"] == summary["publication_generation_id"]
    external_record = json.loads(external.read_text())
    assert external_record["publication_generation_id"] == summary["publication_generation_id"]
    assert external_record["publication_manifest_sha256"] == manifest["manifest_sha256"]
    private_review = json.loads((out / "private/independent_security_review.json").read_text())
    assert private_review["review_result"] == "passed_no_blocker_found"
    assert private_review["reviewed_publication_generation_id"] == summary["publication_generation_id"]
    assert private_review["review_does_not_authorize_execution"] is True
    assert private_review["review_does_not_make_replay_trustworthy"] is True
    assert private_review["replay_trustworthy"] is False
    private_snapshot = json.loads((out / "private/pinned_snapshot_contract.json").read_text())
    assert private_snapshot["snapshot_requirements"]["detached_git_snapshot"] == "required_before_any_future_replay"
    assert private_snapshot["replay_trustworthy"] is False
    assert private_snapshot["sealed_eval_eligible"] is False
    snapshot_secrets = stage.snapshot_secret_values(private_snapshot)
    assert stage.scan_public_tree(out, snapshot_secrets) == json.loads((out / "public_leak_scan.json").read_text())
    leaked_path = private_snapshot["binding_snapshots"][0]["production_path"]
    (out / "summary.json").write_text(json.dumps({"leak": leaked_path}))
    leaked_report = stage.scan_public_tree(out, snapshot_secrets)
    assert leaked_report["passed"] is False
    assert any("private_value:summary.json" in leak for leak in leaked_report["leaks"])
    with pytest.raises(stage.GateError, match="publication_manifest_file_digest_mismatch"):
        stage.assert_publication_generation(out, external)
    assert json.loads((out / "public_leak_scan.json").read_text())["passed"] is True
    assert external_record["authoritative"] is False


def test_publication_generation_rejects_unmanifested_private_file(tmp_path):
    repo, before, after, _, _ = synthetic_repo(tmp_path)
    first = fake_binding(repo, before, after)
    second = fake_binding(repo, before, after)
    first["binding_ref"] = "binding_secret_1"
    second["binding_ref"] = "binding_secret_2"
    out = tmp_path / "artifacts" / stage.STAGE
    external = tmp_path / "summaries" / f"{stage.STAGE}.json"
    stage.publish_preflight([first, second], {"files": [], "manifest_sha256": "4" * 64}, out, external)
    (out / "private" / "stale.json").write_text("{}")
    with pytest.raises(stage.GateError, match="publication_unmanifested_path_set_mismatch"):
        stage.assert_publication_generation(out, external)


def test_publication_generation_rejects_external_generation_drift(tmp_path):
    repo, before, after, _, _ = synthetic_repo(tmp_path)
    first = fake_binding(repo, before, after)
    second = fake_binding(repo, before, after)
    first["binding_ref"] = "binding_secret_1"
    second["binding_ref"] = "binding_secret_2"
    out = tmp_path / "artifacts" / stage.STAGE
    external = tmp_path / "summaries" / f"{stage.STAGE}.json"
    stage.publish_preflight([first, second], {"files": [], "manifest_sha256": "4" * 64}, out, external)
    record = json.loads(external.read_text())
    record["publication_generation_id"] = "0" * 64
    external.write_text(json.dumps(record))
    with pytest.raises(stage.GateError, match="external_generation_mismatch"):
        stage.assert_publication_generation(out, external)


def test_public_payload_scan_requires_generation_manifest_public_path():
    report = stage.scan_public_payloads({
        "contract.json": b"{}",
        "digest_pointers.jsonl": b"{}\n",
        "public_leak_scan.json": b"{}",
        "summary.json": b"{}",
    }, [])
    assert report["passed"] is False
    assert "missing_public_path:publication_manifest.json" in report["leaks"]


def test_cli_execute_is_permanently_rejected_and_no_authority_api_exists():
    source = SCRIPT.read_text()
    assert "FUTURE_AUTHORITY" not in source
    assert "require_future_authority" not in source
    assert not hasattr(stage, "require_future_authority")
    result = subprocess.run([str(stage.PYTHON), str(SCRIPT), "--execute"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert result.returncode != 0
    assert b"execution_not_supported_by_preflight_cli" in result.stderr


def test_mount_contract_rejects_reserved_env_and_protected_overlap(tmp_path):
    worktree = tmp_path / "worktree"
    fixture = tmp_path / "fixture"
    runtime = tmp_path / "runtime"
    for path in (worktree, fixture, runtime):
        path.mkdir()
    writable = stage.phase_directories(tmp_path / "phases", "initial")
    with pytest.raises(stage.GateError, match="reserved_environment_override"):
        stage.build_bwrap_argv(
            Path("/usr/bin/bwrap"), worktree, fixture, writable, ["python"], [runtime],
            {"HOME": "/attacker"},
        )
    bad = {"HOME": worktree, "TMPDIR": writable["TMPDIR"], "XDG_CACHE_HOME": writable["XDG_CACHE_HOME"]}
    with pytest.raises(stage.GateError, match="writable_protected_overlap"):
        stage.build_bwrap_argv(Path("/usr/bin/bwrap"), worktree, fixture, bad, ["python"], [runtime])


def test_sandbox_rejects_host_workspace_and_home_visibility(tmp_path):
    worktree = tmp_path / "worktree"
    fixture = tmp_path / "fixture"
    worktree.mkdir()
    fixture.mkdir()
    writable = stage.phase_directories(tmp_path / "phases", "initial")
    for sensitive in (stage.ROOT, Path.home()):
        with pytest.raises(stage.GateError, match="host_sensitive_mount_forbidden"):
            stage.build_bwrap_argv(
                Path("/usr/bin/bwrap"), worktree, fixture, writable, ["python"], [sensitive],
            )


def test_mount_contract_rejects_noncanonical_and_overlapping_runtime_roots(tmp_path):
    root = tmp_path / "runtime"
    child = root / "child"
    child.mkdir(parents=True)
    with pytest.raises(stage.GateError, match="readonly_roots_overlap"):
        stage.validate_mount_contract([root, child], [], [])
    alias = tmp_path / "alias"
    os.symlink(root, alias)
    with pytest.raises(stage.GateError, match="not_canonical"):
        stage.validate_mount_contract([alias], [], [])


def test_pytest_report_rejects_missing_duplicate_finish_and_exit_mismatch(tmp_path):
    capture, _, report = run_report(tmp_path, "valid", "def test_behavior():\n    assert True\n")
    rows = [json.loads(line) for line in report.read_text().splitlines()]
    cases = [
        ([row for row in rows if row["event"] != "session_finish"], "session_finish_count_mismatch", capture["return_code"]),
        (rows + [next(row for row in rows if row["event"] == "collection_finish")], "collection_finish_count_mismatch", capture["return_code"]),
        (rows + [next(row for row in rows if row["event"] == "runtest_report")], "duplicate_phase_report", capture["return_code"]),
        (rows, "exit_status_mismatch", 9),
    ]
    for index, (case_rows, error, return_code) in enumerate(cases):
        target = tmp_path / f"case-{index}.jsonl"
        target.write_text("".join(json.dumps(row) + "\n" for row in case_rows))
        with pytest.raises(stage.GateError, match=error):
            stage.parse_pytest_report(target, tmp_path / "valid", return_code)


def test_raw_report_digest_is_evidence_not_semantic_fingerprint(tmp_path):
    _, first, _ = run_report(tmp_path, "first", "def test_behavior():\n    assert 1 == 2\n")
    capture, final, raw = run_report(tmp_path, "final-semantic", "def test_behavior():\n    assert 1 == 2\n")
    raw.write_text(raw.read_text() + "\n")
    final = stage.parse_pytest_report(raw, tmp_path / "final-semantic", capture["return_code"])
    assert first["raw_report_sha256"] != final["raw_report_sha256"]
    assert first["failure_fingerprint_sha256"] == final["failure_fingerprint_sha256"]
    assert "raw_report_sha256" not in first["failure_fingerprint_payload"]
