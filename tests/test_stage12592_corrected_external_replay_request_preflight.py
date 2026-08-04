import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12592_corrected_external_replay_request_preflight.py"
SPEC = importlib.util.spec_from_file_location("stage12592", SCRIPT)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


def test_four_per_bucket_and_twelve_repos_is_sufficient():
    ready, deficits = stage.readiness({bucket: 4 for bucket in stage.BUCKETS}, 12)
    assert ready
    assert not any(deficits.values())


def test_eight_per_bucket_is_nonblocking_reserve_only():
    ready, _ = stage.readiness({bucket: 4 for bucket in stage.BUCKETS}, 12)
    assert ready
    assert stage.RESERVE_TARGET == 8


def test_full_commit_with_tests_rejected_but_production_only_plan_accepted():
    changed = ["src/core.py", "tests/test_core.py"]
    full = stage.production_only_plan(changed, changed)
    production = stage.production_only_plan(changed, ["src/core.py"])
    assert not full["accepted"]
    assert not full["full_commit_allowed"]
    assert production["accepted"]
    assert production["selected_test_file_count"] == 0
    assert production["test_tree_hash_checkpoints"] == ["before", "fail", "pass", "revert"]


def test_exact_stage12547_identity_namespace_implementation():
    row = {"canonical_root_id": "RootCase", "root_id_hash": "abc", "canonical_lineage_id": "LineageCase"}
    roots, lineages = stage.stage12547_identity_tokens(row)
    assert roots == ["root:RootCase", "root:abc"]
    assert lineages == ["lineage:LineageCase"]


def test_unknown_protected_identity_is_blocked(monkeypatch, tmp_path):
    monkeypatch.setattr(stage, "PRIVATE_REPOSITORY_BASE", tmp_path)
    status, reasons = stage.resolve_identity({"repo_family": "missing"}, set(), {})
    assert status == "unknown"
    assert reasons == ["unknown_identity_resolution"]


def test_sanitized_manifest_has_no_outcome_or_sensitive_fields():
    candidate = {
        "candidate_id": "candidate-1", "bucket": "python", "repo_executor_ref": "repo-1",
        "source_evidence_ref": "source-1", "changed_file_count": 2,
        "changed_production_file_count": 1, "changed_test_file_count": 1,
        "commit_subject": "must not escape", "expected_outcome": "must not escape",
    }
    row = stage.sanitized_manifest_row(candidate)
    assert not stage.public_key_leaks(row)
    rendered = json.dumps(row)
    assert "commit_subject" not in rendered
    assert "expected_outcome" not in rendered
    assert "patch_summary" not in rendered


def test_verifier_sidecar_requires_executable_authoritative_offline_binding():
    assert stage.validate_verifier_binding({})
    valid = {
        "command_argv": ["pytest", "tests/test_x.py"], "selector": "tests/test_x.py",
        "environment_identity": "env-hash", "dependency_ready": True, "offline_ready": True,
        "authoritative_source_ref": "review-ref",
    }
    assert stage.validate_verifier_binding(valid) == []


def test_cleanliness_requirement_is_complete_and_timestamped():
    valid = {name: True for name in stage.CLEANLINESS_COMPONENTS}
    valid["attested_at_utc"] = "2026-01-01T00:00:00Z"
    valid["immediate_pre_execution_revalidation_required"] = True
    assert stage.validate_cleanliness_attestation(valid) == []
    assert set(stage.CLEANLINESS_COMPONENTS) == {
        "tracked", "untracked", "ignored", "submodules", "index", "symlinks",
        "modes", "lockfiles", "generated_state",
    }


def test_no_authority_build_emits_no_request(monkeypatch, tmp_path):
    monkeypatch.setattr(stage, "OUT", tmp_path / "out")
    monkeypatch.setattr(stage, "SUMMARY", tmp_path / "summary.json")
    monkeypatch.setattr(stage, "PRIVATE_AUTHORITY_INPUT", tmp_path / "missing.jsonl")
    monkeypatch.setattr(stage, "resolve_identity", lambda *args: ("resolved_clear", []))
    summary = stage.build()
    assert summary["no_authority"] is True
    assert summary["request_ready_count"] == 0
    assert summary["training_allowed"] is False
    assert (tmp_path / "out/external_replay_requests.jsonl").read_text() == ""


def test_ordered_contract_and_no_row_classes():
    assert stage.ORDERED_EVENTS == (
        "focused_verifier_fail", "apply_production_only_patch",
        "identical_focused_verifier_pass", "revert_production_patch",
        "identical_focused_verifier_fail_after_revert",
    )
