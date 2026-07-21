from __future__ import annotations

import copy
import hashlib
import importlib.util
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12553_namespace_separated_replay_resolver.py"
SPEC = importlib.util.spec_from_file_location("stage12553", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

H = {
    "trajectory_snapshot_sha256": "1" * 64,
    "trajectory_shard_sha256": "2" * 64,
    "source_row_sha256": "3" * 64,
    "trajectory_sha256": "4" * 64,
    "task_snapshot_sha256": "5" * 64,
    "protected_inventory_sha256": "6" * 64,
    "protected_policy_sha256": "7" * 64,
    "repository_identity_sha256": "8" * 64,
}


def git(repo: Path, *args: str, env: dict[str, str] | None = None, input_text: str | None = None) -> str:
    clean = os.environ.copy()
    if env:
        clean.update(env)
    result = subprocess.run(
        ["git", "-C", str(repo), *args], check=True, text=True, input=input_text,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=clean,
    )
    return result.stdout.strip()


def post_tree(repo: Path, commit: str, patch: str) -> str:
    with tempfile.TemporaryDirectory() as temp:
        env = {"GIT_INDEX_FILE": str(Path(temp) / "index")}
        git(repo, "read-tree", commit, env=env)
        git(repo, "apply", "--cached", "-", env=env, input_text=patch)
        return git(repo, "write-tree", env=env)


def repository(tmp_path: Path) -> tuple[Path, str, str, str, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "remote", "add", "origin", "https://github.com/Owner/Repo.git")
    target = repo / "value.txt"
    target.write_text("before\n", encoding="utf-8")
    git(repo, "add", "value.txt")
    git(
        repo, "-c", "user.email=stage12553@example.invalid", "-c",
        "user.name=Stage12553", "commit", "-qm", "base",
    )
    commit = git(repo, "rev-parse", "HEAD")
    base_tree = git(repo, "rev-parse", "HEAD^{tree}")
    git(repo, "tag", "trusted-snapshot", commit)
    target.write_text("after\n", encoding="utf-8")
    patch = git(repo, "diff", "--", "value.txt") + "\n"
    target.write_text("before\n", encoding="utf-8")
    return repo, commit, base_tree, patch, post_tree(repo, commit, patch)


def make_binding(commit: str, base_tree: str, patch: str, result_tree: str) -> dict[str, Any]:
    return {
        "candidate_id": "candidate-1",
        "canonical_repo": "Owner/Repo",
        "source_native_identity": {
            "instance_id": "trajectory-native-id-must-not-be-used",
            "task_namespace": "swe-bench/verified@release-1",
            "task_instance_id": "Owner__Repo-1",
            "trajectory_namespace": "open-swe-traces@snapshot-1",
            "trajectory_snapshot_sha256": H["trajectory_snapshot_sha256"],
            "trajectory_shard_id": "train-00000-of-00020",
            "trajectory_shard_sha256": H["trajectory_shard_sha256"],
            "trajectory_ordinal": 7,
            "source_row_sha256": H["source_row_sha256"],
            "trajectory_sha256": H["trajectory_sha256"],
            "model_patch_sha256": hashlib.sha256(patch.encode()).hexdigest(),
            "task_snapshot_sha256": H["task_snapshot_sha256"],
            "protected_inventory_sha256": H["protected_inventory_sha256"],
            "protected_policy_sha256": H["protected_policy_sha256"],
            "authoritative_base_commit": commit,
            "authoritative_base_tree": base_tree,
            "expected_post_tree": result_tree,
        },
        "dataset_file": "/spoof/Owner__Repo-1.parquet",
    }


def make_task(repo: Path, commit: str, base_tree: str) -> dict[str, Any]:
    row: dict[str, Any] = {
        "record_type": "authoritative_task_record_v1",
        "authoritative": True,
        "task_namespace": "swe-bench/verified@release-1",
        "task_instance_id": "Owner__Repo-1",
        "task_snapshot_sha256": H["task_snapshot_sha256"],
        "canonical_repo": "owner/repo",
        "repo_lineage": ["https://github.com/Owner/Repo.git", "git@github.com:owner/repo.git"],
        "base_commit": commit,
        "base_tree": base_tree,
        "repo_root": str(repo),
        "trusted_ref": "refs/tags/trusted-snapshot",
        "trusted_ref_tip": commit,
        "trusted_ref_immutable": True,
        "repository_identity_authority": "trusted-dataset-release",
        "repository_identity_sha256": H["repository_identity_sha256"],
    }
    row["canonical_repo_lineage_id"] = MODULE.expected_lineage_id(row, "owner/repo")
    return row


def make_patch(patch: str, result_tree: str, lineage_id: str) -> dict[str, Any]:
    return {
        "record_type": "exact_trajectory_model_patch_v1",
        "trajectory_namespace": "open-swe-traces@snapshot-1",
        "trajectory_snapshot_sha256": H["trajectory_snapshot_sha256"],
        "trajectory_shard_id": "train-00000-of-00020",
        "trajectory_shard_sha256": H["trajectory_shard_sha256"],
        "trajectory_ordinal": 7,
        "source_row_sha256": H["source_row_sha256"],
        "trajectory_sha256": H["trajectory_sha256"],
        "model_patch_sha256": hashlib.sha256(patch.encode()).hexdigest(),
        "model_patch": patch,
        "canonical_repo": "owner/repo",
        "canonical_repo_lineage_id": lineage_id,
        "expected_post_tree": result_tree,
    }


def bind_lineage(binding: dict[str, Any], lineage_id: str) -> None:
    binding["source_native_identity"]["canonical_repo_lineage_id"] = lineage_id


def make_protected(binding: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
    trace_key = MODULE.trajectory_key(binding)
    task_key = MODULE._explicit_task_key(binding)
    assert trace_key and task_key
    lineage_id = task["canonical_repo_lineage_id"]
    certificate = MODULE.resolution_certificate_payload(binding, task, trace_key, task_key, lineage_id)
    return {
        "record_type": "validated_protected_membership_adjudication_v1",
        "validated": True,
        "task_namespace": task_key[0],
        "task_instance_id": task_key[1],
        "task_snapshot_sha256": H["task_snapshot_sha256"],
        "canonical_repo": "OWNER/REPO",
        "protected_status": "CLEAR",
        **certificate,
        "resolution_certificate_sha256": MODULE.stable_hash(certificate),
    }


def bundle(tmp_path: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], str]:
    repo, commit, base_tree, patch, result_tree = repository(tmp_path)
    binding = make_binding(commit, base_tree, patch, result_tree)
    task = make_task(repo, commit, base_tree)
    bind_lineage(binding, task["canonical_repo_lineage_id"])
    patch_row = make_patch(patch, result_tree, task["canonical_repo_lineage_id"])
    protected = make_protected(binding, task)
    return binding, task, protected, patch_row, patch


def run(rows: tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], str]) -> dict[str, Any]:
    binding, task, protected, patch_row, _ = rows
    return MODULE.resolve_replay_candidates([binding], [task], [protected], [patch_row])[0]


