from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12578_prospective_source_acquisition_and_structural_preoutcome_seal.py"
SPEC = importlib.util.spec_from_file_location("stage12578", SCRIPT)
assert SPEC and SPEC.loader
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def clean_observation(_checkout: Path, remote: str, source_path: str):
    seed = M.stable_hash([remote, source_path])
    commit = seed[:40]
    tree = M.stable_hash([seed, "tree"])[:40]
    blob = M.stable_hash([seed, "blob"])[:40]
    content = M.stable_hash([seed, "content"])
    canonical = M.normalize_remote(remote)
    raw = {
        "canonical_remote": canonical,
        "commit_oid": commit,
        "tree_oid": tree,
        "source_path": source_path,
        "git_blob_oid": blob,
        "content_sha256": content,
    }
    return {
        **raw,
        "canonical_identity_hashes": {
            "remote_sha256": M.stable_hash(canonical),
            "commit_sha256": M.stable_hash(commit),
            "tree_sha256": M.stable_hash(tree),
            "path_sha256": M.stable_hash(source_path),
            "blob_oid_sha256": M.stable_hash(blob),
            "content_sha256": content,
        },
        "worktree_clean": True,
        "worktree_matches_committed_blob": True,
        "dirty_status_sha256": M.stable_hash(""),
        "lineage_sha256": M.stable_hash(raw),
    }


@pytest.fixture
def clean_default(monkeypatch):
    monkeypatch.setattr(M, "inspect_git", clean_observation)
    return M.build_stage(file_digests=dict(M.PINS))


def test_default_overlap_is_diagnostic_only_and_zero_sealed(clean_default):
    result = clean_default
    assert result["source_native_candidate_count"] == 0
    assert result["diagnostic_prospect_count"] == 4
    assert result["sealed_candidate_count"] == 0
    assert result["sealed_by_language"] == {"rust": 0, "web_js_ts_html": 0}
    assert all("normalized_protected_train_or_reserved_overlap" in row["reason_codes"] for row in result["diagnostic_prospects"])


def test_all_deny_fields_are_false(clean_default):
    assert all(clean_default[field] is False for field in M.DENY_FIELDS)
    assert clean_default["training_performed"] is False
    assert clean_default["evaluation_performed"] is False
    assert clean_default["admission_performed"] is False


def test_malformed_and_incomplete_universes_fail_closed(monkeypatch):
    monkeypatch.setattr(M, "inspect_git", clean_observation)
    incomplete = M.build_universe_ledger()
    assert any(reason.startswith("authority_closure_incomplete:") for reason in M.validate_universes(incomplete))

    malformed = incomplete[:-1]
    blockers = M.validate_universes(malformed)
    assert "authority_universe_not_exactly_12_artifacts" in blockers
    result = M.build_stage(file_digests=dict(M.PINS), universes=malformed)
    assert result["authority_closure_complete"] is False
    assert result["sealed_candidate_count"] == 0


def test_forbidden_outcome_field_in_universe_is_rejected():
    universes = M.build_universe_ledger()
    universes[0] = {**universes[0], "model_score": 0.99}
    blockers = M.validate_universes(universes)
    assert "outcome_field_in_universe:0" in blockers
    assert "malformed_universe:0" in blockers


def test_validate_caller_candidate_rejects_seal_self_attestation_and_score():
    record = {
        "name": "fabricated",
        "language": "web_js_ts_html",
        "canonical_remote": "https://github.com/example/project",
        "checkout": "/tmp/project",
        "source_path": "src/main.js",
        "preoutcome_seal_sha256": "a" * 64,
        "task_diff_evidence_verified": True,
        "model_score": 1.0,
    }
    blockers = M.validate_caller_candidate(record)
    assert "caller_precomputed_or_unknown_candidate_fields" in blockers
    assert "caller_outcome_fields_rejected" in blockers


