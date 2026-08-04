#!/usr/bin/env python3
"""Join Open-SWE trajectories to SWE-rebench task identity without gold fields."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12555_swe_rebench_identity_adapter"
INPUT = ROOT / "runs/local/artifacts/stage12554_authority_inventory_and_overlap_gate/resolved_authority_fields.jsonl"
PARQUET = Path("/arxiv/datasets/nebius--SWE-rebench-V2/data/train-00000-of-00001.parquet")
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
DATASET = "nebius/SWE-rebench-V2"
REVISION = "475dd5e8703bb5fb22dd3c60b5d038b019eba1e0"
PARQUET_SHA256 = "0e0bf9355f892ad74ae98d4e1c404f39fd6654a8e351ee3e6ab162e4a64cd3ad"
ALLOWED_COLUMNS = ("instance_id", "repo", "base_commit", "language", "created_at")
FORBIDDEN_COLUMNS = (
    "patch", "test_patch", "problem_statement", "pr_description",
    "FAIL_TO_PASS", "PASS_TO_PASS",
)
SHA40 = re.compile(r"^[0-9a-f]{40}$", re.I)
ZERO_FLAGS = {
    "admission_allowed": False, "training_allowed": False, "gpu_allowed": False,
    "replay_allowed": False, "root_credit": False, "repair_credit": False,
    "strict_eval_eligible": False,
}


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_repo(value: Any) -> str | None:
    text = str(value or "").strip().strip("/")
    if text.endswith(".git"):
        text = text[:-4]
    parts = text.split("/")
    if len(parts) != 2 or not all(re.fullmatch(r"[A-Za-z0-9_.-]+", part) for part in parts):
        return None
    return f"{parts[0].lower()}/{parts[1].lower()}"


def field_value(row: dict[str, Any], name: str) -> Any:
    value = (row.get("resolved_fields") or {}).get(name)
    return value.get("value") if isinstance(value, dict) else None


def split_for_repo(repo: str) -> str:
    bucket = int(hashlib.sha256(("repo_split_v1:" + repo).encode()).hexdigest()[:8], 16) % 100
    return "train" if bucket < 80 else "validation" if bucket < 90 else "sealed_eval"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def build(bindings: list[dict[str, Any]], parquet_path: Path, expected_sha: str, revision: str) -> dict[str, Any]:
    import pyarrow.parquet as pq  # type: ignore

    source_errors: list[str] = []
    actual_sha = file_sha256(parquet_path) if parquet_path.is_file() else None
    if actual_sha != expected_sha:
        source_errors.append("authoritative_task_snapshot_digest_mismatch_or_missing")
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        source_errors.append("authoritative_task_revision_invalid")
    authority_rows: list[dict[str, Any]] = []
    if not source_errors:
        parquet = pq.ParquetFile(parquet_path)
        missing = sorted(set(ALLOWED_COLUMNS) - set(parquet.schema_arrow.names))
        if missing:
            source_errors.append("authoritative_identity_schema_incomplete")
        else:
            authority_rows = parquet.read(columns=list(ALLOWED_COLUMNS)).to_pylist()

    snapshot = stable_hash({
        "dataset": DATASET, "revision": revision, "split": "train",
        "parquet_sha256": actual_sha, "allowed_columns": ALLOWED_COLUMNS,
        "row_count": len(authority_rows),
    }) if authority_rows else None
    by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    repo_splits: dict[str, str] = {}
    for row in authority_rows:
        repo = canonical_repo(row.get("repo"))
        instance = str(row.get("instance_id") or "")
        if repo and instance:
            by_key[(repo, instance)].append(row)
            repo_splits[repo] = split_for_repo(repo)

    matched: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for binding in bindings:
        repo = canonical_repo(field_value(binding, "canonical_repo"))
        instance = str(field_value(binding, "trajectory_instance_id") or "")
        key = (repo or "", instance)
        candidates = by_key.get(key, []) if not source_errors else []
        reasons = list(source_errors)
        if not repo or not instance:
            reasons.append("trajectory_exact_repo_instance_key_missing")
        elif not candidates:
            reasons.append("authoritative_task_exact_key_not_found")
        elif len({(str(row.get("base_commit")), str(row.get("language"))) for row in candidates}) != 1:
            reasons.append("authoritative_task_exact_key_conflict")
        row = candidates[0] if candidates and not reasons else None
        if row is not None and not SHA40.fullmatch(str(row.get("base_commit") or "")):
            reasons.append("authoritative_base_commit_invalid")
            row = None
        if row is None:
            blocked.append({
                "record_type": "stage12555_blocked_task_authority_binding_v1",
                "candidate_id": binding.get("candidate_id"),
                "blocking_reasons": sorted(set(reasons)), **ZERO_FLAGS,
            })
            continue
        split = repo_splits[repo]
        identity = {
            "dataset": DATASET, "revision": revision, "source_split": "train",
            "instance_id": instance, "canonical_repo": repo,
            "base_commit": str(row["base_commit"]).lower(),
            "language": str(row.get("language") or "unknown").lower(),
            "created_at": row.get("created_at"),
        }
        matched.append({
            "record_type": "stage12555_exact_task_authority_binding_v1",
            "candidate_id": binding.get("candidate_id"),
            "task_key": [DATASET, revision, "train", instance],
            "task_snapshot_sha256": snapshot,
            "task_identity": identity,
            "task_identity_sha256": stable_hash(identity),
            "policy_split": split,
            "policy_split_key": ["repo_split_v1", repo],
            "protected_from_training": split != "train",
            "blocked_fields": ["authoritative_base_tree", "expected_post_tree", "verifier_replay", "state_after", "stop_continue"],
            "gold_or_reference_fields_read": False,
            "task_patch_equality_join_used": False,
            "similarity_join_used": False,
            **ZERO_FLAGS,
        })

    split_counts = Counter(row["policy_split"] for row in matched)
    language_counts = Counter(row["task_identity"]["language"] for row in matched)
    matched_repos = {row["task_identity"]["canonical_repo"] for row in matched}
    split_repo_sets = {
        split: {row["task_identity"]["canonical_repo"] for row in matched if row["policy_split"] == split}
        for split in ("train", "validation", "sealed_eval")
    }
    repo_overlap = bool(
        split_repo_sets["train"] & split_repo_sets["validation"]
        or split_repo_sets["train"] & split_repo_sets["sealed_eval"]
        or split_repo_sets["validation"] & split_repo_sets["sealed_eval"]
    )
    summary = {
        "stage": STAGE,
        "record_type": "stage12555_swe_rebench_identity_adapter_summary_v1",
        "binding_count": len(bindings), "authority_task_count": len(authority_rows),
        "exact_match_count": len(matched), "blocked_count": len(blocked),
        "unique_matched_repo_count": len(matched_repos),
        "split_counts": dict(sorted(split_counts.items())),
        "language_counts": dict(sorted(language_counts.items())),
        "repo_split_overlap": repo_overlap,
        "task_dataset": DATASET, "task_revision": revision,
        "task_parquet_sha256": actual_sha, "task_snapshot_sha256": snapshot,
        "adapter_read_columns": list(ALLOWED_COLUMNS),
        "forbidden_columns_read": [], "gold_or_reference_fields_read": False,
        "task_patch_equality_join_used": False, "similarity_join_used": False,
        "split_policy": "sha256(repo_split_v1 + canonical_repo) modulo 100: 80/10/10",
        "split_policy_sha256": stable_hash({"name": "repo_split_v1", "thresholds": [80, 90, 100]}),
        "default_disposition": "blocked_pending_checkout_replay_and_state_proof",
        **ZERO_FLAGS,
    }
    return {"matched": matched, "blocked": blocked, "summary": summary}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--parquet", type=Path, default=PARQUET)
    parser.add_argument("--expected-sha256", default=PARQUET_SHA256)
    parser.add_argument("--revision", default=REVISION)
    parser.add_argument("--output-dir", type=Path, default=OUT)
    parser.add_argument("--summary", type=Path, default=SUMMARY)
    args = parser.parse_args()
    result = build(read_jsonl(args.input), args.parquet, args.expected_sha256, args.revision)
    write_jsonl(args.output_dir / "exact_task_authority_bindings.jsonl", result["matched"])
    write_jsonl(args.output_dir / "blocked_task_authority_bindings.jsonl", result["blocked"])
    write_json(args.output_dir / "summary.json", result["summary"])
    write_json(args.summary, result["summary"])
    print(json.dumps(result["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