def test_positive_resolution_emits_trees_and_certificate(tmp_path: Path) -> None:
    result = run(bundle(tmp_path))
    assert result["resolution_status"] == "resolved_replay_candidate"
    assert len(result["pre_tree_id"]) == len(result["post_index_tree_id"]) == 40
    assert result["pre_tree_id"] != result["post_index_tree_id"]
    assert len(result["resolution_certificate_sha256"]) == 64
    assert all(result[name] is False for name in MODULE.ZERO_FLAGS)


def test_missing_task_namespace_never_falls_back_to_trajectory_instance(tmp_path: Path) -> None:
    rows = bundle(tmp_path)
    binding = rows[0]
    del binding["source_native_identity"]["task_namespace"]
    del binding["source_native_identity"]["task_instance_id"]
    binding["source_native_identity"]["instance_id"] = rows[1]["task_instance_id"]
    result = run(rows)
    assert result["resolution_status"] == "blocked"
    assert "explicit_task_namespace_missing_from_trajectory_binding" in result["blocking_reasons"]
    assert "explicit_task_instance_id_missing_from_trajectory_binding" in result["blocking_reasons"]
    assert result["trajectory_instance_id_fallback_used"] is False


def test_hash_only_binding_requires_separate_patch_bytes(tmp_path: Path) -> None:
    binding, task, protected, _, _ = bundle(tmp_path)
    result = MODULE.resolve_replay_candidates([binding], [task], [protected], [])[0]
    assert result["resolution_status"] == "unresolved"


def test_cross_spliced_protected_clearance_blocks(tmp_path: Path) -> None:
    rows = bundle(tmp_path)
    rows[2]["trajectory_key_sha256"] = "9" * 64
    result = run(rows)
    assert "protected_certificate_trajectory_key_sha256_mismatch" in result["blocking_reasons"]


def test_self_attested_clear_without_certificate_blocks(tmp_path: Path) -> None:
    rows = bundle(tmp_path)
    for name in list(MODULE.resolution_certificate_payload(
        rows[0], rows[1], MODULE.trajectory_key(rows[0]), MODULE._explicit_task_key(rows[0]),
        rows[1]["canonical_repo_lineage_id"],
    )):
        rows[2].pop(name)
    rows[2].pop("resolution_certificate_sha256")
    assert run(rows)["resolution_status"] == "blocked"


def test_mutated_trusted_ref_blocks(tmp_path: Path) -> None:
    rows = bundle(tmp_path)
    repo = Path(rows[1]["repo_root"])
    tree = git(repo, "rev-parse", "HEAD^{tree}")
    other = git(repo, "commit-tree", tree, input_text="other\n")
    git(repo, "tag", "-f", "trusted-snapshot", other)
    result = run(rows)
    assert "trusted_ref_tip_mismatch_or_missing" in result["blocking_reasons"]


