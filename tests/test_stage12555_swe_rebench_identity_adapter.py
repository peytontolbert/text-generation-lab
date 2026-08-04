from __future__ import annotations

import importlib.util
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("stage12555", ROOT / "scripts/build_stage12555_swe_rebench_identity_adapter.py")
assert SPEC and SPEC.loader
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def fixture(tmp_path: Path, *, patch: str = "gold"):
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "tasks.parquet"
    rows = [
        {"instance_id": "Org__Repo-1", "repo": "Org/Repo", "base_commit": "a" * 40, "language": "Rust", "created_at": "2026-01-01", "patch": patch, "test_patch": "secret", "problem_statement": "secret", "pr_description": "secret", "FAIL_TO_PASS": ["x"], "PASS_TO_PASS": ["y"]},
        {"instance_id": "Other__Repo-2", "repo": "Other/Repo", "base_commit": "b" * 40, "language": "Python", "created_at": "2026-01-02", "patch": patch, "test_patch": "secret", "problem_statement": "secret", "pr_description": "secret", "FAIL_TO_PASS": ["x"], "PASS_TO_PASS": ["y"]},
    ]
    pq.write_table(pa.Table.from_pylist(rows), path)
    binding = {"candidate_id": "c1", "resolved_fields": {"canonical_repo": {"value": "org/repo"}, "trajectory_instance_id": {"value": "Org__Repo-1"}}}
    return path, M.file_sha256(path), [binding]


def test_exact_identity_join_reads_allowlist_and_stays_blocked(tmp_path: Path):
    path, digest, bindings = fixture(tmp_path)
    result = M.build(bindings, path, digest, M.REVISION)
    assert result["summary"]["exact_match_count"] == 1
    assert result["summary"]["adapter_read_columns"] == list(M.ALLOWED_COLUMNS)
    assert result["summary"]["forbidden_columns_read"] == []
    assert result["matched"][0]["training_allowed"] is False


def test_gold_mutation_does_not_change_identity_or_split(tmp_path: Path):
    p1, d1, bindings = fixture(tmp_path / "one", patch="gold one")
    p2, d2, _ = fixture(tmp_path / "two", patch="gold two")
    a = M.build(bindings, p1, d1, M.REVISION)["matched"][0]
    b = M.build(bindings, p2, d2, M.REVISION)["matched"][0]
    assert a["task_identity"] == b["task_identity"]
    assert a["policy_split"] == b["policy_split"]
    assert a["task_identity_sha256"] == b["task_identity_sha256"]


def test_repo_split_is_repo_disjoint(tmp_path: Path):
    path, digest, bindings = fixture(tmp_path)
    bindings.append({"candidate_id": "c2", "resolved_fields": {"canonical_repo": {"value": "org/repo"}, "trajectory_instance_id": {"value": "Org__Repo-1"}}})
    result = M.build(bindings, path, digest, M.REVISION)
    assert len({row["policy_split"] for row in result["matched"]}) == 1
    assert result["summary"]["repo_split_overlap"] is False


def test_corrupt_snapshot_fails_closed(tmp_path: Path):
    path, digest, bindings = fixture(tmp_path)
    result = M.build(bindings, path, "0" * 64, M.REVISION)
    assert result["matched"] == []
    assert result["summary"]["training_allowed"] is False


def test_exact_repo_and_instance_required(tmp_path: Path):
    path, digest, bindings = fixture(tmp_path)
    bindings[0]["resolved_fields"]["canonical_repo"]["value"] = "wrong/repo"
    result = M.build(bindings, path, digest, M.REVISION)
    assert result["matched"] == []
    assert "authoritative_task_exact_key_not_found" in result["blocked"][0]["blocking_reasons"]
