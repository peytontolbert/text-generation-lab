#!/usr/bin/env python3
"""Validate authoritative protected-task universe manifests and adjudicate Stage12550 rows.

Coverage is derived only from task records inside validated manifests. Paths and
filenames are deliberately excluded from all identity and coverage decisions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12552_protected_task_universe_validator"
INPUT = ROOT / "runs/local/artifacts/stage12550_source_native_replay_eligibility_prefilter/recovery_worklist.jsonl"
OUT = ROOT / "runs/local/artifacts" / STAGE
ADJUDICATION_OUT = OUT / "coverage_adjudications.jsonl"
INVALID_OUT = OUT / "invalid_manifests.jsonl"
INVENTORY_OUT = OUT / "validated_inventory.json"
OUT_SUMMARY = OUT / "summary.json"
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

SHA256_RE = re.compile(r"^[0-9a-f]{64}$", re.I)
FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$", re.I)
SAFE_REPO_PART_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
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
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def canonical_repo(value: Any) -> str | None:
    text = str(value or "").strip().replace("\\", "/")
    if text.startswith("git@github.com:"):
        text = text.split(":", 1)[1]
    elif "://" in text:
        parsed = urlparse(text)
        if parsed.hostname not in {"github.com", "www.github.com"}:
            return None
        text = parsed.path
    text = text.strip("/")
    if text.lower().endswith(".git"):
        text = text[:-4]
    parts = text.split("/")
    if len(parts) == 1 and "__" in text:
        parts = text.split("__", 1)
    if len(parts) != 2 or not all(SAFE_REPO_PART_RE.fullmatch(part) for part in parts):
        return None
    return f"{parts[0].lower()}/{parts[1].lower()}"


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected object")
    return value


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


def snapshot_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    """Return the immutable dataset material; location and filenames are irrelevant."""
    splits = []
    for split in manifest.get("splits", []) if isinstance(manifest.get("splits"), list) else []:
        shards = []
        for shard in split.get("shards", []) if isinstance(split, dict) and isinstance(split.get("shards"), list) else []:
            tasks = []
            for task in shard.get("tasks", []) if isinstance(shard, dict) and isinstance(shard.get("tasks"), list) else []:
                tasks.append({key: task.get(key) for key in ("instance_id", "repo", "base_commit", "metadata_source")} if isinstance(task, dict) else {"invalid_task": task})
            shards.append({key: shard.get(key) for key in ("shard_id", "shard_sha256", "declared_complete", "expected_task_count")} | {"tasks": tasks} if isinstance(shard, dict) else {"invalid_shard": shard})
        splits.append({key: split.get(key) for key in ("split_id", "declared_complete", "expected_shard_count", "expected_task_count")} | {"shards": shards} if isinstance(split, dict) else {"invalid_split": split})
    return {
        "dataset_id": manifest.get("dataset_id"),
        "declared_complete": manifest.get("declared_complete"),
        "expected_split_count": manifest.get("expected_split_count"),
        "expected_shard_count": manifest.get("expected_shard_count"),
        "expected_task_count": manifest.get("expected_task_count"),
        "splits": splits,
    }


def manifest_snapshot_sha256(manifest: dict[str, Any]) -> str:
    return stable_hash(snapshot_payload(manifest))


def _valid_provenance(value: Any) -> bool:
    return bool(
        isinstance(value, dict)
        and value.get("source_kind") == "authoritative_dataset_release_manifest"
        and isinstance(value.get("authority"), str) and value["authority"].strip()
        and isinstance(value.get("source_uri"), str) and value["source_uri"].strip()
        and SHA256_RE.fullmatch(str(value.get("source_record_sha256") or ""))
        and value.get("candidate_authored") is False
        and value.get("derived_from_protected_trajectory") is False
    )


def validate_manifest(manifest: dict[str, Any]) -> tuple[list[str], list[dict[str, Any]]]:
    reasons: list[str] = []
    tasks: list[dict[str, Any]] = []
    if manifest.get("record_type") != "protected_task_universe_manifest_v1":
        reasons.append("unsupported_manifest_record_type")
    if manifest.get("authoritative") is not True or not _valid_provenance(manifest.get("provenance")):
        reasons.append("authoritative_manifest_provenance_missing_or_untrusted")
    if not isinstance(manifest.get("dataset_id"), str) or not manifest["dataset_id"].strip():
        reasons.append("canonical_dataset_identity_missing")
    if manifest.get("declared_complete") is not True:
        reasons.append("dataset_completeness_not_declared")
    if manifest.get("dataset_snapshot_sha256") != manifest_snapshot_sha256(manifest):
        reasons.append("dataset_snapshot_digest_mismatch")

    splits = manifest.get("splits")
    if not isinstance(splits, list) or not splits:
        reasons.append("explicit_split_inventory_missing")
        splits = []
    if manifest.get("expected_split_count") != len(splits):
        reasons.append("split_inventory_incomplete")
    split_ids = [split.get("split_id") for split in splits if isinstance(split, dict)]
    if len(split_ids) != len(set(split_ids)) or any(not isinstance(item, str) or not item for item in split_ids):
        reasons.append("duplicate_or_invalid_split_identity")

    shard_total = 0
    dataset_actual_task_total = 0
    dataset_declared_task_total = 0
    shard_keys: set[tuple[str, str]] = set()
    for split in splits:
        if not isinstance(split, dict):
            reasons.append("invalid_split_record")
            continue
        if split.get("declared_complete") is not True:
            reasons.append("split_completeness_not_declared")
        shards = split.get("shards")
        if not isinstance(shards, list) or not shards:
            reasons.append("explicit_shard_inventory_missing")
            shards = []
        if split.get("expected_shard_count") != len(shards):
            reasons.append("shard_inventory_incomplete")
        shard_total += len(shards)
        split_actual_task_total = 0
        split_declared_task_total = 0
        for shard in shards:
            if not isinstance(shard, dict):
                reasons.append("invalid_shard_record")
                continue
            shard_id = shard.get("shard_id")
            key = (str(split.get("split_id") or ""), str(shard_id or ""))
            if not isinstance(shard_id, str) or not shard_id or key in shard_keys:
                reasons.append("duplicate_or_invalid_shard_identity")
            shard_keys.add(key)
            if shard.get("declared_complete") is not True:
                reasons.append("shard_completeness_not_declared")
            if not SHA256_RE.fullmatch(str(shard.get("shard_sha256") or "")):
                reasons.append("immutable_shard_digest_missing")
            shard_tasks = shard.get("tasks")
            if not isinstance(shard_tasks, list):
                reasons.append("explicit_shard_task_inventory_missing")
                continue
            shard_expected_tasks = shard.get("expected_task_count")
            if not isinstance(shard_expected_tasks, int) or isinstance(shard_expected_tasks, bool) or shard_expected_tasks <= 0:
                reasons.append("positive_shard_task_count_not_declared")
            if shard_expected_tasks != len(shard_tasks):
                reasons.append("shard_task_inventory_incomplete")
            split_actual_task_total += len(shard_tasks)
            if isinstance(shard_expected_tasks, int) and not isinstance(shard_expected_tasks, bool):
                split_declared_task_total += shard_expected_tasks
            for task in shard_tasks:
                if not isinstance(task, dict):
                    reasons.append("invalid_task_record")
                    continue
                repo = canonical_repo(task.get("repo"))
                instance = task.get("instance_id")
                commit = str(task.get("base_commit") or "").lower()
                if repo is None or not isinstance(instance, str) or not instance:
                    reasons.append("canonical_repo_instance_identity_missing")
                if not FULL_SHA_RE.fullmatch(commit):
                    reasons.append("authoritative_base_commit_missing")
                if task.get("metadata_source") != "authoritative_dataset_manifest":
                    reasons.append("task_metadata_source_untrusted_or_trajectory_derived")
                tasks.append({
                    "dataset_id": manifest.get("dataset_id"),
                    "split_id": split.get("split_id"),
                    "shard_id": shard_id,
                    "instance_id": instance,
                    "repo_raw": task.get("repo"),
                    "canonical_repo": repo,
                    "base_commit": commit,
                })
        split_expected_tasks = split.get("expected_task_count")
        if not isinstance(split_expected_tasks, int) or isinstance(split_expected_tasks, bool) or split_expected_tasks <= 0:
            reasons.append("positive_split_task_count_not_declared")
        if split_expected_tasks != split_actual_task_total or split_expected_tasks != split_declared_task_total:
            reasons.append("split_task_total_mismatch")
        dataset_actual_task_total += split_actual_task_total
        if isinstance(split_expected_tasks, int) and not isinstance(split_expected_tasks, bool):
            dataset_declared_task_total += split_expected_tasks
    if manifest.get("expected_shard_count") != shard_total:
        reasons.append("dataset_shard_inventory_incomplete")
    dataset_expected_tasks = manifest.get("expected_task_count")
    if not isinstance(dataset_expected_tasks, int) or isinstance(dataset_expected_tasks, bool) or dataset_expected_tasks <= 0:
        reasons.append("positive_dataset_task_count_not_declared")
    if dataset_expected_tasks != dataset_actual_task_total or dataset_expected_tasks != dataset_declared_task_total:
        reasons.append("dataset_task_total_mismatch")
    if not tasks:
        reasons.append("protected_task_universe_empty")
    return sorted(set(reasons)), tasks


def _recovery_key(row: dict[str, Any]) -> tuple[str, str] | None:
    identity = row.get("source_native_identity")
    identity = identity if isinstance(identity, dict) else {}
    repo = canonical_repo(row.get("canonical_repo"))
    instance = identity.get("instance_id")
    if repo is None or not isinstance(instance, str) or not instance:
        return None
    return repo, instance


def validate_universe(
    recovery_rows: list[dict[str, Any]],
    manifests: list[dict[str, Any]],
    required_dataset_ids: Iterable[str] | None = None,
) -> dict[str, Any]:
    invalid: list[dict[str, Any]] = []
    all_tasks: list[dict[str, Any]] = []
    universe_reasons: list[str] = []
    required_list = list(required_dataset_ids or [])
    required_valid = all(isinstance(item, str) and item.strip() == item and item for item in required_list)
    required_set = set(required_list) if required_valid else set()
    if not required_list:
        universe_reasons.append("protected_dataset_scope_missing")
    elif not required_valid:
        universe_reasons.append("invalid_required_dataset_id")
    if len(required_list) != len(required_set):
        universe_reasons.append("duplicate_required_dataset_id")
    if not manifests:
        universe_reasons.append("protected_universe_manifest_missing")
    for index, manifest in enumerate(manifests):
        reasons, tasks = validate_manifest(manifest)
        if reasons:
            invalid.append({
                "manifest_index": index,
                "dataset_id": manifest.get("dataset_id"),
                "manifest_sha256": stable_hash(manifest),
                "blocking_reasons": reasons,
                **ZERO_FLAGS,
            })
            universe_reasons.extend(reasons)
        else:
            all_tasks.extend(tasks)

    dataset_ids = [item.get("dataset_id") for item in manifests]
    if len(dataset_ids) != len(set(dataset_ids)):
        universe_reasons.append("duplicate_dataset_manifest")
    manifest_dataset_set = {item for item in dataset_ids if isinstance(item, str)}
    if required_set - manifest_dataset_set:
        universe_reasons.append("required_protected_dataset_missing")
    if manifest_dataset_set - required_set:
        universe_reasons.append("unexpected_protected_dataset_manifest")

    by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    by_instance: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for task in all_tasks:
        if task["canonical_repo"] is not None and isinstance(task["instance_id"], str):
            by_key[(task["canonical_repo"], task["instance_id"])].append(task)
            by_instance[task["instance_id"]].append(task)
    for records in by_key.values():
        if len(records) > 1:
            universe_reasons.append("duplicate_canonical_task_identity_or_alias")
        if len({record["base_commit"] for record in records}) > 1:
            universe_reasons.append("conflicting_task_base_commits")
    for records in by_instance.values():
        if len({record["canonical_repo"] for record in records}) > 1:
            universe_reasons.append("conflicting_task_repo_identities")

    universe_reasons = sorted(set(universe_reasons))
    valid = not universe_reasons
    adjudications: list[dict[str, Any]] = []
    for recovery in recovery_rows:
        key = _recovery_key(recovery)
        reasons: list[str] = []
        if not valid:
            status = "unadjudicated"
            reasons = ["protected_universe_missing_incomplete_or_ambiguous", *universe_reasons]
        elif key is None:
            status = "unadjudicated"
            reasons = ["stage12550_canonical_repo_instance_identity_missing"]
        elif key in by_key:
            status = "overlap"
            reasons = ["protected_task_overlap_detected"]
        else:
            status = "clear"
        adjudications.append({
            "record_type": "stage12552_protected_task_coverage_adjudication_v1",
            "candidate_id": recovery.get("candidate_id"),
            "canonical_repo": key[0] if key else None,
            "instance_id": key[1] if key else None,
            "coverage_status": status,
            "blocking_reasons": sorted(set(reasons)),
            "coverage_inferred_from_filename": False,
            **ZERO_FLAGS,
        })
    inventory = {
        "record_type": "stage12552_validated_protected_task_inventory_v1",
        "universe_valid": valid,
        "blocking_reasons": universe_reasons,
        "required_dataset_ids": sorted(required_set),
        "validated_manifest_count": len(manifests) - len(invalid) if valid else 0,
        "validated_task_count": len(all_tasks) if valid else 0,
        "canonical_task_inventory_sha256": stable_hash(sorted(
            (task["canonical_repo"], task["instance_id"], task["base_commit"])
            for task in all_tasks
        )) if valid else None,
        "filename_or_path_coverage_inference_used": False,
        **ZERO_FLAGS,
    }
    return {"adjudications": adjudications, "invalid_manifests": invalid, "inventory": inventory}


def build_summary(
    recovery_rows: list[dict[str, Any]],
    manifests: list[dict[str, Any]],
    required_dataset_ids: list[str],
    result: dict[str, Any],
) -> dict[str, Any]:
    statuses = Counter(row["coverage_status"] for row in result["adjudications"])
    reasons = Counter(
        reason for row in result["adjudications"] for reason in row["blocking_reasons"]
    )
    return {
        "stage": STAGE,
        "stage12550_recovery_rows_loaded": len(recovery_rows),
        "configured_manifest_count": len(manifests),
        "required_dataset_id_count": len(required_dataset_ids),
        "invalid_manifest_count": len(result["invalid_manifests"]),
        "universe_valid": result["inventory"]["universe_valid"],
        "validated_manifest_count": result["inventory"]["validated_manifest_count"],
        "validated_task_count": result["inventory"]["validated_task_count"],
        "coverage_overlap_count": statuses["overlap"],
        "coverage_clear_count": statuses["clear"],
        "coverage_unadjudicated_count": statuses["unadjudicated"],
        "reason_counts": dict(sorted(reasons.items())),
        "all_recovery_rows_adjudicated": statuses["unadjudicated"] == 0,
        "filename_or_path_coverage_inference_used": False,
        "protected_trajectory_metadata_trusted": False,
        **ZERO_FLAGS,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--manifest", type=Path, action="append", default=[])
    parser.add_argument("--required-dataset-id", action="append", default=[])
    parser.add_argument("--output-dir", type=Path, default=OUT)
    parser.add_argument("--summary", type=Path, default=SUMMARY)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    recovery_rows = read_jsonl(args.input)
    manifests = [read_json(path) for path in args.manifest]
    result = validate_universe(recovery_rows, manifests, args.required_dataset_id)
    write_jsonl(args.output_dir / ADJUDICATION_OUT.name, result["adjudications"])
    write_jsonl(args.output_dir / INVALID_OUT.name, result["invalid_manifests"])
    write_json(args.output_dir / INVENTORY_OUT.name, result["inventory"])
    summary = build_summary(recovery_rows, manifests, args.required_dataset_id, result)
    write_json(args.output_dir / OUT_SUMMARY.name, summary)
    write_json(args.summary, summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