def test_base_unreachable_from_pinned_trusted_ref_blocks(tmp_path: Path) -> None:
    rows = bundle(tmp_path)
    binding, task, _, patch_row, _ = rows
    repo = Path(task["repo_root"])
    other = git(repo, "commit-tree", task["base_tree"], input_text="unrelated\n")
    git(repo, "tag", "-f", "trusted-snapshot", other)
    task["trusted_ref_tip"] = other
    task["canonical_repo_lineage_id"] = MODULE.expected_lineage_id(task, "owner/repo")
    bind_lineage(binding, task["canonical_repo_lineage_id"])
    patch_row["canonical_repo_lineage_id"] = task["canonical_repo_lineage_id"]
    rows = (binding, task, make_protected(binding, task), patch_row, rows[4])
    assert "authoritative_base_not_reachable_from_trusted_ref" in run(rows)["blocking_reasons"]


def test_replace_refs_block(tmp_path: Path) -> None:
    rows = bundle(tmp_path)
    repo = Path(rows[1]["repo_root"])
    replacement = git(repo, "commit-tree", rows[1]["base_tree"], input_text="replacement\n")
    git(repo, "replace", rows[1]["base_commit"], replacement)
    assert "replace_refs_forbidden" in run(rows)["blocking_reasons"]


def test_shallow_repository_blocks(tmp_path: Path) -> None:
    rows = bundle(tmp_path)
    repo = Path(rows[1]["repo_root"])
    (repo / ".git" / "shallow").write_text(rows[1]["base_commit"] + "\n")
    assert "shallow_repository_forbidden" in run(rows)["blocking_reasons"]


def test_object_alternates_block(tmp_path: Path) -> None:
    rows = bundle(tmp_path)
    repo = Path(rows[1]["repo_root"])
    path = repo / ".git" / "objects" / "info" / "alternates"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("/tmp/untrusted-objects\n")
    assert "object_alternates_forbidden" in run(rows)["blocking_reasons"]


def test_promisor_partial_clone_state_blocks(tmp_path: Path) -> None:
    rows = bundle(tmp_path)
    git(Path(rows[1]["repo_root"]), "config", "remote.origin.promisor", "true")
    result = run(rows)
    assert "promisor_or_partial_clone_forbidden" in result["blocking_reasons"]


def test_uncontrolled_local_git_config_blocks(tmp_path: Path) -> None:
    rows = bundle(tmp_path)
    git(Path(rows[1]["repo_root"]), "config", "core.hooksPath", "/tmp/hooks")
    assert "uncontrolled_local_git_config_forbidden" in run(rows)["blocking_reasons"]


def test_synthetic_origin_without_identity_certificate_blocks(tmp_path: Path) -> None:
    rows = bundle(tmp_path)
    for name in ("trusted_ref", "trusted_ref_tip", "trusted_ref_immutable",
                 "repository_identity_authority", "repository_identity_sha256",
                 "canonical_repo_lineage_id"):
        rows[1].pop(name)
    assert run(rows)["resolution_status"] == "blocked"


def test_base_tree_mismatch_blocks(tmp_path: Path) -> None:
    rows = bundle(tmp_path)
    binding, task, _, patch_row, _ = rows
    task["base_tree"] = "9" * 40
    binding["source_native_identity"]["authoritative_base_tree"] = "9" * 40
    rows = (binding, task, make_protected(binding, task), patch_row, rows[4])
    assert "authoritative_base_tree_mismatch" in run(rows)["blocking_reasons"]


def test_resulting_tree_binding_mismatch_blocks(tmp_path: Path) -> None:
    rows = bundle(tmp_path)
    binding, task, _, patch_row, _ = rows
    binding["source_native_identity"]["expected_post_tree"] = "9" * 40
    patch_row["expected_post_tree"] = "9" * 40
    rows = (binding, task, make_protected(binding, task), patch_row, rows[4])
    assert "resulting_tree_binding_mismatch" in run(rows)["blocking_reasons"]


def test_reference_patch_never_applied(tmp_path: Path) -> None:
    rows = bundle(tmp_path)
    rows[3]["reference_patch"] = "not a patch"
    rows[3]["gold_patch"] = "also not a patch"
    result = run(rows)
    assert result["resolution_status"] == "resolved_replay_candidate"
    assert result["reference_or_gold_patch_applied"] is False


def test_duplicate_task_authority_fails_closed(tmp_path: Path) -> None:
    binding, task, protected, patch_row, _ = bundle(tmp_path)
    result = MODULE.resolve_replay_candidates(
        [binding], [task, copy.deepcopy(task)], [protected], [patch_row],
    )[0]
    assert result["blocking_reasons"] == ["authoritative_task_record_ambiguous"]
