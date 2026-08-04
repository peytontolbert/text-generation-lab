#!/usr/bin/env python3
"""Materialize legacy deny keys and audit enforcement against committed candidates."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12563_operational_legacy_deny_gate"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
SEALED = ROOT / "runs/local/artifacts/stage12105_sealed_transition_candidate_atlas/sealed_transition_candidate_rows.jsonl"
LOCKED = ROOT / "runs/local/artifacts/stage8672_locked_benchmark_pack_manifest/locked_benchmark_packs.jsonl"
COMMITMENT = ROOT / "runs/local/artifacts/stage12562_pre_outcome_candidate_commitment/candidate_commitment.json"
BINDINGS = ROOT / "runs/local/artifacts/stage12555_swe_rebench_identity_adapter/exact_task_authority_bindings.jsonl"
FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
ZERO = {"admission_allowed": False, "training_allowed": False, "replay_allowed": False,
        "root_credit": False, "repair_credit": False, "level3_credit": False,
        "strict_eval_eligible": False, "gpu_allowed": False}


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("expected object")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sealed_root(row: dict[str, Any]) -> str:
    return str(row.get("stage12105_root_key") or row.get("root_lineage_key") or row.get("root_id") or "")


def certified_git_identity(root: str) -> tuple[str, str] | None:
    parts = root.split("::")
    if len(parts) >= 2 and parts[0] in {"modelcontextprotocol_typescript_sdk", "openclaw_clawhub", "sourcebot"} and FULL_SHA_RE.fullmatch(parts[1]):
        return parts[0], parts[1]
    return None


def audit(sealed: list[dict[str, Any]], locked: list[dict[str, Any]], commitment: dict[str, Any],
          bindings: list[dict[str, Any]]) -> dict[str, Any]:
    roots = sorted({sealed_root(row) for row in sealed} - {""})
    root_keys = [stable_hash(["legacy_deny_v1", "stage12105", root]) for root in roots]
    git_identities = sorted({identity for root in roots if (identity := certified_git_identity(root)) is not None})
    certified_roots = sum(certified_git_identity(root) is not None for root in roots)
    pack_identities = sorted({
        (str(row.get("source_id") or ""), str(row.get("lineage_hash") or ""), str(row.get("artifact_hash") or ""))
        for row in locked
    })
    locked_valid = len(pack_identities) == len(locked) == 5 and all(row.get("train_eligible") is False for row in locked)

    payload = commitment.get("commitment_payload") or {}
    commitment_valid = commitment.get("pre_outcome_commitment_valid") is True and commitment.get("commitment_sha256") == stable_hash(payload)
    candidate_ids = payload.get("candidate_ids") if isinstance(payload.get("candidate_ids"), list) else []
    by_candidate = {row.get("candidate_id"): row for row in bindings}
    candidate_provenance_complete = all(
        candidate in by_candidate
        and by_candidate[candidate].get("policy_split") == "train"
        and (by_candidate[candidate].get("task_identity") or {}).get("canonical_repo")
        and FULL_SHA_RE.fullmatch(str((by_candidate[candidate].get("task_identity") or {}).get("base_commit") or ""))
        for candidate in candidate_ids
    ) and len(candidate_ids) == len(set(candidate_ids)) == 8

    candidate_commits = {
        str((by_candidate[candidate].get("task_identity") or {}).get("base_commit") or "")
        for candidate in candidate_ids if candidate in by_candidate
    }
    protected_commits = {commit for _, commit in git_identities}
    denied_candidate_count = len(candidate_commits & protected_commits)
    unresolved_roots = len(roots) - certified_roots
    protected_key_set_complete = len(roots) == 25 and len(root_keys) == 25
    # This stage is a diagnostic only. Syntactically recovered identities and
    # sidecar hashes do not prove recursive enforcement at every ingestion
    # boundary, so no input combination may authorize replay here.
    operational_ingestion_hooks_verified = False
    legacy_deny_enforced = False
    return {
        "normalization_schema": "legacy_deny_v1",
        "protected_root_count": len(roots),
        "protected_root_key_count": len(root_keys),
        "protected_root_key_set_sha256": stable_hash(root_keys),
        "certified_git_root_count": certified_roots,
        "certified_git_identity_count": len(git_identities),
        "certified_git_identity_set_sha256": stable_hash(git_identities),
        "unresolved_protected_root_count": unresolved_roots,
        "locked_pack_count": len(locked),
        "locked_pack_identity_count": len(pack_identities),
        "locked_pack_set_sha256": stable_hash(pack_identities),
        "locked_packs_train_ineligible": locked_valid,
        "candidate_count": len(candidate_ids),
        "candidate_commitment_valid": commitment_valid,
        "candidate_provenance_complete": candidate_provenance_complete,
        "denied_candidate_count": denied_candidate_count,
        "unproven_candidate_count": len(candidate_ids) if unresolved_roots else 0,
        "operational_ingestion_hooks_verified": operational_ingestion_hooks_verified,
        "legacy_deny_enforced": legacy_deny_enforced,
        "sandbox_progression_allowed": legacy_deny_enforced,
        "blocking_reasons": ([] if legacy_deny_enforced else [
            reason for condition, reason in (
                (protected_key_set_complete, "protected_root_key_set_incomplete"),
                (locked_valid, "locked_pack_boundary_invalid"),
                (commitment_valid, "candidate_commitment_invalid"),
                (candidate_provenance_complete, "candidate_provenance_incomplete"),
                (unresolved_roots == 0, "protected_git_or_local_lineage_unresolved"),
                (denied_candidate_count == 0, "committed_candidate_matches_protected_commit"),
                (operational_ingestion_hooks_verified, "operational_ingestion_hooks_unverified"),
            ) if not condition
        ]),
    }


def build() -> dict[str, Any]:
    result = audit(read_jsonl(SEALED), read_jsonl(LOCKED), read_json(COMMITMENT), read_jsonl(BINDINGS))
    return {
        "stage": STAGE, "record_type": "stage12563_operational_legacy_deny_gate_summary_v1",
        **result,
        "source_sha256": {"sealed": file_sha256(SEALED), "locked": file_sha256(LOCKED),
                          "commitment": file_sha256(COMMITMENT), "bindings": file_sha256(BINDINGS)},
        "stage8672_promotion_replay_blocked": False,
        "stage8672_training_ingestion_blocked": False,
        "stage8672_training_ingestion_policy_required": True,
        "raw_protected_payload_emitted": False,
        **ZERO,
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    result = build()
    write_json(OUT / "operational_legacy_deny_audit.json", result)
    write_json(OUT / "summary.json", result)
    write_json(SUMMARY, result)
    print(json.dumps({key: result[key] for key in ("protected_root_count", "certified_git_root_count", "unresolved_protected_root_count", "candidate_commitment_valid", "legacy_deny_enforced", "sandbox_progression_allowed", "blocking_reasons")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
