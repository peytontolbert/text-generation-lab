#!/usr/bin/env python3
"""Fail-closed authoritative protected-lineage enforcement preflight."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12564_authoritative_protected_lineage_preflight"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
SEALED = ROOT / "runs/local/artifacts/stage12105_sealed_transition_candidate_atlas/sealed_transition_candidate_rows.jsonl"
LOCKED = ROOT / "runs/local/artifacts/stage8672_locked_benchmark_pack_manifest/locked_benchmark_packs.jsonl"
STAGE12560 = ROOT / "runs/summaries/stage12560_protected_namespace_deny_sidecars.json"
COMMITMENT = ROOT / "runs/local/artifacts/stage12562_pre_outcome_candidate_commitment/candidate_commitment.json"
SCOPE = ROOT / "runs/summaries/stage12561_active_protected_scope_gate.json"
READY = ROOT / "runs/local/artifacts/stage12556_local_checkout_readiness_census/checkout_object_ready.jsonl"
BINDINGS = ROOT / "runs/local/artifacts/stage12555_swe_rebench_identity_adapter/exact_task_authority_bindings.jsonl"
VERIFIED = ROOT / "runs/local/artifacts/stage12554_authority_inventory_and_overlap_gate/protected_swe_bench_verified_manifest.json"

# These are the Stage12560-recorded source digests. They deliberately do not
# follow a later file or a later self-reported hash.
LEGACY_SOURCE_ANCHORS = {
    "sealed": "dbaf3800b987bb8607c8cd2ddb0ddcbf2011e6be9b2f4c0a41847013b86dddd2",
    "locked": "a6cce0dabed78c240037a0ef7d06fb739e7dd9b835ca57686d49d66bff84a570",
}
VERIFIED_MANIFEST_SHA256 = "50e52154348d471c0d6407e466b3bffce4a197fbe81cce6db122ef22c4bcb5c5"
LOCKED_SEMANTIC_SHA256 = "80b2e89981e96056fa16cfcc632e80b95b916d0f095786bc988e3e5c4ea4336c"
FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
ZERO = {
    "admission_allowed": False,
    "training_allowed": False,
    "replay_allowed": False,
    "root_credit": False,
    "repair_credit": False,
    "level3_credit": False,
    "strict_eval_eligible": False,
    "gpu_allowed": False,
}
COMMITMENT_SOURCES = {
    "ready": READY,
    "authority": ROOT / "runs/local/artifacts/stage12554_authority_inventory_and_overlap_gate/resolved_authority_fields.jsonl",
    "task_bindings": BINDINGS,
    "checkout_summary": ROOT / "runs/summaries/stage12556_local_checkout_readiness_census.json",
    "preflight_summary": ROOT / "runs/summaries/stage12557_private_train_replay_pilot.json",
    "scope_gate": SCOPE,
    "frontier_decision": ROOT / "runs/summaries/stage11509_preservation_strengthened_frontier_promotion_decision.json",
    "runtime_bundle": ROOT / "runs/local/artifacts/stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json",
    "runtime_weights": ROOT / "runs/local/artifacts/stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/model_state.pt",
}
LOCKED_KEYS = {
    "artifact_hash", "blocked_training_reason", "exists", "hidden_final", "lineage_hash",
    "parsed_scores", "path", "promotion_only", "slice_tags", "source_id", "split_role",
    "task_pack_id", "thresholds", "train_eligible",
}


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def manifest_tasks(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if {"instance_id", "repo", "base_commit"}.issubset(value):
            found.append(value)
        for child in value.values():
            found.extend(manifest_tasks(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(manifest_tasks(child))
    return found


def canonical_repo(value: Any) -> str | None:
    text = str(value or "").strip().replace("\\", "/").removesuffix(".git").strip("/").lower()
    return text if len(text.split("/")) == 2 and all(text.split("/")) else None


def identity(repo: Any, commit: Any) -> tuple[str, str] | None:
    canonical = canonical_repo(repo)
    revision = str(commit or "").lower()
    if canonical and FULL_SHA_RE.fullmatch(revision):
        return canonical, revision
    return None


def sealed_root(row: dict[str, Any]) -> str:
    return str(row.get("stage12105_root_key") or row.get("root_lineage_key") or row.get("root_id") or "")


def locked_semantics_valid(rows: list[dict[str, Any]]) -> bool:
    if len(rows) != 5 or len({row.get("source_id") for row in rows}) != 5:
        return False
    for row in rows:
        source_id = row.get("source_id")
        if set(row) != LOCKED_KEYS or not isinstance(source_id, str):
            return False
        if row.get("task_pack_id") != f"locked_{source_id}":
            return False
        if not all(DIGEST_RE.fullmatch(str(row.get(key) or "")) for key in ("lineage_hash", "artifact_hash")):
            return False
        exact = {
            "exists": True,
            "hidden_final": False,
            "parsed_scores": [],
            "promotion_only": True,
            "split_role": "locked_regression",
            "train_eligible": False,
            "blocked_training_reason": "locked_eval_source_never_mined_into_training",
        }
        if any(row.get(key) != value for key, value in exact.items()):
            return False
        if not str(row.get("path") or "").startswith("/arxiv/"):
            return False
        if not isinstance(row.get("slice_tags"), list) or not row["slice_tags"]:
            return False
        if not isinstance(row.get("thresholds"), dict) or not row["thresholds"]:
            return False
    ordered = sorted(rows, key=lambda row: row["source_id"])
    return stable_hash(ordered) == LOCKED_SEMANTIC_SHA256


def audit(
    sealed: list[dict[str, Any]],
    locked: list[dict[str, Any]],
    commitment: dict[str, Any],
    ready: list[dict[str, Any]],
    bindings: list[dict[str, Any]],
    verified_tasks: list[dict[str, Any]],
    scope: dict[str, Any],
    stage12560: dict[str, Any],
    *,
    legacy_source_hashes: dict[str, str | None],
    current_commitment_source_hashes: dict[str, str | None],
    verified_manifest_sha256: str | None,
) -> dict[str, Any]:
    blockers: list[str] = []

    recorded_legacy = stage12560.get("source_sha256") if isinstance(stage12560.get("source_sha256"), dict) else {}
    legacy_anchors_valid = all(
        recorded_legacy.get(name) == expected and legacy_source_hashes.get(name) == expected
        for name, expected in LEGACY_SOURCE_ANCHORS.items()
    )
    if not legacy_anchors_valid:
        blockers.append("stage12560_legacy_source_anchor_mismatch")

    locked_valid = locked_semantics_valid(locked)
    if not locked_valid:
        blockers.append("locked_pack_exact_semantics_invalid")

    roots = sorted({root for row in sealed if (root := sealed_root(row))})
    # Legacy root strings are labels, not authority records. A SHA-looking label
    # is never upgraded to certified provenance without an authoritative adapter.
    unresolved_roots = [
        {
            "protected_root_key_sha256": stable_hash(["stage12105", root]),
            "resolution_status": "unresolved",
            "reason": "authoritative_repo_and_commit_provenance_missing",
        }
        for root in roots
    ]
    if len(roots) != 25:
        blockers.append("protected_root_set_missing_or_duplicate")
    if unresolved_roots:
        blockers.append("protected_legacy_lineage_unresolved")

    payload = commitment.get("commitment_payload")
    payload = payload if isinstance(payload, dict) else {}
    committed_sources = payload.get("source_sha256") if isinstance(payload.get("source_sha256"), dict) else {}
    source_keys_exact = set(committed_sources) == set(COMMITMENT_SOURCES)
    commitment_sources_current = source_keys_exact and all(
        current_commitment_source_hashes.get(name) is not None
        and committed_sources.get(name) == current_commitment_source_hashes.get(name)
        for name in COMMITMENT_SOURCES
    )
    commitment_envelope_valid = (
        commitment.get("record_type") == "stage12562_pre_outcome_candidate_commitment_v1"
        and commitment.get("pre_outcome_commitment_valid") is True
        and commitment.get("commitment_sha256") == stable_hash(payload)
        and payload.get("schema") == "pre_outcome_candidate_commitment_v1"
    )
    if not commitment_envelope_valid:
        blockers.append("stage12562_commitment_envelope_invalid")
    if not commitment_sources_current:
        blockers.append("stage12562_commitment_source_hash_mismatch")

    candidate_ids = payload.get("candidate_ids") if isinstance(payload.get("candidate_ids"), list) else []
    task_keys = payload.get("task_keys") if isinstance(payload.get("task_keys"), list) else []
    ready_pairs = {(str(row.get("candidate_id") or ""), stable_hash(row.get("task_key"))) for row in ready}
    committed_pairs = {
        (str(candidate_id), stable_hash(task_key))
        for candidate_id, task_key in zip(candidate_ids, task_keys, strict=False)
    }
    selection_exact = (
        bool(candidate_ids)
        and len(candidate_ids) == len(set(candidate_ids))
        and len(candidate_ids) == len(task_keys)
        and committed_pairs == ready_pairs
    )
    if not selection_exact:
        blockers.append("committed_candidate_selection_not_authoritative")

    binding_ids = [row.get("candidate_id") for row in bindings]
    by_candidate = {row.get("candidate_id"): row for row in bindings}
    candidate_identities: set[tuple[str, str]] = set()
    provenance_complete = len(binding_ids) == len(set(binding_ids))
    for candidate_id in candidate_ids:
        row = by_candidate.get(candidate_id)
        item = (row or {}).get("task_identity") or {}
        resolved = identity(item.get("canonical_repo"), item.get("base_commit"))
        if not row or row.get("policy_split") != "train" or resolved is None:
            provenance_complete = False
        else:
            candidate_identities.add(resolved)
    provenance_complete = provenance_complete and len(candidate_identities) == len(candidate_ids)
    if not provenance_complete:
        blockers.append("candidate_repo_commit_provenance_incomplete")

    protected_identities: set[tuple[str, str]] = set()
    malformed_protected = 0
    for row in bindings:
        if row.get("policy_split") not in {"validation", "sealed_eval"}:
            continue
        item = row.get("task_identity") or {}
        resolved = identity(item.get("canonical_repo"), item.get("base_commit"))
        if resolved is None:
            malformed_protected += 1
        else:
            protected_identities.add(resolved)
    for row in verified_tasks:
        resolved = identity(row.get("repo"), row.get("base_commit"))
        if resolved is None:
            malformed_protected += 1
        else:
            protected_identities.add(resolved)
    if malformed_protected or not protected_identities:
        blockers.append("certifiable_active_protected_identity_set_incomplete")

    verified_manifest_anchored = verified_manifest_sha256 == VERIFIED_MANIFEST_SHA256
    if not verified_manifest_anchored:
        blockers.append("active_protected_manifest_anchor_mismatch")

    overlap = sorted(candidate_identities & protected_identities)
    if overlap:
        blockers.append("committed_candidate_repo_commit_overlap")
    repo_overlap = sorted({repo for repo, _ in candidate_identities} & {repo for repo, _ in protected_identities})
    if repo_overlap:
        blockers.append("committed_candidate_repo_family_overlap")

    stage12561_disjoint = (
        scope.get("diagnostic_active_scope_disjoint") is True
        and scope.get("exact_task_overlap_count") == 0
        and scope.get("canonical_repo_overlap_count") == 0
        and scope.get("malformed_protected_identity_count") == 0
        and scope.get("invalid_ready_count") == 0
        and scope.get("duplicate_binding_id_count") == 0
    )
    if not stage12561_disjoint:
        blockers.append("stage12561_active_protected_disjointness_not_proven")

    # Hook installation must be proved by code-level integration tests in a
    # later stage. It is never accepted as a caller-provided assertion here.
    operational_ingestion_hooks_verified = False
    blockers.append("recursive_ingestion_enforcement_hooks_unverified")

    requirements_demonstrated = not blockers
    # The repository has no tested recursive ingestion hooks. Do not convert a
    # data-only audit into execution authority.
    authorization_allowed = False
    return {
        "legacy_source_anchors_valid": legacy_anchors_valid,
        "locked_pack_exact_semantics_valid": locked_valid,
        "protected_root_count": len(roots),
        "certified_legacy_root_count": 0,
        "unresolved_protected_root_count": len(unresolved_roots),
        "unresolved_protected_roots": unresolved_roots,
        "stage12562_commitment_envelope_valid": commitment_envelope_valid,
        "stage12562_commitment_sources_current": commitment_sources_current,
        "committed_candidate_selection_exact": selection_exact,
        "candidate_count": len(candidate_ids),
        "candidate_repo_commit_provenance_complete": provenance_complete,
        "certifiable_active_protected_identity_count": len(protected_identities),
        "malformed_active_protected_identity_count": malformed_protected,
        "candidate_protected_repo_commit_overlap_count": len(overlap),
        "candidate_protected_repo_commit_overlap_sha256": stable_hash(overlap),
        "candidate_protected_repo_family_overlap_count": len(repo_overlap),
        "candidate_protected_repo_family_overlap_sha256": stable_hash(repo_overlap),
        "active_protected_manifest_anchored": verified_manifest_anchored,
        "stage12561_active_protected_disjointness_proven": stage12561_disjoint,
        "operational_ingestion_hooks_verified": operational_ingestion_hooks_verified,
        "all_authorization_requirements_demonstrated": requirements_demonstrated,
        "protected_lineage_enforcement_authoritative": authorization_allowed,
        "blocking_reasons": sorted(set(blockers)),
        "raw_protected_payload_emitted": False,
        **ZERO,
    }


def build() -> dict[str, Any]:
    legacy_hashes = {"sealed": file_sha256(SEALED), "locked": file_sha256(LOCKED)}
    source_hashes = {name: file_sha256(path) for name, path in COMMITMENT_SOURCES.items()}
    result = audit(
        read_jsonl(SEALED), read_jsonl(LOCKED), read_json(COMMITMENT), read_jsonl(READY),
        read_jsonl(BINDINGS), manifest_tasks(json.loads(VERIFIED.read_text(encoding="utf-8"))),
        read_json(SCOPE), read_json(STAGE12560), legacy_source_hashes=legacy_hashes,
        current_commitment_source_hashes=source_hashes,
        verified_manifest_sha256=file_sha256(VERIFIED),
    )
    return {
        "stage": STAGE,
        "record_type": "stage12564_authoritative_protected_lineage_preflight_summary_v1",
        **result,
        "authoritative_source_sha256": {
            "legacy": legacy_hashes,
            "commitment_sources": source_hashes,
            "stage12560_summary": file_sha256(STAGE12560),
            "stage12562_commitment": file_sha256(COMMITMENT),
        },
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    result = build()
    write_json(OUT / "authoritative_protected_lineage_preflight.json", result)
    write_json(OUT / "summary.json", result)
    write_json(SUMMARY, result)
    print(json.dumps({key: result[key] for key in (
        "legacy_source_anchors_valid", "locked_pack_exact_semantics_valid",
        "stage12562_commitment_sources_current", "candidate_protected_repo_commit_overlap_count",
        "unresolved_protected_root_count", "protected_lineage_enforcement_authoritative", "blocking_reasons",
    )}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
