from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12551_open_swe_upstream_identity_and_checkout_resolver.py"
SPEC = importlib.util.spec_from_file_location("stage12551", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

DATASET = "/authoritative/open-swe/train-000.parquet"
INSTANCE = "Owner__Repo-123"
DATASET_SHA = "8" * 64
ROW_INDEX = 17
PATCH = "diff --git a/value.txt b/value.txt\n--- a/value.txt\n+++ b/value.txt\n@@ -1 +1 @@\n-old\n+new\n"
SOURCE_ROW_SHA = "6" * 64


def run(*args: str, cwd: Path) -> str:
    result = subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=True)
    return result.stdout.strip()


def recovery(**updates: object) -> dict[str, object]:
    row: dict[str, object] = {
        "candidate_id": "candidate-1",
        "source_native_identity": {
            "dataset_file": DATASET,
            "instance_id": INSTANCE,
            "trajectory_id": "trajectory-not-an-authority",
            "dataset_file_sha256": DATASET_SHA,
            "row_index_zero_based": ROW_INDEX,
        },
        "canonical_repo": "Owner/Repo",
        "model_patch_sha256": hashlib.sha256(PATCH.encode()).hexdigest(),
        "source_dataset_file_sha256": DATASET_SHA,
        "source_row_index_zero_based": ROW_INDEX,
        "source_row_sha256": SOURCE_ROW_SHA,
        "trajectory": [{"content": "git rev-parse HEAD\n" + "f" * 40}],
    }
    row.update(updates)
    return row


def source(commit: str, **updates: object) -> dict[str, object]:
    row: dict[str, object] = {
        "record_type": "open_swe_upstream_task_record_v1",
        "authoritative": True,
        "dataset_file": DATASET,
        "instance_id": INSTANCE,
        "repo": "Owner/Repo",
        "dataset_file_sha256": DATASET_SHA,
        "source_row_index_zero_based": ROW_INDEX,
        "trajectory_id": "trajectory-not-an-authority",
        "source_row_sha256": SOURCE_ROW_SHA,
        "base_commit": commit,
        "base_commit_source": "upstream_task_record",
        "patch": PATCH,
        "patch_source": "upstream_task_record",
    }
    row.update(updates)
    return row


def make_mirror(tmp_path: Path, *, remote: str = "https://github.com/Owner/Repo.git") -> tuple[Path, str]:
    work = tmp_path / "work"
    work.mkdir()
    run("git", "init", "-q", cwd=work)
    run("git", "config", "user.name", "Stage Test", cwd=work)
    run("git", "config", "user.email", "stage@example.invalid", cwd=work)
    (work / "value.txt").write_text("old\n", encoding="utf-8")
    run("git", "add", "value.txt", cwd=work)
    run("git", "commit", "-qm", "base", cwd=work)
    commit = run("git", "rev-parse", "HEAD", cwd=work)
    mirrors = tmp_path / "mirrors"
    mirrors.mkdir()
    mirror = mirrors / "owner__repo.git"
    run("git", "clone", "-q", "--bare", str(work), str(mirror), cwd=tmp_path)
    run("git", "remote", "set-url", "origin", remote, cwd=mirror)
    return mirrors, commit


def snapshot(path: Path) -> dict[str, str]:
    return {
        str(item.relative_to(path)): hashlib.sha256(item.read_bytes()).hexdigest()
        for item in sorted(path.rglob("*"))
        if item.is_file()
    }


def resolve(rows: list[dict[str, object]], metadata: list[dict[str, object]], roots: list[Path]) -> dict[str, list[dict[str, object]]]:
    return MODULE.resolve_rows(rows, metadata, roots)


def test_exact_authoritative_join_resolves_verified_checkout(tmp_path: Path) -> None:
    mirrors, commit = make_mirror(tmp_path)
    result = resolve([recovery()], [source(commit)], [mirrors])
    assert len(result["resolved"]) == 1
    row = result["resolved"][0]
    assert row["canonical_repo"] == "owner/repo"
    assert row["base_commit"] == commit
    assert row["checkout_binding"]["patch_applicability_verified"] is True
    assert row["protected_universe_status"] == "unresolved_separate_gate"
    assert all(row[name] is False for name in MODULE.ZERO_FLAGS)


def test_metadata_only_sha_without_git_object_remains_unresolved(tmp_path: Path) -> None:
    mirrors, _ = make_mirror(tmp_path)
    result = resolve([recovery()], [source("a" * 40)], [mirrors])
    assert not result["resolved"]
    assert "authoritative_base_commit_git_object_missing" in result["unresolved"][0]["blocking_reasons"]


def test_repo_alias_normalization() -> None:
    aliases = [
        "Owner/Repo",
        "Owner__Repo",
        "https://github.com/Owner/Repo.git",
        "git@github.com:Owner/Repo.git",
    ]
    assert {MODULE.canonical_repo(alias) for alias in aliases} == {"owner/repo"}


def test_conflicting_base_commits_are_blocked(tmp_path: Path) -> None:
    mirrors, commit = make_mirror(tmp_path)
    other = "b" * 40 if commit != "b" * 40 else "c" * 40
    result = resolve([recovery()], [source(commit), source(other)], [mirrors])
    assert not result["resolved"]
    assert "conflicting_authoritative_base_commits" in result["conflicting"][0]["blocking_reasons"]


