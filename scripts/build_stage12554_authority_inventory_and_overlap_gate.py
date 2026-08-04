#!/usr/bin/env python3
"""Build a fail-closed authority inventory before any replay resolution.

This stage reads only identity columns from protected task metadata. It never
reads gold patches, test patches, problem statements, or PR descriptions, and
it never joins a task record to a trajectory by patch equality or path text.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12554_authority_inventory_and_overlap_gate"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
DEFAULT_BINDINGS = ROOT / "runs/local/artifacts/stage12550_source_native_replay_eligibility_prefilter/recovery_worklist.jsonl"
DEFAULT_OPEN_SWE_ROOT = Path("/arxiv/datasets/nvidia--Open-SWE-Traces")
DEFAULT_OPEN_SWE_REF = Path("/data/.cache/huggingface/hub/datasets--nvidia--Open-SWE-Traces/refs/main")
DEFAULT_VERIFIED_ARROW = Path("/data/.cache/huggingface/datasets/princeton-nlp___swe-bench_verified/default/0.0.0/c104f840cc67f8b6eec6f759ebc8b2693d585d4a/swe-bench_verified-test.arrow")
DEFAULT_VERIFIED_INFO = DEFAULT_VERIFIED_ARROW.with_name("dataset_info.json")

SHA256_RE = re.compile(r"^[0-9a-f]{64}$", re.I)
REVISION_RE = re.compile(r"^[0-9a-f]{40}$", re.I)
OPEN_SWE_DATASET = "nvidia/Open-SWE-Traces"
UPSTREAM_TASK_DATASET = "nebius/SWE-rebench-V2"
VERIFIED_DATASET = "princeton-nlp/SWE-bench_Verified"
PROTECTED_COLUMNS = ("instance_id", "repo", "base_commit")
FORBIDDEN_PROTECTED_COLUMNS = {
    "patch", "gold_patch", "test_patch", "problem_statement", "pr_description",
    "hints_text", "FAIL_TO_PASS", "PASS_TO_PASS",
}
ZERO_FLAGS = {
    "admission_allowed": False,
    "training_allowed": False,
    "gpu_allowed": False,
    "replay_allowed": False,
    "root_credit": False,
    "repair_credit": False,
    "strict_eval_eligible": False,
}


def stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{number}: expected object")
            rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def canonical_repo(value: Any) -> str | None:
    text = str(value or "").strip().lower().replace("\\", "/")
    if text.startswith("https://github.com/"):
        text = text[len("https://github.com/"):]
    if text.endswith(".git"):
        text = text[:-4]
    text = text.strip("/")
    return text if text.count("/") == 1 and all(text.split("/")) else None


def parse_cache_metadata(path: Path) -> tuple[str | None, str | None]:
    if not path.is_file():
        return None, None
    parts = path.read_text(encoding="utf-8").splitlines()
    revision = parts[0].strip().lower() if parts else ""
    digest = parts[1].strip().lower() if len(parts) > 1 else ""
    return (
        revision if REVISION_RE.fullmatch(revision) else None,
        digest if SHA256_RE.fullmatch(digest) else None,
    )


def shard_coordinates(root: Path, shard: Path) -> tuple[str, str, str] | None:
    try:
        relative = shard.relative_to(root).as_posix()
    except ValueError:
        return None
    match = re.fullmatch(r"data/([^/]+)_trajectories/(train-\d{5}-of-\d{5}\.parquet)", relative)
    if not match:
        return None
    family, shard_id = match.groups()
    if family.endswith("_openhands"):
        split, config = family[:-len("_openhands")], "openhands"
    elif family.endswith("_sweagent"):
        split, config = family[:-len("_sweagent")], "sweagent"
    else:
        return None
    return config, split, shard_id


def provenance(value: Any, *, source: Path, revision: str, field: str, verification: str) -> dict[str, Any]:
    return {
        "value": value,
        "authority": "huggingface_dataset_publisher_cache",
        "source": str(source),
        "source_revision": revision,
        "source_field": field,
        "verification": verification,
    }


def blocked_field(reason: str, acquisition: str) -> dict[str, Any]:
    return {"status": "blocked", "reason": reason, "required_acquisition": acquisition}


def load_bound_open_swe_rows(
    bindings: list[dict[str, Any]], root: Path, revision: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    import pyarrow.parquet as pq  # type: ignore

    by_path: dict[Path, list[dict[str, Any]]] = {}
    for binding in bindings:
        identity = binding.get("source_native_identity")
        identity = identity if isinstance(identity, dict) else {}
        by_path.setdefault(Path(str(identity.get("dataset_file") or "")), []).append(binding)

    resolved: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    verified_shards: dict[str, str] = {}
    for shard, shard_bindings in sorted(by_path.items(), key=lambda item: str(item[0])):
        coords = shard_coordinates(root, shard)
        metadata = root / ".cache/huggingface/download" / shard.relative_to(root)
        metadata = metadata.with_name(metadata.name + ".metadata") if coords else metadata
        metadata_revision, metadata_digest = parse_cache_metadata(metadata)
        actual_digest = file_sha256(shard) if shard.is_file() else None
        shard_errors: list[str] = []
        if coords is None:
            shard_errors.append("shard_not_in_authoritative_release_layout")
        if metadata_revision != revision:
            shard_errors.append("shard_release_revision_binding_missing_or_mismatched")
        if metadata_digest is None or actual_digest != metadata_digest:
            shard_errors.append("shard_content_digest_missing_or_mismatched")
        if not shard_errors and actual_digest:
            verified_shards[str(shard)] = actual_digest

        table = None
        complete_row_digests: dict[int, str] = {}
        if not shard_errors:
            parquet = pq.ParquetFile(shard)
            required = {"instance_id", "repo", "trajectory_id", "model_patch"}
            if not required.issubset(parquet.schema_arrow.names):
                shard_errors.append("authoritative_trajectory_identity_schema_incomplete")
            else:
                table = parquet.read(columns=sorted(required))
                target_ordinals = sorted({
                    identity.get("row_index_zero_based")
                    for binding in shard_bindings
                    for identity in [binding.get("source_native_identity")]
                    if isinstance(identity, dict)
                    and isinstance(identity.get("row_index_zero_based"), int)
                    and not isinstance(identity.get("row_index_zero_based"), bool)
                })
                if target_ordinals:
                    targets = set(target_ordinals)
                    max_target = target_ordinals[-1]
                    offset = 0
                    for batch in parquet.iter_batches(batch_size=32):
                        for local_index, complete_row in enumerate(batch.to_pylist()):
                            ordinal = offset + local_index
                            if ordinal in targets:
                                stage12550_row = dict(complete_row)
                                stage12550_row["dataset_file"] = str(shard)
                                stage12550_row["dataset_file_sha256"] = actual_digest
                                stage12550_row["source_row_index_zero_based"] = ordinal
                                complete_row_digests[ordinal] = stable_hash(stage12550_row)
                        offset += batch.num_rows
                        if offset > max_target:
                            break
        for binding in shard_bindings:
            identity = binding.get("source_native_identity")
            identity = identity if isinstance(identity, dict) else {}
            ordinal = identity.get("row_index_zero_based")
            errors = list(shard_errors)
            source_row: dict[str, Any] | None = None
            if table is not None and isinstance(ordinal, int) and not isinstance(ordinal, bool) and 0 <= ordinal < table.num_rows:
                source_row = table.slice(ordinal, 1).to_pylist()[0]
            else:
                errors.append("source_row_ordinal_missing_or_out_of_range")
            if source_row is not None:
                checks = {
                    "instance_id": (identity.get("instance_id"), source_row.get("instance_id")),
                    "trajectory_id": (identity.get("trajectory_id"), source_row.get("trajectory_id")),
                    "canonical_repo": (canonical_repo(binding.get("canonical_repo")), canonical_repo(source_row.get("repo"))),
                    "model_patch_sha256": (
                        str(binding.get("model_patch_sha256") or "").lower(),
                        hashlib.sha256(str(source_row.get("model_patch") or "").encode()).hexdigest(),
                    ),
                }
                errors.extend(f"{name}_binding_mismatch" for name, pair in checks.items() if pair[0] != pair[1])
                # Stage12550 hashed the complete release row. Stream each shard once
                # and retain only requested ordinal digests instead of rereading the
                # trajectory-heavy shard for every binding.
                if complete_row_digests.get(ordinal) != str(binding.get("source_row_sha256") or "").lower():
                    errors.append("source_row_digest_binding_mismatch")
            if errors:
                blocked.append({
                    "record_type": "stage12554_blocked_authority_binding_v1",
                    "candidate_id": binding.get("candidate_id"),
                    "blocking_reasons": sorted(set(errors)),
                    "resolved_fields": {},
                    "blocked_fields": {},
                    "gold_or_reference_patch_read": False,
                    "task_patch_equality_join_used": False,
                    "dataset_path_identity_inference_used": False,
                    **ZERO_FLAGS,
                })
                continue
            assert source_row is not None and coords and actual_digest
            config, split, shard_id = coords
            source_row_digest = str(binding["source_row_sha256"]).lower()
            fields = {
                "trajectory_dataset": provenance(OPEN_SWE_DATASET, source=metadata, revision=revision, field="cache.repository", verification="publisher_cache_revision"),
                "trajectory_revision": provenance(revision, source=metadata, revision=revision, field="metadata.revision", verification="exact_40_hex_revision"),
                "trajectory_config": provenance(config, source=root / "README.md", revision=revision, field="configs.config_name", verification="release_manifest_layout_match"),
                "trajectory_split": provenance(split, source=root / "README.md", revision=revision, field="configs.data_files.split", verification="release_manifest_layout_match"),
                "trajectory_shard_id": provenance(shard_id, source=metadata, revision=revision, field="release_relative_shard", verification="release_manifest_layout_match"),
                "trajectory_shard_sha256": provenance(actual_digest, source=metadata, revision=revision, field="metadata.etag", verification="full_file_sha256_match"),
                "trajectory_ordinal": provenance(ordinal, source=shard, revision=revision, field="row_index_zero_based", verification="exact_ordinal"),
                "source_row_sha256": provenance(source_row_digest, source=shard, revision=revision, field="complete_row", verification="canonical_complete_row_sha256_match"),
                "trajectory_instance_id": provenance(source_row["instance_id"], source=shard, revision=revision, field="instance_id", verification="exact_value_match"),
                "trajectory_id": provenance(source_row["trajectory_id"], source=shard, revision=revision, field="trajectory_id", verification="exact_value_match"),
                "canonical_repo": provenance(canonical_repo(source_row["repo"]), source=shard, revision=revision, field="repo", verification="exact_canonical_value_match"),
                "model_patch_sha256": provenance(str(binding["model_patch_sha256"]).lower(), source=shard, revision=revision, field="model_patch", verification="candidate_output_sha256_match"),
                "upstream_task_dataset": provenance(UPSTREAM_TASK_DATASET, source=root / "README.md", revision=revision, field="Data Fields.instance_id", verification="publisher_declared_upstream_dataset"),
            }
            missing = {
                "task_release_revision": blocked_field("swe_rebench_v2_release_revision_missing", "immutable SWE-rebench-V2 snapshot"),
                "task_split": blocked_field("swe_rebench_v2_split_missing", "authoritative split membership"),
                "task_snapshot_sha256": blocked_field("swe_rebench_v2_snapshot_missing", "content-addressed task release manifest"),
                "authoritative_base_commit": blocked_field("base_commit_not_present_in_open_swe_release", "allowlisted SWE-rebench-V2 task metadata"),
                "authoritative_base_tree": blocked_field("verified_git_checkout_missing", "trusted repository mirror containing base commit"),
                "expected_post_tree": blocked_field("end_to_end_patch_application_not_run", "clean-index model-patch application"),
                "canonical_repo_lineage_id": blocked_field("trusted_repository_lineage_missing", "trusted remote/ref identity certificate"),
                "trajectory_sha256": blocked_field("trajectory_content_intentionally_not_read_for_selection", "separate non-selection content audit"),
            }
            resolved.append({
                "record_type": "stage12554_resolved_authority_fields_v1",
                "candidate_id": binding.get("candidate_id"),
                "namespaced_trajectory_key": [OPEN_SWE_DATASET, revision, config, split, shard_id, ordinal, source_row["trajectory_id"]],
                "task_key_status": "unresolved_release_revision_and_split",
                "resolved_fields": fields,
                "blocked_fields": missing,
                "overall_disposition": "blocked",
                "blocking_reasons": sorted({item["reason"] for item in missing.values()}),
                "gold_or_reference_patch_read": False,
                "task_patch_equality_join_used": False,
                "dataset_path_identity_inference_used": False,
                **ZERO_FLAGS,
            })
    return resolved, blocked, {"verified_shards": verified_shards}


def cross_shard_audit(root: Path, revision: str) -> dict[str, Any]:
    import pyarrow.parquet as pq  # type: ignore

    rows = []
    for shard in sorted((root / "data").glob("*_trajectories/*.parquet")):
        coords = shard_coordinates(root, shard)
        metadata = root / ".cache/huggingface/download" / shard.relative_to(root)
        metadata = metadata.with_name(metadata.name + ".metadata")
        metadata_revision, metadata_digest = parse_cache_metadata(metadata)
        try:
            parquet = pq.ParquetFile(shard)
            columns = [name for name in ("instance_id", "repo", "trajectory_id") if name in parquet.schema_arrow.names]
            identity_table = parquet.read(columns=columns)
        except Exception as error:
            rows.append({
                "shard": shard.relative_to(root).as_posix(),
                "config": coords[0] if coords else None,
                "split": coords[1] if coords else None,
                "declared_shard_sha256": metadata_digest,
                "revision_bound": metadata_revision == revision,
                "row_count": 0,
                "sample_ordinal": None,
                "sample_identity_sha256": None,
                "sampled_columns": [],
                "sampled_protected_content": False,
                "blocking_reasons": ["parquet_shard_unreadable_or_corrupt"],
                "error_type": type(error).__name__,
            })
            continue
        ordinal = int(stable_hash(shard.relative_to(root).as_posix())[:16], 16) % max(identity_table.num_rows, 1)
        sample = identity_table.slice(ordinal, 1).to_pylist()[0] if identity_table.num_rows else {}
        rows.append({
            "shard": shard.relative_to(root).as_posix(),
            "config": coords[0] if coords else None,
            "split": coords[1] if coords else None,
            "declared_shard_sha256": metadata_digest,
            "revision_bound": metadata_revision == revision,
            "row_count": parquet.metadata.num_rows,
            "sample_ordinal": ordinal,
            "sample_identity_sha256": stable_hash(sample),
            "sampled_columns": columns,
            "sampled_protected_content": False,
        })
    return {
        "record_type": "stage12554_cross_shard_authority_audit_v1",
        "release_revision": revision,
        "shard_count": len(rows),
        "all_shards_sampled": bool(rows) and all(row["sample_identity_sha256"] for row in rows),
        "all_shards_revision_bound": bool(rows) and all(row["revision_bound"] for row in rows),
        "shards": rows,
        **ZERO_FLAGS,
    }


def load_protected_manifest(arrow_path: Path, info_path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    import pyarrow.ipc as ipc  # type: ignore

    reasons: list[str] = []
    if not arrow_path.is_file() or not info_path.is_file():
        return None, ["swe_bench_verified_authoritative_cache_missing"]
    info = json.loads(info_path.read_text(encoding="utf-8"))
    checksums = info.get("download_checksums")
    checksums = checksums if isinstance(checksums, dict) else {}
    uris = sorted(checksums)
    revision_match = re.search(r"@([0-9a-f]{40})/", uris[0]) if len(uris) == 1 else None
    if not revision_match:
        return None, ["swe_bench_verified_pinned_revision_missing"]
    revision = revision_match.group(1).lower()
    with arrow_path.open("rb") as handle:
        try:
            table = ipc.open_file(handle).read_all()
        except Exception:
            handle.seek(0)
            table = ipc.open_stream(handle).read_all()
    missing = set(PROTECTED_COLUMNS) - set(table.schema.names)
    if missing:
        return None, ["protected_identity_schema_incomplete"]
    selected = table.select(PROTECTED_COLUMNS)
    tasks = []
    for row in selected.to_pylist():
        repo = canonical_repo(row.get("repo"))
        commit = str(row.get("base_commit") or "").lower()
        instance = row.get("instance_id")
        if repo is None or not isinstance(instance, str) or not instance or not REVISION_RE.fullmatch(commit):
            reasons.append("invalid_protected_task_identity")
            continue
        tasks.append({"instance_id": instance, "repo": repo, "base_commit": commit, "metadata_source": "authoritative_dataset_manifest"})
    dataset_id = f"{VERIFIED_DATASET}@{revision}"
    shard_digest = file_sha256(arrow_path)
    manifest: dict[str, Any] = {
        "record_type": "protected_task_universe_manifest_v1",
        "authoritative": True,
        "dataset_id": dataset_id,
        "declared_complete": not reasons and len(tasks) == selected.num_rows == 500,
        "expected_split_count": 1,
        "expected_shard_count": 1,
        "expected_task_count": selected.num_rows,
        "provenance": {
            "source_kind": "authoritative_dataset_release_manifest",
            "authority": "princeton-nlp/SWE-bench_Verified Hugging Face release",
            "source_uri": uris[0],
            "source_record_sha256": stable_hash({"dataset_info_sha256": file_sha256(info_path), "arrow_sha256": shard_digest}),
            "candidate_authored": False,
            "derived_from_protected_trajectory": False,
        },
        "splits": [{
            "split_id": "test",
            "declared_complete": not reasons and len(tasks) == selected.num_rows == 500,
            "expected_shard_count": 1,
            "expected_task_count": selected.num_rows,
            "shards": [{
                "shard_id": "test.arrow",
                "shard_sha256": shard_digest,
                "declared_complete": not reasons and len(tasks) == selected.num_rows == 500,
                "expected_task_count": selected.num_rows,
                "tasks": tasks,
            }],
        }],
        "adapter_read_columns": list(PROTECTED_COLUMNS),
        "forbidden_columns_read": [],
        "protected_split_train_eligible": False,
        **ZERO_FLAGS,
    }
    stage12552 = load_stage12552()
    manifest["dataset_snapshot_sha256"] = stage12552.manifest_snapshot_sha256(manifest)
    validation_reasons, _ = stage12552.validate_manifest(manifest)
    return manifest, sorted(set(reasons + validation_reasons))


def load_stage12552() -> Any:
    path = ROOT / "scripts/build_stage12552_protected_task_universe_validator.py"
    spec = importlib.util.spec_from_file_location("stage12552_for_stage12554", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load Stage12552 validator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def protected_audit(bindings: list[dict[str, Any]], manifest: dict[str, Any] | None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    protected = set()
    if manifest:
        for task in manifest["splits"][0]["shards"][0]["tasks"]:
            protected.add((task["repo"], task["instance_id"]))
    rows = []
    for binding in bindings:
        identity = binding.get("source_native_identity")
        identity = identity if isinstance(identity, dict) else {}
        unscoped = (canonical_repo(binding.get("canonical_repo")), str(identity.get("instance_id") or ""))
        rows.append({
            "record_type": "stage12554_namespaced_protected_overlap_adjudication_v1",
            "candidate_id": binding.get("candidate_id"),
            "candidate_task_key": [UPSTREAM_TASK_DATASET, None, None, unscoped[1]],
            "protected_namespace": manifest.get("dataset_id") if manifest else None,
            "protected_split": "test" if manifest else None,
            "unscoped_repo_instance_overlap": unscoped in protected,
            "coverage_status": "UNADJUDICATED",
            "blocking_reasons": ["swe_rebench_v2_protected_scope_missing", "candidate_task_revision_and_split_unresolved"],
            "instance_only_join_used": False,
            "gold_or_reference_patch_read": False,
            "protected_split_train_eligible": False,
            **ZERO_FLAGS,
        })
    return rows, {
        "unscoped_overlap_count": sum(row["unscoped_repo_instance_overlap"] for row in rows),
        "coverage_unadjudicated_count": len(rows),
    }


def build(
    bindings: list[dict[str, Any]], open_swe_root: Path, open_swe_ref: Path,
    verified_arrow: Path, verified_info: Path,
) -> dict[str, Any]:
    revision = open_swe_ref.read_text(encoding="utf-8").strip().lower() if open_swe_ref.is_file() else ""
    release_errors = [] if REVISION_RE.fullmatch(revision) else ["open_swe_pinned_revision_missing"]
    resolved: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    shard_state: dict[str, Any] = {"verified_shards": {}}
    if not release_errors:
        resolved, blocked, shard_state = load_bound_open_swe_rows(bindings, open_swe_root, revision)
    else:
        blocked = [{
            "record_type": "stage12554_blocked_authority_binding_v1",
            "candidate_id": row.get("candidate_id"),
            "blocking_reasons": release_errors,
            "resolved_fields": {}, "blocked_fields": {}, **ZERO_FLAGS,
        } for row in bindings]
    cross_shard = cross_shard_audit(open_swe_root, revision) if not release_errors else {
        "record_type": "stage12554_cross_shard_authority_audit_v1", "blocking_reasons": release_errors, **ZERO_FLAGS,
    }
    manifest, manifest_errors = load_protected_manifest(verified_arrow, verified_info)
    overlap_rows, overlap_counts = protected_audit(bindings, manifest)
    validator_result = None
    if manifest:
        stage12552 = load_stage12552()
        required = [manifest["dataset_id"], f"{UPSTREAM_TASK_DATASET}@UNRESOLVED"]
        validator_result = stage12552.validate_universe(bindings, [manifest], required)
    reasons = Counter(reason for row in resolved + blocked for reason in row.get("blocking_reasons", []))
    reasons.update({reason: len(bindings) for reason in manifest_errors})
    reasons["stage12551_gold_patch_equality_contract_forbidden"] += len(bindings)
    reasons["stage12551_stage12552_stage12553_schema_incompatible"] += len(bindings)
    reasons["swe_rebench_v2_authoritative_snapshot_not_local"] += len(bindings)
    summary = {
        "stage": STAGE,
        "record_type": "stage12554_authority_inventory_and_overlap_gate_summary_v1",
        "binding_count": len(bindings),
        "authoritative_trajectory_field_ledger_count": len(resolved),
        "hard_source_binding_failure_count": len(blocked),
        "overall_blocked_binding_count": len(bindings),
        "resolved_end_to_end_candidate_count": 0,
        "open_swe_revision": revision or None,
        "verified_bound_shard_count": len(shard_state["verified_shards"]),
        "release_shard_count": cross_shard.get("shard_count", 0),
        "release_shards_sampled_count": len(cross_shard.get("shards", [])),
        "candidate_bound_shard_count": len({str((row.get("source_native_identity") or {}).get("dataset_file")) for row in bindings}),
        "candidate_sampling_cross_shard": len({str((row.get("source_native_identity") or {}).get("dataset_file")) for row in bindings}) > 1,
        "protected_verified_manifest_valid": not manifest_errors and manifest is not None,
        "protected_verified_task_count": manifest["expected_task_count"] if manifest else 0,
        "protected_full_scope_valid": bool(validator_result and validator_result["inventory"]["universe_valid"]),
        **overlap_counts,
        "reason_counts": dict(sorted(reasons.items())),
        "stage12551_authoritative_acceptance_invoked": False,
        "stage12551_gold_patch_equality_contract_forbidden": True,
        "stage12552_validator_invoked": validator_result is not None,
        "stage12553_resolution_invoked": False,
        "end_to_end_real_source_fixture_passed": False,
        "gold_or_reference_patch_read": False,
        "protected_task_content_read": False,
        "task_patch_equality_join_used": False,
        "dataset_path_identity_inference_used": False,
        "default_disposition": "blocked",
        **ZERO_FLAGS,
    }
    return {
        "resolved": resolved,
        "blocked": blocked,
        "cross_shard": cross_shard,
        "manifest": manifest,
        "manifest_errors": manifest_errors,
        "overlap": overlap_rows,
        "validator_result": validator_result,
        "summary": summary,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bindings", type=Path, default=DEFAULT_BINDINGS)
    parser.add_argument("--open-swe-root", type=Path, default=DEFAULT_OPEN_SWE_ROOT)
    parser.add_argument("--open-swe-ref", type=Path, default=DEFAULT_OPEN_SWE_REF)
    parser.add_argument("--verified-arrow", type=Path, default=DEFAULT_VERIFIED_ARROW)
    parser.add_argument("--verified-info", type=Path, default=DEFAULT_VERIFIED_INFO)
    parser.add_argument("--output-dir", type=Path, default=OUT)
    parser.add_argument("--summary", type=Path, default=SUMMARY)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = build(read_jsonl(args.bindings), args.open_swe_root, args.open_swe_ref, args.verified_arrow, args.verified_info)
    write_jsonl(args.output_dir / "resolved_authority_fields.jsonl", result["resolved"])
    write_jsonl(args.output_dir / "blocked_bindings.jsonl", result["blocked"])
    write_json(args.output_dir / "cross_shard_authority_audit.json", result["cross_shard"])
    write_json(args.output_dir / "protected_swe_bench_verified_manifest.json", result["manifest"] or {"blocking_reasons": result["manifest_errors"], **ZERO_FLAGS})
    write_jsonl(args.output_dir / "protected_overlap_adjudications.jsonl", result["overlap"])
    write_json(args.output_dir / "protected_full_scope_inventory.json", result["validator_result"]["inventory"] if result["validator_result"] else {"universe_valid": False, **ZERO_FLAGS})
    write_json(args.output_dir / "summary.json", result["summary"])
    write_json(args.summary, result["summary"])
    print(json.dumps(result["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
