from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("stage12556", ROOT / "scripts/build_stage12556_local_checkout_readiness_census.py")
assert SPEC and SPEC.loader
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def git(repo: Path, *args: str):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, text=True, capture_output=True).stdout.strip()


def mirror(tmp_path: Path, origin: str = "https://github.com/org/repo.git"):
    repo = tmp_path / "org" / "repo"
    repo.mkdir(parents=True)
    git(repo, "init")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test")
    (repo / "a.txt").write_text("a")
    git(repo, "add", "a.txt")
    git(repo, "commit", "-m", "base")
    git(repo, "remote", "add", "origin", origin)
    return repo, git(repo, "rev-parse", "HEAD")


def binding(commit: str, split: str = "train", repo: str = "org/repo"):
    return {"candidate_id": "c", "policy_split": split, "task_key": ["d", "r", "train", "i"], "task_identity": {"canonical_repo": repo, "base_commit": commit, "language": "python"}}


def test_exact_origin_and_reachable_commit_is_readiness_only(tmp_path: Path):
    repo, commit = mirror(tmp_path)
    result = M.build([binding(commit)], [tmp_path])
    assert result["summary"]["exact_checkout_object_ready_count"] == 1
    assert result["ready"][0]["training_allowed"] is False
    assert result["ready"][0]["level3_credit"] is False


def test_wrong_origin_blocks(tmp_path: Path):
    _, commit = mirror(tmp_path, "https://github.com/other/repo.git")
    result = M.build([binding(commit)], [tmp_path])
    assert result["ready"] == []
    assert "canonical_origin_mirror_missing" in result["blocked"][0]["blocking_reasons"]


def test_missing_commit_blocks(tmp_path: Path):
    mirror(tmp_path)
    result = M.build([binding("f" * 40)], [tmp_path])
    assert result["ready"] == []
    assert "authoritative_base_commit_object_missing" in result["blocked"][0]["blocking_reasons"]


def test_protected_rows_are_not_enumerated(tmp_path: Path):
    _, commit = mirror(tmp_path)
    result = M.build([binding(commit, "sealed_eval")], [tmp_path])
    assert result["ready"] == [] and result["blocked"] == []
    assert result["summary"]["protected_binding_count_excluded"] == 1


def test_duplicate_valid_mirrors_block_as_ambiguous(tmp_path: Path):
    first, commit = mirror(tmp_path / "one")
    second = tmp_path / "two" / "org" / "repo"
    second.parent.mkdir(parents=True)
    subprocess.run(["git", "clone", str(first), str(second)], check=True, capture_output=True)
    git(second, "remote", "set-url", "origin", "https://github.com/org/repo.git")
    result = M.build([binding(commit)], [tmp_path])
    assert result["ready"] == []
    assert "multiple_valid_local_mirrors_ambiguous" in result["blocked"][0]["blocking_reasons"]
