#!/usr/bin/env python3
"""Commit exact candidate/task pairs before any replay outcome is available."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12565_paired_pre_outcome_candidate_commitment_v2"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
SOURCES = {
    "stage12555_exact_authority_bindings": ROOT / "runs/local/artifacts/stage12555_swe_rebench_identity_adapter/exact_task_authority_bindings.jsonl",
    "stage12555_summary": ROOT / "runs/summaries/stage12555_swe_rebench_identity_adapter.json",
    "stage12556_ready_rows": ROOT / "runs/local/artifacts/stage12556_local_checkout_readiness_census/checkout_object_ready.jsonl",
    "stage12556_summary": ROOT / "runs/summaries/stage12556_local_checkout_readiness_census.json",
    "active_protected_swe_bench_manifest": ROOT / "runs/local/artifacts/stage12554_authority_inventory_and_overlap_gate/protected_swe_bench_verified_manifest.json",
    "stage11507_runtime_bundle": ROOT / "runs/local/artifacts/stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json",
    "stage11507_runtime_weights": ROOT / "runs/local/artifacts/stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/model_state.pt",
    "stage11509_frontier_decision": ROOT / "runs/summaries/stage11509_preservation_strengthened_frontier_promotion_decision.json",
}
PINNED_SOURCE_SHA256 = {
    "active_protected_swe_bench_manifest": "50e52154348d471c0d6407e466b3bffce4a197fbe81cce6db122ef22c4bcb5c5",
    "stage11507_runtime_bundle": "415a4d172c45238258f42eae3b51b23820e7482494a2aed340ddff56687510db",
    "stage11507_runtime_weights": "8bc717e1b3f7cf8321262d1a70f4ee86489a6fb10e6ae3f16eb6646f72b3ad37",
    "stage11509_frontier_decision": "865493cc65bad5ebd7dda26ed2914ab57cbc688b56eed8336fe90e19a2b10f72",
    "stage12555_exact_authority_bindings": "b423a417dc2f0a65c808a4edd2b3e4b7cdd8f90c0f3af8de8a92e8a5575bbeae",
    "stage12555_summary": "3f6ca86dcc00771721c3f4c46a4473e92c9edc582acad5293c3260526ebe3907",
    "stage12556_ready_rows": "ad7f205b0b757437c073ca88e014bdd0140083bbbeb5b93b6e088e1f55b91511",
    "stage12556_summary": "1618f0dac59496acecc16c7a3f4f0f979b745f297cfbac3b21dd53d2b80bbb03",
}
EXPECTED_COUNT = 8
EXPECTED_SCORER = "encoder_option_retrieval_evidence_judgment_head"
EXPECTED_WEIGHTS_SHA256 = PINNED_SOURCE_SHA256["stage11507_runtime_weights"]
EXPECTED_MODEL = {
    "runtime_stage": 11507,
    "scorer": EXPECTED_SCORER,
    "weights_sha256": EXPECTED_WEIGHTS_SHA256,
}
AUTHORIZATION_POLICY = "commitment_only_never_authorizes_replay_training_execution_or_gpu"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^[0-9a-f]{64}$")
ALLOWED_SELECTION_FEATURES = (
    "candidate_id",
    "full_task_key",
    "policy_split_train",
    "exact_stage12555_authority_binding",
    "stage12556_checkout_object_ready",
    "canonical_repo",
    "base_commit",
    "instance_id",
    "task_identity_sha256",
    "task_snapshot_sha256",
)
FORBIDDEN_SELECTION_FEATURES = (
    "replay_outcome",
    "verifier_exit",
    "test_output",
    "reward",
    "model_prediction",
    "gold_patch",
    "patch_effect",
    "protected_target",
)
ZERO = {
    "admission_allowed": False,
    "training_allowed": False,
    "replay_allowed": False,
    "gpu_allowed": False,
    "execution_authorized": False,
    "root_credit": False,
    "repair_credit": False,
    "level3_credit": False,
    "strict_eval_eligible": False,
}


def stable_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(encoded).hexdigest()


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
        raise ValueError(f"expected JSON object: {path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    values = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not all(isinstance(value, dict) for value in values):
        raise ValueError(f"expected JSON object rows: {path}")
    return values


def _duplicates(values: list[str]) -> bool:
    return len(values) != len(set(values))


def contains_forbidden_field(value: Any) -> bool:
    forbidden = set(FORBIDDEN_SELECTION_FEATURES)
    if isinstance(value, dict):
        return any(str(key).lower() in forbidden or contains_forbidden_field(child) for key, child in value.items())
    if isinstance(value, list):
        return any(contains_forbidden_field(child) for child in value)
    return False


def ready_row_projection(row: dict[str, Any]) -> dict[str, Any]:
    certificate = row.get("checkout_object_certificate")
    certificate = certificate if isinstance(certificate, dict) else {}
    return {
        "candidate_id": row.get("candidate_id"),
        "task_key": row.get("task_key"),
        "language": row.get("language"),
        "certificate_sha256": row.get("certificate_sha256"),
        "checkout_object_certificate": {
            key: certificate.get(key)
            for key in ("canonical_repo", "origin_url", "base_commit", "base_tree", "covering_refs", "mirror_path")
        },
        "lineage_status": row.get("lineage_status"),
        "protected_content_used": row.get("protected_content_used"),
    }


def authority_row_projection(row: dict[str, Any]) -> dict[str, Any]:
    identity = row.get("task_identity")
    identity = identity if isinstance(identity, dict) else {}
    return {
        "candidate_id": row.get("candidate_id"),
        "task_key": row.get("task_key"),
        "task_snapshot_sha256": row.get("task_snapshot_sha256"),
        "task_identity": {
            key: identity.get(key)
            for key in (
                "dataset", "revision", "source_split", "instance_id",
                "canonical_repo", "base_commit", "language", "created_at",
            )
        },
        "task_identity_sha256": row.get("task_identity_sha256"),
        "policy_split": row.get("policy_split"),
        "policy_split_key": row.get("policy_split_key"),
        "protected_from_training": row.get("protected_from_training"),
    }


def _task_key_valid(task_key: Any, identity: dict[str, Any]) -> bool:
    return (
        isinstance(task_key, list)
        and len(task_key) == 4
        and all(isinstance(item, str) and item for item in task_key)
        and task_key[0] == identity.get("dataset")
        and task_key[1] == identity.get("revision")
        and task_key[2] == identity.get("source_split")
        and task_key[3] == identity.get("instance_id")
    )


def _contract(source_hashes: dict[str, str | None]) -> dict[str, Any]:
    return {
        "schema": "paired_pre_outcome_candidate_commitment_v2",
        "selection_algorithm": "all_and_only_current_stage12556_ready_rows_exact_join_stage12555_by_candidate_id_sorted",
        "expected_atomic_record_count": EXPECTED_COUNT,
        "selected_model": dict(EXPECTED_MODEL),
        "allowed_selection_features": list(ALLOWED_SELECTION_FEATURES),
        "forbidden_selection_features": list(FORBIDDEN_SELECTION_FEATURES),
        "input_read_policy": {
            "identity_and_readiness_only": True,
            "replay_outcomes_read": False,
            "test_outputs_read": False,
            "rewards_read": False,
            "model_predictions_read": False,
            "gold_patches_read": False,
        },
        "authoritative_source_sha256": dict(sorted(source_hashes.items())),
        "authorization_policy": AUTHORIZATION_POLICY,
        "source_row_projection_schema": "stage12565_identity_readiness_allowlist_v1",
    }


def verify_envelope(value: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    contract = value.get("contract")
    records = value.get("atomic_records")
    if not isinstance(contract, dict) or contract.get("schema") != "paired_pre_outcome_candidate_commitment_v2":
        blockers.append("contract_schema_invalid")
        contract = {}
    if not isinstance(records, list):
        blockers.append("atomic_records_not_a_list")
        records = []
    if len(records) != EXPECTED_COUNT:
        blockers.append("atomic_record_count_not_exactly_eight")
    candidate_ids = [str(row.get("candidate_id") or "") for row in records if isinstance(row, dict)]
    if len(candidate_ids) != len(records) or any(not item for item in candidate_ids) or _duplicates(candidate_ids):
        blockers.append("atomic_candidate_ids_missing_or_duplicate")
    if candidate_ids != sorted(candidate_ids):
        blockers.append("atomic_records_not_deterministically_sorted")
    for row in records:
        if not isinstance(row, dict):
            blockers.append("atomic_record_invalid")
            continue
        body = {key: item for key, item in row.items() if key != "atomic_record_sha256"}
        if row.get("atomic_record_sha256") != stable_hash(body):
            blockers.append("atomic_record_digest_mismatch")
        task_key = row.get("task_key")
        if not isinstance(task_key, list) or len(task_key) != 4 or task_key[3] != row.get("instance_id"):
            blockers.append("atomic_task_key_instance_mismatch")
        if row.get("selected_model") != EXPECTED_MODEL:
            blockers.append("atomic_selected_model_mismatch")
    committed = {"contract": contract, "atomic_records": records}
    if value.get("commitment_sha256") != stable_hash(committed):
        blockers.append("top_level_commitment_digest_mismatch")
    source_hashes = contract.get("authoritative_source_sha256")
    if source_hashes != dict(sorted(PINNED_SOURCE_SHA256.items())):
        blockers.append("authoritative_source_anchor_mismatch")
    if contract.get("allowed_selection_features") != list(ALLOWED_SELECTION_FEATURES):
        blockers.append("allowed_selection_features_changed")
    if contract.get("forbidden_selection_features") != list(FORBIDDEN_SELECTION_FEATURES):
        blockers.append("forbidden_selection_features_changed")
    if contract.get("selected_model") != EXPECTED_MODEL:
        blockers.append("contract_selected_model_mismatch")
    if contract.get("authorization_policy") != AUTHORIZATION_POLICY:
        blockers.append("authorization_policy_changed")
    if any(value.get(key) is not False for key in ZERO):
        blockers.append("prohibited_authorization_flag")
    return sorted(set(blockers))


def build(
    ready_rows: list[dict[str, Any]],
    authority_rows: list[dict[str, Any]],
    checkout_summary: dict[str, Any],
    authority_summary: dict[str, Any],
    runtime_bundle: dict[str, Any],
    frontier_decision: dict[str, Any],
    source_hashes: dict[str, str | None],
) -> dict[str, Any]:
    blockers: list[str] = []
    ready_ids = [str(row.get("candidate_id") or "") for row in ready_rows]
    authority_ids = [str(row.get("candidate_id") or "") for row in authority_rows]
    if len(ready_rows) != EXPECTED_COUNT:
        blockers.append("stage12556_ready_count_not_exactly_eight")
    if any(not item for item in ready_ids) or _duplicates(ready_ids):
        blockers.append("stage12556_candidate_ids_missing_or_duplicate")
    if any(not item for item in authority_ids) or _duplicates(authority_ids):
        blockers.append("stage12555_candidate_ids_missing_or_duplicate")
    if set(source_hashes) != set(SOURCES) or source_hashes != PINNED_SOURCE_SHA256:
        blockers.append("authoritative_source_hash_missing_or_changed")
    if checkout_summary.get("exact_checkout_object_ready_count") != EXPECTED_COUNT:
        blockers.append("stage12556_summary_ready_count_mismatch")
    if authority_summary.get("task_snapshot_sha256") is None:
        blockers.append("stage12555_task_snapshot_missing")

    selected = frontier_decision.get("selected_frontier_after_decision") or {}
    metadata = runtime_bundle.get("metadata") or {}
    runtime_valid = (
        selected.get("runtime_stage") == 11507
        and selected.get("scorer") == EXPECTED_SCORER
        and metadata.get("bounded_choice_aux_source") == EXPECTED_SCORER
        and runtime_bundle.get("weights_sha256") == EXPECTED_WEIGHTS_SHA256
        and source_hashes.get("stage11507_runtime_weights") == EXPECTED_WEIGHTS_SHA256
    )
    if not runtime_valid:
        blockers.append("selected_stage11507_runtime_scorer_or_weights_mismatch")

    by_candidate = {str(row.get("candidate_id") or ""): row for row in authority_rows}
    records: list[dict[str, Any]] = []
    for ready in ready_rows:
        candidate_id = str(ready.get("candidate_id") or "")
        authority = by_candidate.get(candidate_id)
        if authority is None:
            blockers.append("ready_candidate_missing_exact_stage12555_binding")
            continue
        if contains_forbidden_field(ready) or contains_forbidden_field(authority):
            blockers.append("forbidden_candidate_source_field_present")
        identity = authority.get("task_identity")
        identity = identity if isinstance(identity, dict) else {}
        certificate = ready.get("checkout_object_certificate")
        certificate = certificate if isinstance(certificate, dict) else {}
        task_key = ready.get("task_key")
        if task_key != authority.get("task_key"):
            blockers.append("candidate_task_key_join_mismatch")
        if not _task_key_valid(task_key, identity) or not _task_key_valid(authority.get("task_key"), identity):
            blockers.append("full_task_key_identity_mismatch")
        if authority.get("policy_split") != "train":
            blockers.append("candidate_policy_split_not_train")
        if authority.get("task_identity_sha256") != stable_hash(identity):
            blockers.append("task_identity_digest_mismatch")
        if authority.get("task_snapshot_sha256") != authority_summary.get("task_snapshot_sha256"):
            blockers.append("task_snapshot_digest_mismatch")
        repo = str(identity.get("canonical_repo") or "")
        commit = str(identity.get("base_commit") or "")
        if repo != certificate.get("canonical_repo"):
            blockers.append("canonical_repo_authority_checkout_mismatch")
        if commit != certificate.get("base_commit") or not SHA40.fullmatch(commit):
            blockers.append("base_commit_authority_checkout_mismatch_or_invalid")
        if not DIGEST.fullmatch(str(authority.get("task_identity_sha256") or "")):
            blockers.append("task_identity_digest_invalid")
        if not DIGEST.fullmatch(str(authority.get("task_snapshot_sha256") or "")):
            blockers.append("task_snapshot_digest_invalid")
        body = {
            "record_type": "stage12565_atomic_candidate_task_commitment_v2",
            "candidate_id": candidate_id,
            "task_key": task_key,
            "canonical_repo": repo,
            "base_commit": commit,
            "instance_id": identity.get("instance_id"),
            "policy_split": authority.get("policy_split"),
            "task_identity_sha256": authority.get("task_identity_sha256"),
            "task_snapshot_sha256": authority.get("task_snapshot_sha256"),
            "source_artifact_sha256": {
                "stage12555_exact_authority_bindings": source_hashes.get("stage12555_exact_authority_bindings"),
                "stage12556_ready_rows": source_hashes.get("stage12556_ready_rows"),
            },
            "source_row_sha256": {
                "stage12555_exact_authority_binding": stable_hash(authority_row_projection(authority)),
                "stage12556_ready_row": stable_hash(ready_row_projection(ready)),
            },
            "selected_model": dict(EXPECTED_MODEL),
        }
        records.append({**body, "atomic_record_sha256": stable_hash(body)})

    records.sort(key=lambda row: row["candidate_id"])
    contract = _contract(source_hashes)
    committed = {"contract": contract, "atomic_records": records}
    result = {
        "stage": STAGE,
        "record_type": "stage12565_paired_pre_outcome_candidate_commitment_v2",
        **committed,
        "commitment_sha256": stable_hash(committed),
        "atomic_record_count": len(records),
        "pre_outcome_commitment_valid": False,
        "blocking_reasons": [],
        **ZERO,
    }
    blockers.extend(verify_envelope(result))
    result["blocking_reasons"] = sorted(set(blockers))
    result["pre_outcome_commitment_valid"] = not result["blocking_reasons"]
    return result


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    source_hashes = {name: file_sha256(path) for name, path in SOURCES.items()}
    result = build(
        read_jsonl(SOURCES["stage12556_ready_rows"]),
        read_jsonl(SOURCES["stage12555_exact_authority_bindings"]),
        read_json(SOURCES["stage12556_summary"]),
        read_json(SOURCES["stage12555_summary"]),
        read_json(SOURCES["stage11507_runtime_bundle"]),
        read_json(SOURCES["stage11509_frontier_decision"]),
        source_hashes,
    )
    write_json(OUT / "paired_candidate_commitment_v2.json", result)
    write_json(OUT / "summary.json", result)
    write_json(SUMMARY, result)
    print(json.dumps({key: result[key] for key in (
        "atomic_record_count", "pre_outcome_commitment_valid", "commitment_sha256",
        "blocking_reasons", "replay_allowed", "training_allowed", "gpu_allowed",
    )}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
