from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.ipc as ipc
import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12554_authority_inventory_and_overlap_gate.py"
SPEC = importlib.util.spec_from_file_location("stage12554", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
REV = "a" * 40


def fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path, list[dict[str, object]]]:
    release = tmp_path / "open-swe"
    shard = release / "data/minimax_m25_openhands_trajectories/train-00000-of-00001.parquet"
    shard.parent.mkdir(parents=True)
    row = {
        "instance_id": "Owner__Repo-1", "repo": "Owner/Repo", "trajectory_id": "trajectory-1",
        "model_patch": "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-a\n+b\n",
        "trajectory": [{"role": "user", "content": "must not be emitted"}], "resolved": 1,
    }
    pq.write_table(pa.Table.from_pylist([row]), shard)
    digest = MODULE.file_sha256(shard)
    metadata = release / ".cache/huggingface/download/data/minimax_m25_openhands_trajectories/train-00000-of-00001.parquet.metadata"
    metadata.parent.mkdir(parents=True)
    metadata.write_text(f"{REV}\n{digest}\n", encoding="utf-8")
    (release / "README.md").write_text("instance_id values are from nebius/SWE-rebench-V2\n", encoding="utf-8")
    ref = tmp_path / "ref"
    ref.write_text(REV + "\n", encoding="utf-8")
    stage12550_row = {
        **row,
        "dataset_file": str(shard),
        "dataset_file_sha256": digest,
        "source_row_index_zero_based": 0,
    }
    binding = {
        "candidate_id": "c1", "canonical_repo": "owner/repo",
        "model_patch_sha256": hashlib.sha256(row["model_patch"].encode()).hexdigest(),
        "source_row_sha256": MODULE.stable_hash(stage12550_row),
        "source_native_identity": {
            "dataset_file": str(shard), "dataset_file_sha256": digest,
            "instance_id": row["instance_id"], "trajectory_id": row["trajectory_id"], "row_index_zero_based": 0,
        },
    }
    arrow = tmp_path / "verified.arrow"
    protected = pa.Table.from_pylist([{
        "instance_id": "Protected__Repo-1", "repo": "Protected/Repo", "base_commit": "b" * 40,
        "patch": "gold must not be read", "test_patch": "secret", "problem_statement": "secret",
    }])
    with arrow.open("wb") as handle:
        with ipc.new_stream(handle, protected.schema) as writer:
            writer.write_table(protected)
    info = tmp_path / "dataset_info.json"
    uri = f"hf://datasets/princeton-nlp/SWE-bench_Verified@{'c' * 40}/data/test-00000-of-00001.parquet"
    info.write_text(json.dumps({"download_checksums": {uri: {}}, "splits": {"test": {"num_examples": 1}}}), encoding="utf-8")
    return release, ref, arrow, info, [binding]


def test_exact_source_recovers_only_authority_fields_and_stays_blocked(tmp_path: Path) -> None:
    release, ref, arrow, info, bindings = fixture(tmp_path)
    result = MODULE.build(bindings, release, ref, arrow, info)
    row = result["resolved"][0]
    assert row["resolved_fields"]["trajectory_revision"]["value"] == REV
    assert row["resolved_fields"]["trajectory_instance_id"]["value"] == "Owner__Repo-1"
    assert "authoritative_base_commit" in row["blocked_fields"]
    assert row["overall_disposition"] == "blocked"
    assert result["summary"]["resolved_end_to_end_candidate_count"] == 0
    assert all(row[name] is False for name in MODULE.ZERO_FLAGS)


def test_shard_digest_tamper_fails_before_field_recovery(tmp_path: Path) -> None:
    release, ref, arrow, info, bindings = fixture(tmp_path)
    bindings[0]["source_native_identity"]["dataset_file_sha256"] = "d" * 64
    # The authoritative cache metadata remains decisive; a projected digest cannot replace it.
    shard = Path(bindings[0]["source_native_identity"]["dataset_file"])
    shard.write_bytes(shard.read_bytes() + b"tamper")
    result = MODULE.build(bindings, release, ref, arrow, info)
    assert result["resolved"] == []
    assert "shard_content_digest_missing_or_mismatched" in result["blocked"][0]["blocking_reasons"]


def test_protected_adapter_reads_allowlist_and_never_emits_content(tmp_path: Path) -> None:
    _, _, arrow, info, _ = fixture(tmp_path)
    manifest, reasons = MODULE.load_protected_manifest(arrow, info)
    # Synthetic fixture has one task, so completeness floor blocks authority but content exclusion remains testable.
    assert manifest is not None
    assert manifest["adapter_read_columns"] == list(MODULE.PROTECTED_COLUMNS)
    assert manifest["forbidden_columns_read"] == []
    encoded = json.dumps(manifest)
    assert "gold must not be read" not in encoded and "problem_statement" not in encoded
    assert "dataset_completeness_not_declared" in reasons


def test_unknown_swe_rebench_scope_keeps_overlap_unadjudicated(tmp_path: Path) -> None:
    release, ref, arrow, info, bindings = fixture(tmp_path)
    result = MODULE.build(bindings, release, ref, arrow, info)
    row = result["overlap"][0]
    assert row["coverage_status"] == "UNADJUDICATED"
    assert "swe_rebench_v2_protected_scope_missing" in row["blocking_reasons"]
    assert row["instance_only_join_used"] is False


def test_namespaced_keys_include_release_revision_split_and_instance(tmp_path: Path) -> None:
    release, ref, arrow, info, bindings = fixture(tmp_path)
    row = MODULE.build(bindings, release, ref, arrow, info)["resolved"][0]
    key = row["namespaced_trajectory_key"]
    assert key[:4] == [MODULE.OPEN_SWE_DATASET, REV, "openhands", "minimax_m25"]
    assert key[-1] == "trajectory-1"
    assert row["task_key_status"] == "unresolved_release_revision_and_split"


def test_cross_shard_audit_samples_every_shard_not_prefix(tmp_path: Path) -> None:
    release, _, _, _, _ = fixture(tmp_path)
    original = next((release / "data").glob("*_trajectories/*.parquet"))
    second = release / "data/qwen35_sweagent_trajectories/train-00000-of-00001.parquet"
    second.parent.mkdir(parents=True)
    second.write_bytes(original.read_bytes())
    digest = MODULE.file_sha256(second)
    metadata = release / ".cache/huggingface/download/data/qwen35_sweagent_trajectories/train-00000-of-00001.parquet.metadata"
    metadata.parent.mkdir(parents=True, exist_ok=True)
    metadata.write_text(f"{REV}\n{digest}\n", encoding="utf-8")
    audit = MODULE.cross_shard_audit(release, REV)
    assert audit["shard_count"] == 2
    assert audit["all_shards_sampled"] is True
    assert {row["split"] for row in audit["shards"]} == {"minimax_m25", "qwen35"}


def test_summary_explicitly_forbids_stage12551_patch_equality_path(tmp_path: Path) -> None:
    release, ref, arrow, info, bindings = fixture(tmp_path)
    summary = MODULE.build(bindings, release, ref, arrow, info)["summary"]
    assert summary["stage12551_authoritative_acceptance_invoked"] is False
    assert summary["stage12551_gold_patch_equality_contract_forbidden"] is True
    assert summary["stage12553_resolution_invoked"] is False
    assert summary["task_patch_equality_join_used"] is False
    assert summary["gold_or_reference_patch_read"] is False