def test_duplicate_roots_are_blocked():
    row = {"canonical_remote": "https://github.com/example/project", "source_path": "src/main.js"}
    assert M.duplicate_root_blockers([row, dict(row)]) == ["duplicate_root_or_source_dominance"]


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def test_revalidate_detects_content_mutation(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.name", "Stage12578 Test")
    _git(repo, "config", "user.email", "stage12578@example.test")
    _git(repo, "remote", "add", "origin", "https://github.com/example/project.git")
    source = repo / "src/main.js"
    source.parent.mkdir()
    source.write_text("export const value = 1;\n", encoding="utf-8")
    _git(repo, "add", "src/main.js")
    _git(repo, "commit", "-m", "fixture")

    observation = M.inspect_git(repo, "https://github.com/example/project", "src/main.js")
    source.write_text("export const value = 2;\n", encoding="utf-8")
    valid, blockers = M.revalidate_git_observation(observation, repo)
    assert valid is False
    assert "source_changed:worktree_clean" in blockers
    assert "source_changed:worktree_matches_committed_blob" in blockers


def test_source_pin_mismatch_blocks_and_gives_no_authority(monkeypatch):
    monkeypatch.setattr(M, "inspect_git", clean_observation)
    digests = dict(M.PINS)
    digests["active_protected"] = M.stable_hash("changed")
    result = M.build_stage(file_digests=digests)
    assert "source_file_pin_mismatch:active_protected" in result["blocking_reasons"]
    assert result["all_input_artifacts_pinned"] is False
    assert result["authority_closure_complete"] is False
    assert result["sealed_candidate_count"] == 0
    assert all(result[field] is False for field in M.DENY_FIELDS)


def test_crafted_complete_12_row_caller_universe_is_non_authoritative(monkeypatch):
    monkeypatch.setattr(M, "inspect_git", clean_observation)
    crafted = [
        {
            "universe_id": f"crafted_{index}",
            "role": ("protected", "train", "reserved")[index % 3],
            "complete": True,
            "entries": [f"unrelated_{index}"],
        }
        for index in range(12)
    ]
    result = M.build_stage(file_digests=dict(M.PINS), universes=crafted)
    assert "caller_universe_override_non_authoritative" in result["blocking_reasons"]
    assert result["exact_canonical_universe_binding"] is False
    assert result["authority_closure_complete"] is False
    assert result["source_native_candidate_count"] == 0
    assert result["diagnostic_prospect_count"] == 4


def test_normalized_universe_alias_collides_bddy_api_and_bddy_hyphen_api(monkeypatch):
    monkeypatch.setattr(M, "inspect_git", clean_observation)
    crafted = [
        {
            "universe_id": f"crafted_{index}",
            "role": "protected",
            "complete": True,
            "entries": ["bddy-api" if index == 0 else f"unrelated_{index}"],
        }
        for index in range(12)
    ]
    assert M.normalize_alias("bddy_api") == M.normalize_alias("bddy-api")
    result = M.build_stage(file_digests=dict(M.PINS), universes=crafted)
    bddy_api = next(
        row for row in result["diagnostic_prospects"]
        if row["lineage"]["canonical_remote"].endswith("/bddy-api")
    )
    assert "normalized_protected_train_or_reserved_overlap" in bddy_api["reason_codes"]
    assert result["source_native_candidate_count"] == 0


def test_duplicate_roots_normalize_https_ssh_git_and_path_aliases():
    records = [
        {
            "canonical_remote": "https://github.com/Example/repo-name.git",
            "source_path": "./src/task-file.ts",
        },
        {
            "canonical_remote": "git@github.com:example/repo_name",
            "source_path": "src/task_file.ts",
        },
    ]
    assert M.duplicate_root_blockers(records) == ["duplicate_root_or_source_dominance"]


def test_null_rows_and_null_or_non_list_entries_fail_closed(monkeypatch):
    monkeypatch.setattr(M, "inspect_git", clean_observation)
    assert M.validate_universes(None) == ["malformed_universe_collection"]

    null_row = M.build_universe_ledger()
    null_row[0] = None
    assert "malformed_universe:0" in M.validate_universes(null_row)
    result = M.build_stage(file_digests=dict(M.PINS), universes=null_row)
    assert "caller_universe_override_non_authoritative" in result["blocking_reasons"]
    assert result["source_native_candidate_count"] == 0

    null_entries = M.build_universe_ledger()
    null_entries[0] = {**null_entries[0], "entries": None}
    assert "malformed_universe:active_protected" in M.validate_universes(null_entries)

    non_list_entries = M.build_universe_ledger()
    non_list_entries[0] = {**non_list_entries[0], "entries": "not-a-list"}
    assert "malformed_universe:active_protected" in M.validate_universes(non_list_entries)


def test_revalidation_mutation_forces_diagnostic_classification(monkeypatch):
    monkeypatch.setattr(M, "inspect_git", clean_observation)
    calls: list[Path] = []

    def changed_after_inspection(_observation, checkout):
        calls.append(checkout)
        return False, ["source_changed:content_sha256"]

    monkeypatch.setattr(M, "revalidate_git_observation", changed_after_inspection)
    result = M.build_stage(file_digests=dict(M.PINS))
    assert len(calls) == 4
    assert result["source_native_candidate_count"] == 0
    assert result["diagnostic_prospect_count"] == 4
    assert all(
        "source_changed:content_sha256" in row["reason_codes"]
        for row in result["diagnostic_prospects"]
    )
    assert all(
        f"web_prospect_revalidation_failed:{name}" in result["blocking_reasons"]
        for name, *_rest in M.WEB_PROSPECTS
    )
