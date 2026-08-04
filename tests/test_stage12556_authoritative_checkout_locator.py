from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("s12556", ROOT / "scripts/build_stage12556_authoritative_checkout_locator.py")
assert SPEC and SPEC.loader
M = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(M)


def git(path: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(path), *args], text=True, capture_output=True, check=True)
    return result.stdout.strip()


def mirror(root: Path, repo="org/repo", origin=None) -> tuple[Path, str, str]:
    path = root / repo.split("/")[0] / repo.split("/")[1]
    path.mkdir(parents=True)
    git(path, "init"); git(path, "config", "user.email", "t@example.com"); git(path, "config", "user.name", "T")
    (path / "file.txt").write_text("clean\n")
    git(path, "add", "file.txt"); git(path, "commit", "-m", "base")
    git(path, "remote", "add", "origin", origin or f"https://github.com/{repo}.git")
    return path, git(path, "rev-parse", "HEAD"), git(path, "rev-parse", "HEAD^{tree}")


def row(commit: str, split="train") -> dict:
    identity = {"canonical_repo": "org/repo", "base_commit": commit, "instance_id": "org__repo-1"}
    return {"candidate_id": "c1", "policy_split": split, "task_identity": identity,
            "task_identity_sha256": M.stable_hash(identity), "task_snapshot_sha256": "a" * 64,
            "patch": "must never propagate", "test_patch": "secret", "problem_statement": "secret"}


def test_clean_exact_mirror_success_and_no_gold_fields(tmp_path: Path):
    path, commit, tree = mirror(tmp_path)
    result = M.build([row(commit)], [tmp_path], 10)
    cert = result["certificates"][0]
    assert cert["base_tree"] == tree and cert["mirror_path"] == str(path)
    payload = json.dumps(result)
    assert "must never propagate" not in payload and "secret" not in payload
    assert result["worklist"][0]["replay_allowed"] is False


def test_wrong_origin_fails_closed(tmp_path: Path):
    _, commit, _ = mirror(tmp_path, origin="https://github.com/wrong/repo.git")
    result = M.build([row(commit)], [tmp_path], 10)
    assert not result["certificates"]
    assert "canonical_origin_identity_mismatch" in result["blocked"][0]["blocking_reasons"]


def test_missing_commit_fails_closed(tmp_path: Path):
    mirror(tmp_path)
    result = M.build([row("f" * 40)], [tmp_path], 10)
    assert "authoritative_base_commit_missing" in result["blocked"][0]["blocking_reasons"]


def test_duplicate_verified_mirrors_are_ambiguous(tmp_path: Path):
    first, commit, _ = mirror(tmp_path / "one")
    second = tmp_path / "two" / "org" / "repo"; second.parent.mkdir(parents=True)
    subprocess.run(["git", "clone", "-q", str(first), str(second)], check=True)
    git(second, "remote", "set-url", "origin", "https://github.com/org/repo.git")
    result = M.build([row(commit)], [tmp_path / "one", tmp_path / "two"], 10)
    assert not result["certificates"]
    assert "multiple_verified_local_mirrors_ambiguous" in result["blocked"][0]["blocking_reasons"]


def test_sealed_and_validation_excluded(tmp_path: Path):
    _, commit, _ = mirror(tmp_path)
    result = M.build([row(commit, "sealed_eval"), row(commit, "validation")], [tmp_path], 10)
    assert not result["certificates"] and not result["blocked"]
    assert result["summary"]["excluded_non_train_counts"] == {"sealed_eval": 1, "validation": 1}


def test_output_is_deterministic_and_bounded(tmp_path: Path):
    _, commit, _ = mirror(tmp_path)
    rows = [row(commit), {**row(commit), "candidate_id": "c2"}]
    a = M.build(rows, [tmp_path], 1)
    b = M.build(list(reversed(rows)), [tmp_path], 1)
    assert a == b and len(a["worklist"]) == 1
