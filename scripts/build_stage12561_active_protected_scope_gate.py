#!/usr/bin/env python3
"""Retire uncanonical legacy evals and validate the active protected scope."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12561_active_protected_scope_gate"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
READY = ROOT / "runs/local/artifacts/stage12556_local_checkout_readiness_census/checkout_object_ready.jsonl"
BINDINGS = ROOT / "runs/local/artifacts/stage12555_swe_rebench_identity_adapter/exact_task_authority_bindings.jsonl"
VERIFIED = ROOT / "runs/local/artifacts/stage12554_authority_inventory_and_overlap_gate/protected_swe_bench_verified_manifest.json"
LEGACY = {
    "stage12105": ROOT / "runs/local/artifacts/stage12105_sealed_transition_candidate_atlas/sealed_transition_candidate_rows.jsonl",
    "stage8672": ROOT / "runs/local/artifacts/stage8672_locked_benchmark_pack_manifest/locked_benchmark_packs.jsonl",
}
ZERO = {"admission_allowed": False, "training_allowed": False, "replay_allowed": False,
        "root_credit": False, "repair_credit": False, "level3_credit": False,
        "strict_eval_eligible": False, "gpu_allowed": False}
FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_repo(value: Any) -> str | None:
    text = str(value or "").strip().replace("\\", "/").removesuffix(".git").strip("/").lower()
    return text if len(text.split("/")) == 2 else None


def manifest_tasks(value: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if {"instance_id", "repo", "base_commit"}.issubset(value):
            out.append(value)
        for child in value.values():
            out.extend(manifest_tasks(child))
    elif isinstance(value, list):
        for child in value:
            out.extend(manifest_tasks(child))
    return out


def evaluate(ready: list[dict[str, Any]], bindings: list[dict[str, Any]], verified_tasks: list[dict[str, Any]],
             *, legacy_deny_enforced: bool = False, selection_committed_pre_outcome: bool = False) -> dict[str, Any]:
    binding_ids = [row.get("candidate_id") for row in bindings]
    duplicate_binding_ids = len(binding_ids) - len(set(binding_ids))
    by_candidate = {row.get("candidate_id"): row for row in bindings}
    train: list[tuple[str, str, str]] = []
    invalid: list[str] = []
    for row in ready:
        binding = by_candidate.get(row.get("candidate_id"))
        identity = (binding or {}).get("task_identity") or {}
        repo = canonical_repo(identity.get("canonical_repo"))
        instance = str(identity.get("instance_id") or "")
        commit = str(identity.get("base_commit") or "").lower()
        if not binding or binding.get("policy_split") != "train" or not repo or not instance or not FULL_SHA_RE.fullmatch(commit):
            invalid.append(str(row.get("candidate_id")))
        else:
            train.append((repo, instance, commit))

    rebench_eval = []
    for row in bindings:
        if row.get("policy_split") not in {"validation", "sealed_eval"}:
            continue
        item = row.get("task_identity") or {}
        repo = canonical_repo(item.get("canonical_repo"))
        if repo:
            rebench_eval.append((repo, str(item.get("instance_id") or ""), str(item.get("base_commit") or "").lower()))
    verified = []
    malformed_protected = 0
    for row in verified_tasks:
        repo = canonical_repo(row.get("repo"))
        commit = str(row.get("base_commit") or "").lower()
        if repo and row.get("instance_id") and FULL_SHA_RE.fullmatch(commit):
            verified.append((repo, str(row.get("instance_id") or ""), commit))
        else:
            malformed_protected += 1

    train_set, protected = set(train), set(rebench_eval) | set(verified)
    train_repos = {item[0] for item in train_set}
    protected_repos = {item[0] for item in protected}
    exact_overlap = sorted(train_set & protected)
    repo_overlap = sorted(train_repos & protected_repos)
    diagnostic_disjoint = bool(train_set) and not invalid and not exact_overlap and not repo_overlap and not malformed_protected and not duplicate_binding_ids
    clearance = diagnostic_disjoint and legacy_deny_enforced and selection_committed_pre_outcome
    return {
        "train_identity_count": len(train_set), "rebench_protected_identity_count": len(set(rebench_eval)),
        "swe_bench_verified_identity_count": len(set(verified)), "invalid_ready_count": len(invalid),
        "malformed_protected_identity_count": malformed_protected, "duplicate_binding_id_count": duplicate_binding_ids,
        "exact_task_overlap_count": len(exact_overlap), "canonical_repo_overlap_count": len(repo_overlap),
        "exact_overlap_sha256": hashlib.sha256(json.dumps(exact_overlap, sort_keys=True).encode()).hexdigest(),
        "repo_overlap_sha256": hashlib.sha256(json.dumps(repo_overlap, sort_keys=True).encode()).hexdigest(),
        "diagnostic_active_scope_disjoint": diagnostic_disjoint,
        "legacy_deny_enforced": legacy_deny_enforced,
        "selection_committed_pre_outcome": selection_committed_pre_outcome,
        "active_scope_clearance": clearance,
    }


def build() -> dict[str, Any]:
    verified = json.loads(VERIFIED.read_text(encoding="utf-8"))
    result = evaluate(read_jsonl(READY), read_jsonl(BINDINGS), manifest_tasks(verified))
    legacy = {name: {"source_sha256": file_sha256(path), "claim_eligible": False,
                     "training_eligible": False, "disposition": "frozen_historical_deny_namespace"}
              for name, path in LEGACY.items()}
    summary = {
        "stage": STAGE, "record_type": "stage12561_active_protected_scope_gate_summary_v1",
        **result,
        "active_protected_universes": ["nebius/SWE-rebench-V2 validation+sealed_eval", "princeton-nlp/SWE-bench_Verified test"],
        "legacy_namespace_count": len(legacy),
        "legacy_metrics_claim_eligible": False,
        "legacy_payloads_read": False,
        "retirement_reason": "legacy namespaces lack certified canonical repository and immutable revision lineage",
        "candidate_ready_manifest_sha256": file_sha256(READY),
        "candidate_binding_manifest_sha256": file_sha256(BINDINGS),
        "selection_commitment_status": "missing_pre_outcome_commitment",
        "sandbox_execution_still_required": True,
        "sandbox_progression_allowed": False,
        "decision": "rejected_unresolved_legacy_deny_and_selection_commitment",
        **ZERO,
    }
    return {"legacy": legacy, "summary": summary}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    result = build()
    write_json(OUT / "retired_legacy_namespaces.json", result["legacy"])
    write_json(OUT / "summary.json", result["summary"])
    write_json(SUMMARY, result["summary"])
    print(json.dumps(result["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
