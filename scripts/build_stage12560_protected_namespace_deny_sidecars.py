#!/usr/bin/env python3
"""Emit hashed legacy protected namespaces and conservative collision metrics."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12560_protected_namespace_deny_sidecars"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
CANDIDATES = ROOT / "runs/local/artifacts/stage12555_swe_rebench_identity_adapter/exact_task_authority_bindings.jsonl"
SEALED = ROOT / "runs/local/artifacts/stage12105_sealed_transition_candidate_atlas/sealed_transition_candidate_rows.jsonl"
LOCKED = ROOT / "runs/local/artifacts/stage8672_locked_benchmark_pack_manifest/locked_benchmark_packs.jsonl"
ZERO = {"admission_allowed": False, "training_allowed": False, "replay_allowed": False,
        "root_credit": False, "repair_credit": False, "level3_credit": False,
        "strict_eval_eligible": False, "gpu_allowed": False}


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def normalized_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def build_sidecars(candidates: list[dict[str, Any]], sealed: list[dict[str, Any]], locked: list[dict[str, Any]]) -> dict[str, Any]:
    candidate_repos = sorted({str((row.get("task_identity") or {}).get("canonical_repo") or "").lower() for row in candidates} - {""})
    sealed_repo_labels = sorted({str(row.get("repo_id") or "").lower() for row in sealed} - {""})
    sealed_roots = sorted({str(row.get("stage12105_root_key") or row.get("root_lineage_key") or row.get("root_id") or "") for row in sealed} - {""})
    locked_ids = sorted({
        (str(row.get("source_id") or ""), str(row.get("task_pack_id") or ""), str(row.get("lineage_hash") or ""), str(row.get("artifact_hash") or ""))
        for row in locked
    })
    exact = sorted(set(candidate_repos) & set(sealed_repo_labels))
    normalized = sorted({
        (repo, label) for repo in candidate_repos for label in sealed_repo_labels
        if normalized_label(repo.rsplit("/", 1)[-1]) == normalized_label(label)
    })
    sidecars = {
        "sealed_namespace": {
            "source_qualified_root_count": len(sealed_roots),
            "source_qualified_root_hashes": [digest(["stage12105", root]) for root in sealed_roots],
            "repo_label_count": len(sealed_repo_labels),
            "repo_label_hashes": [digest(["stage12105_repo_label", label]) for label in sealed_repo_labels],
            "canonical_repo_mapping_complete": False,
            "immutable_revision_mapping_complete": False,
        },
        "locked_namespace": {
            "source_qualified_pack_count": len(locked_ids),
            "source_qualified_pack_hashes": [digest(["stage8672", *item]) for item in locked_ids],
            "canonical_repo_mapping_complete": False,
            "immutable_revision_mapping_complete": False,
        },
    }
    summary = {
        "stage": STAGE,
        "record_type": "stage12560_protected_namespace_deny_sidecars_summary_v1",
        "candidate_repo_count": len(candidate_repos),
        "sealed_root_count": len(sealed_roots),
        "sealed_repo_label_count": len(sealed_repo_labels),
        "locked_pack_count": len(locked_ids),
        "exact_repo_label_overlap_count": len(exact),
        "normalized_basename_collision_count": len(normalized),
        "exact_overlap_sha256": digest(exact),
        "normalized_collision_sha256": digest(normalized),
        "raw_prompt_target_evidence_emitted": False,
        "path_or_filename_repo_inference_used": False,
        "protected_clearance": False,
        "blocking_reasons": ["stage12105_canonical_repo_mapping_incomplete", "stage12105_immutable_revision_mapping_incomplete",
                             "stage8672_promotion_namespace_has_no_canonical_task_lineage"],
        **ZERO,
    }
    return {"sidecars": sidecars, "summary": summary}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    result = build_sidecars(read_jsonl(CANDIDATES), read_jsonl(SEALED), read_jsonl(LOCKED))
    result["summary"]["source_sha256"] = {"candidates": file_sha256(CANDIDATES), "sealed": file_sha256(SEALED), "locked": file_sha256(LOCKED)}
    write_json(OUT / "hashed_namespace_sidecars.json", result["sidecars"])
    write_json(OUT / "summary.json", result["summary"])
    write_json(SUMMARY, result["summary"])
    print(json.dumps(result["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
