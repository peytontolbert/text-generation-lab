from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("stage12558", ROOT / "scripts/build_stage12558_combined_protected_universe_gate.py")
assert SPEC and SPEC.loader
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def task(repo: str = "org/repo", instance: str = "org__repo-1", commit: str = "a" * 40):
    return {"canonical_repo": repo, "instance_id": instance, "base_commit": commit}


def universe(tasks, complete=True):
    return {"universe_id": "u", "source_path": "x", "source_sha256": "1" * 64,
            "declared_complete": complete, "canonical_lineage_complete": complete, "tasks": tasks}


def test_complete_disjoint_universe_clears():
    result = M.adjudicate([task()], [universe([task("other/repo", "other__repo-2", "b" * 40)])])
    assert result["protected_clearance"] is True


def test_exact_overlap_blocks():
    result = M.adjudicate([task()], [universe([task()])])
    assert result["any_exact_task_overlap"] is True
    assert result["protected_clearance"] is False


def test_same_repo_different_task_blocks():
    result = M.adjudicate([task()], [universe([task("org/repo", "org__repo-2", "b" * 40)])])
    assert result["any_exact_task_overlap"] is False
    assert result["any_canonical_repo_overlap"] is True
    assert result["protected_clearance"] is False


def test_incomplete_or_empty_universe_blocks():
    assert M.adjudicate([task()], [universe([task("other/repo", "x", "b" * 40)], False)])["protected_clearance"] is False
    assert M.adjudicate([task()], [universe([], True)])["protected_clearance"] is False


def test_malformed_identity_blocks_completeness():
    result = M.adjudicate([task()], [universe([{"repo": "artifact-path", "instance_id": "x", "base_commit": "b" * 40}])])
    assert result["records"][0]["coverage_complete"] is False


def test_missing_or_invalid_source_digest_blocks_completeness():
    item = universe([task("other/repo", "x", "b" * 40)])
    item["source_sha256"] = None
    assert M.adjudicate([task()], [item])["protected_clearance"] is False


def test_output_is_deterministic():
    left = M.adjudicate([task()], [universe([task("other/repo", "x", "b" * 40)])])
    right = M.adjudicate([task()], [universe([task("other/repo", "x", "b" * 40)])])
    assert left == right