def test_wrong_remote_is_blocked(tmp_path: Path) -> None:
    mirrors, commit = make_mirror(tmp_path, remote="https://github.com/wrong/repository.git")
    result = resolve([recovery()], [source(commit)], [mirrors])
    assert "canonical_upstream_remote_identity_mismatch" in result["conflicting"][0]["blocking_reasons"]


def test_missing_mirror_is_unresolved(tmp_path: Path) -> None:
    result = resolve([recovery()], [source("a" * 40)], [tmp_path / "absent"])
    assert "configured_local_git_mirror_missing" in result["unresolved"][0]["blocking_reasons"]


def test_duplicate_identical_source_rows_are_deduped(tmp_path: Path) -> None:
    mirrors, commit = make_mirror(tmp_path)
    record = source(commit)
    result = resolve([recovery()], [record, json.loads(json.dumps(record))], [mirrors])
    assert len(result["resolved"]) == 1
    assert not result["conflicting"]


def test_shell_derived_sha_is_never_accepted(tmp_path: Path) -> None:
    mirrors, commit = make_mirror(tmp_path)
    shell_record = source(commit, base_commit_source="trajectory_shell_output")
    result = resolve([recovery()], [shell_record], [mirrors])
    assert "authoritative_upstream_source_record_missing" in result["unresolved"][0]["blocking_reasons"]


def test_nonapplicable_patch_is_blocked(tmp_path: Path) -> None:
    mirrors, commit = make_mirror(tmp_path)
    bad_patch = "diff --git a/value.txt b/value.txt\n--- a/value.txt\n+++ b/value.txt\n@@ -1 +1 @@\n-does-not-exist\n+new\n"
    result = resolve(
        [recovery(model_patch_sha256=hashlib.sha256(bad_patch.encode()).hexdigest())],
        [source(commit, patch=bad_patch)],
        [mirrors],
    )
    assert "authoritative_patch_not_applicable_at_base" in result["conflicting"][0]["blocking_reasons"]


def test_resolution_does_not_mutate_mirror(tmp_path: Path) -> None:
    mirrors, commit = make_mirror(tmp_path)
    mirror = mirrors / "owner__repo.git"
    before = snapshot(mirror)
    result = resolve([recovery()], [source(commit)], [mirrors])
    after = snapshot(mirror)
    assert len(result["resolved"]) == 1
    assert after == before


def test_nonexact_dataset_or_instance_does_not_join(tmp_path: Path) -> None:
    mirrors, commit = make_mirror(tmp_path)
    result = resolve([recovery()], [source(commit, dataset_file=DATASET + ".similar")], [mirrors])
    assert "authoritative_upstream_source_record_missing" in result["unresolved"][0]["blocking_reasons"]


def test_patch_digest_mismatch_is_blocked_before_git_resolution(tmp_path: Path) -> None:
    mirrors, commit = make_mirror(tmp_path)
    result = resolve([recovery(model_patch_sha256="9" * 64)], [source(commit)], [mirrors])
    assert not result["resolved"]
    assert "model_patch_binding_mismatch" in result["conflicting"][0]["blocking_reasons"]


def test_dataset_snapshot_mismatch_is_blocked_before_git_resolution(tmp_path: Path) -> None:
    mirrors, commit = make_mirror(tmp_path)
    result = resolve([recovery(source_dataset_file_sha256="7" * 64)], [source(commit)], [mirrors])
    assert not result["resolved"]
    assert "dataset_snapshot_binding_mismatch" in result["conflicting"][0]["blocking_reasons"]


def test_source_row_ordinal_mismatch_is_blocked_before_git_resolution(tmp_path: Path) -> None:
    mirrors, commit = make_mirror(tmp_path)
    result = resolve([recovery(source_row_index_zero_based=18)], [source(commit)], [mirrors])
    assert not result["resolved"]
    assert "source_row_ordinal_binding_mismatch" in result["conflicting"][0]["blocking_reasons"]


def test_repo_mismatch_is_blocked_before_git_resolution(tmp_path: Path) -> None:
    mirrors, commit = make_mirror(tmp_path)
    result = resolve([recovery(canonical_repo="Other/Repo")], [source(commit)], [mirrors])
    assert not result["resolved"]
    assert "canonical_repo_binding_mismatch" in result["conflicting"][0]["blocking_reasons"]


def test_trajectory_identity_mismatch_is_blocked(tmp_path: Path) -> None:
    mirrors, commit = make_mirror(tmp_path)
    result = resolve([recovery()], [source(commit, trajectory_id="other")], [mirrors])
    assert "trajectory_identity_binding_mismatch" in result["conflicting"][0]["blocking_reasons"]


def test_source_row_hash_mismatch_is_blocked(tmp_path: Path) -> None:
    mirrors, commit = make_mirror(tmp_path)
    result = resolve([recovery()], [source(commit, source_row_sha256="5" * 64)], [mirrors])
    assert "source_row_hash_binding_mismatch" in result["conflicting"][0]["blocking_reasons"]
