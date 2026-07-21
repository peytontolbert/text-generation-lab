from __future__ import annotations

import copy
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12552_protected_task_universe_validator.py"
SPEC = importlib.util.spec_from_file_location("stage12552", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

COMMIT = "a" * 40


def task(**updates: object) -> dict[str, object]:
    value: dict[str, object] = {
        "instance_id": "Owner__Repo-1",
        "repo": "Owner/Repo",
        "base_commit": COMMIT,
        "metadata_source": "authoritative_dataset_manifest",
    }
    value.update(updates)
    return value


def manifest(tasks: list[dict[str, object]] | None = None, **updates: object) -> dict[str, object]:
    task_rows = tasks if tasks is not None else [task()]
    value: dict[str, object] = {
        "record_type": "protected_task_universe_manifest_v1",
        "authoritative": True,
        "dataset_id": "swe-bench/verified@release-1",
        "declared_complete": True,
        "expected_split_count": 1,
        "expected_shard_count": 1,
        "expected_task_count": len(task_rows),
        "provenance": {
            "source_kind": "authoritative_dataset_release_manifest",
            "authority": "dataset-publisher",
            "source_uri": "https://example.invalid/releases/1/manifest.json",
            "source_record_sha256": "1" * 64,
            "candidate_authored": False,
            "derived_from_protected_trajectory": False,
        },
        "splits": [{
            "split_id": "test",
            "declared_complete": True,
            "expected_shard_count": 1,
            "expected_task_count": len(task_rows),
            "shards": [{
                "shard_id": "shard-0",
                "shard_sha256": "2" * 64,
                "declared_complete": True,
                "expected_task_count": len(task_rows),
                "tasks": task_rows,
            }],
        }],
    }
    value.update(updates)
    value["dataset_snapshot_sha256"] = MODULE.manifest_snapshot_sha256(value)
    return value


def recovery(**updates: object) -> dict[str, object]:
    value: dict[str, object] = {
        "candidate_id": "candidate-1",
        "canonical_repo": "owner/repo",
        "source_native_identity": {"instance_id": "Owner__Repo-1"},
    }
    value.update(updates)
    return value


def validate(
    manifests: list[dict[str, object]],
    rows: list[dict[str, object]] | None = None,
    required: list[str] | None = None,
) -> dict[str, object]:
    return MODULE.validate_universe(
        rows or [recovery()], manifests, required or ["swe-bench/verified@release-1"]
    )


def test_complete_authoritative_manifest_adjudicates_overlap_and_clear() -> None:
    result = validate([manifest()], [recovery(), recovery(candidate_id="c2", source_native_identity={"instance_id": "other-2"})])
    assert result["inventory"]["universe_valid"] is True
    assert [row["coverage_status"] for row in result["adjudications"]] == ["overlap", "clear"]
    assert all(all(row[name] is False for name in MODULE.ZERO_FLAGS) for row in result["adjudications"])


def test_filename_spoof_never_creates_coverage() -> None:
    spoof = manifest([task(instance_id="different-2")])
    spoof["splits"][0]["shards"][0]["filename"] = "Owner__Repo-1-protected-test.parquet"
    spoof["dataset_snapshot_sha256"] = MODULE.manifest_snapshot_sha256(spoof)
    result = validate([spoof])
    assert result["adjudications"][0]["coverage_status"] == "clear"
    assert result["inventory"]["filename_or_path_coverage_inference_used"] is False


def test_empty_task_universe_is_invalid_and_unadjudicated() -> None:
    result = validate([manifest([])])
    assert result["adjudications"][0]["coverage_status"] == "unadjudicated"
    assert "protected_task_universe_empty" in result["inventory"]["blocking_reasons"]
    assert "positive_dataset_task_count_not_declared" in result["inventory"]["blocking_reasons"]


def test_missing_shard_fails_closed_for_every_recovery_row() -> None:
    bad = manifest()
    bad["splits"][0]["expected_shard_count"] = 2
    bad["expected_shard_count"] = 2
    bad["dataset_snapshot_sha256"] = MODULE.manifest_snapshot_sha256(bad)
    result = validate([bad], [recovery(), recovery(candidate_id="c2")])
    assert [row["coverage_status"] for row in result["adjudications"]] == ["unadjudicated", "unadjudicated"]
    assert "shard_inventory_incomplete" in result["inventory"]["blocking_reasons"]


def test_duplicate_repo_alias_is_ambiguous() -> None:
    result = validate([manifest([task(), task(repo="Owner__Repo")])])
    assert result["inventory"]["universe_valid"] is False
    assert "duplicate_canonical_task_identity_or_alias" in result["inventory"]["blocking_reasons"]


def test_conflicting_repo_for_instance_is_ambiguous() -> None:
    result = validate([manifest([task(), task(repo="Other/Repo")])])
    assert "conflicting_task_repo_identities" in result["inventory"]["blocking_reasons"]


def test_conflicting_base_commit_is_ambiguous() -> None:
    result = validate([manifest([task(), task(base_commit="b" * 40)])])
    assert "conflicting_task_base_commits" in result["inventory"]["blocking_reasons"]


def test_snapshot_mismatch_fails_closed() -> None:
    bad = manifest()
    bad["dataset_snapshot_sha256"] = "f" * 64
    result = validate([bad])
    assert "dataset_snapshot_digest_mismatch" in result["inventory"]["blocking_reasons"]
    assert result["adjudications"][0]["coverage_status"] == "unadjudicated"


def test_metadata_sourced_from_protected_trajectory_is_rejected() -> None:
    bad = manifest([task(metadata_source="protected_trajectory")])
    bad["provenance"]["source_kind"] = "protected_trajectory"
    bad["provenance"]["derived_from_protected_trajectory"] = True
    bad["dataset_snapshot_sha256"] = MODULE.manifest_snapshot_sha256(bad)
    result = validate([bad])
    assert "authoritative_manifest_provenance_missing_or_untrusted" in result["inventory"]["blocking_reasons"]
    assert "task_metadata_source_untrusted_or_trajectory_derived" in result["inventory"]["blocking_reasons"]


def test_missing_manifest_leaves_all_rows_unadjudicated_and_flags_false() -> None:
    result = MODULE.validate_universe([recovery(), recovery(candidate_id="c2")], [], [])
    assert all(row["coverage_status"] == "unadjudicated" for row in result["adjudications"])
    assert all(all(row[name] is False for name in MODULE.ZERO_FLAGS) for row in result["adjudications"])


def test_missing_required_dataset_blocks_globally() -> None:
    result = validate([manifest()], required=["swe-rebench/test@release-1"])
    assert result["adjudications"][0]["coverage_status"] == "unadjudicated"
    assert "required_protected_dataset_missing" in result["inventory"]["blocking_reasons"]
    assert "unexpected_protected_dataset_manifest" in result["inventory"]["blocking_reasons"]


def test_partial_multi_dataset_scope_blocks_globally() -> None:
    result = validate(
        [manifest()],
        required=["swe-bench/verified@release-1", "swe-rebench/test@release-1"],
    )
    assert result["inventory"]["universe_valid"] is False
    assert result["adjudications"][0]["coverage_status"] == "unadjudicated"
    assert "required_protected_dataset_missing" in result["inventory"]["blocking_reasons"]


def test_snapshot_binds_task_inventory_not_filename() -> None:
    original = manifest()
    renamed = copy.deepcopy(original)
    renamed["splits"][0]["shards"][0]["filename"] = "anything-at-all.bin"
    assert MODULE.manifest_snapshot_sha256(renamed) == MODULE.manifest_snapshot_sha256(original)
    changed = copy.deepcopy(original)
    changed["splits"][0]["shards"][0]["tasks"][0]["base_commit"] = "b" * 40
    assert MODULE.manifest_snapshot_sha256(changed) != MODULE.manifest_snapshot_sha256(original)
