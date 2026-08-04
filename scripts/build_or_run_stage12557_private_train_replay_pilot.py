#!/usr/bin/env python3
"""Build a fail-closed, train-only private replay pilot for Stage12557."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
_GUARD_SPEC = importlib.util.spec_from_file_location("stage12567_source_lineage_guard", ROOT / "scripts/source_lineage_guard.py")
if not _GUARD_SPEC or not _GUARD_SPEC.loader:
    raise ImportError("source_lineage_guard.py is unavailable")
_GUARD = importlib.util.module_from_spec(_GUARD_SPEC)
sys.modules[_GUARD_SPEC.name] = _GUARD
_GUARD_SPEC.loader.exec_module(_GUARD)
evaluate_row_source_lineage = _GUARD.evaluate_row_source_lineage
load_source_registry = _GUARD.load_source_registry
_COMMITMENT_SPEC = importlib.util.spec_from_file_location("stage12565_contract", ROOT / "scripts/build_stage12565_paired_pre_outcome_candidate_commitment_v2.py")
if not _COMMITMENT_SPEC or not _COMMITMENT_SPEC.loader:
    raise ImportError("Stage12565 commitment builder is unavailable")
_COMMITMENT = importlib.util.module_from_spec(_COMMITMENT_SPEC)
sys.modules[_COMMITMENT_SPEC.name] = _COMMITMENT
_COMMITMENT_SPEC.loader.exec_module(_COMMITMENT)
STAGE = "stage12557_private_train_replay_pilot"
READY = ROOT / "runs/local/artifacts/stage12556_local_checkout_readiness_census/checkout_object_ready.jsonl"
TRAJECTORIES = ROOT / "runs/local/artifacts/stage12554_authority_inventory_and_overlap_gate/resolved_authority_fields.jsonl"
TASKS = ROOT / "runs/local/artifacts/stage12555_swe_rebench_identity_adapter/exact_task_authority_bindings.jsonl"
TASK_PARQUET = Path("/arxiv/datasets/nebius--SWE-rebench-V2/data/train-00000-of-00001.parquet")
TASK_PARQUET_SHA256 = "0e0bf9355f892ad74ae98d4e1c404f39fd6654a8e351ee3e6ab162e4a64cd3ad"
OUT = ROOT / "runs/local/artifacts" / STAGE
PRIVATE = ROOT / "runs/local/private" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
ATOMIC_COMMITMENT = ROOT / "runs/local/artifacts/stage12565_paired_pre_outcome_candidate_commitment_v2/paired_candidate_commitment_v2.json"
LINEAGE_STATE = ROOT / "runs/local/artifacts/stage12564_authoritative_protected_lineage_preflight/authoritative_protected_lineage_preflight.json"
SOURCE_ADAPTER = ROOT / "runs/local/artifacts/stage12568_open_swe_source_lineage_adapter/source_lineage_reference_adapter.json"
TRAJECTORY_COLUMNS = ("instance_id", "repo", "trajectory_id", "model_patch")
TASK_IDENTITY_COLUMNS = ("instance_id", "repo", "base_commit", "language")
TASK_VERIFIER_COLUMNS = ("instance_id", "install_config", "FAIL_TO_PASS")
NEVER_READ = {"patch", "test_patch", "problem_statement", "pr_description", "PR description", "PASS_TO_PASS"}
EXPECTED_CANDIDATE_COUNT = 8
CANONICAL_OPEN_SWE_SOURCE_ID = "src_53e6cea43bf6fbb6"
PINNED_OPEN_SWE_REVISION = "f6689f56f1af2e2082861738071d4c4278b1922a"
PINNED_OPEN_SWE_SHARD_SHA256 = "5befb7356a4bce7c13bc5a8313fdd42df0488c567eeaf42a668dcf307642320e"
ATOMIC_COMMITMENT_SHA256 = "f90d9a972f4e2029c97344f8ed17fa9d2f1ce8f143651901f7d21a4d3bd53e1a"
LINEAGE_STATE_SHA256 = "c9e95cbab0eac344e8be5e595067114ef380730fb17baa627c1868451d99aede"
SOURCE_ADAPTER_SHA256 = "a83a025e54283e82018c3762554c14d5ed5c74767201f0d8f3a84a59f70b519b"
SOURCE_ADAPTER_SEMANTIC_SHA256 = "a2df700a7355fce2e54724ec4ccd2d2d7c29030ec8ce90480a0166985a791f11"
BASE_REGISTRY_SHA256 = "98b50df0083fea7be08ccf513b361e78669a2d1be03db7948a2f0a3a90bab807"
DIGEST = re.compile(r"^[0-9a-f]{64}\Z")
ZERO = {
    "admission_allowed": False, "training_allowed": False, "gpu_allowed": False,
    "replay_allowed": False, "root_credit": False, "repair_credit": False,
    "strict_eval_eligible": False, "level3_credit": False,
}


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def stable_hash(value: Any) -> str:
    return digest_bytes(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode())


def file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def read_json(path: Path) -> dict[str, Any]:
    result = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError(f"expected JSON object: {path}")
    return result


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def value(binding: dict[str, Any], field: str) -> Any:
    item = (binding.get("resolved_fields") or {}).get(field)
    return item.get("value") if isinstance(item, dict) else None


def source(binding: dict[str, Any], field: str) -> Path:
    item = (binding.get("resolved_fields") or {}).get(field)
    return Path(str(item.get("source") or "")) if isinstance(item, dict) else Path()


def canonical_repo(raw: Any) -> str:
    return str(raw or "").strip().strip("/").removesuffix(".git").lower()


def _join_task_projections(
    identity_rows: list[dict[str, Any]], verifier_rows: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    identity_ids = [str(row.get("instance_id") or "") for row in identity_rows]
    verifier_ids = [str(row.get("instance_id") or "") for row in verifier_rows]
    if any(not instance for instance in identity_ids):
        return {}, ["task_identity_instance_id_missing"]
    if any(not instance for instance in verifier_ids):
        return {}, ["task_verifier_instance_id_missing"]
    if set(identity_ids) != set(verifier_ids):
        return {}, ["task_identity_verifier_join_key_mismatch"]
    if len(identity_ids) != len(set(identity_ids)) or len(verifier_ids) != len(set(verifier_ids)):
        return {}, ["task_identity_verifier_join_key_not_unique"]
    identities = {str(row["instance_id"]): row for row in identity_rows}
    verifiers = {str(row["instance_id"]): row for row in verifier_rows}
    return {
        instance: [{**identities[instance], **verifiers[instance]}]
        for instance in sorted(identities)
    }, []


def _identity_pairs(
    ready_rows: list[dict[str, Any]], task_rows: list[dict[str, Any]],
    trajectory_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    blockers: list[str] = []
    ready_ids = [str(row.get("candidate_id") or "") for row in ready_rows]
    if len(ready_rows) != EXPECTED_CANDIDATE_COUNT:
        blockers.append("ready_candidate_count_not_exactly_eight")
    if any(not item for item in ready_ids) or len(ready_ids) != len(set(ready_ids)):
        blockers.append("ready_candidate_ids_missing_or_duplicate")
    task_ids = [str(row.get("candidate_id") or "") for row in task_rows]
    if len(task_rows) != EXPECTED_CANDIDATE_COUNT:
        blockers.append("task_candidate_count_not_exactly_eight")
    if any(not item for item in task_ids) or len(task_ids) != len(set(task_ids)):
        blockers.append("task_candidate_ids_missing_or_duplicate")
    if set(task_ids) != set(ready_ids):
        blockers.append("task_candidate_set_not_exactly_ready")
    task_by_id = {str(row.get("candidate_id") or ""): row for row in task_rows}
    trajectory_ids = [str(row.get("candidate_id") or "") for row in trajectory_rows]
    if len(trajectory_rows) != EXPECTED_CANDIDATE_COUNT:
        blockers.append("trajectory_candidate_count_not_exactly_eight")
    if any(not item for item in trajectory_ids) or len(trajectory_ids) != len(set(trajectory_ids)):
        blockers.append("trajectory_candidate_ids_missing_or_duplicate")
    if set(trajectory_ids) != set(ready_ids):
        blockers.append("trajectory_candidate_set_not_exactly_ready")
    trajectory_by_id = {str(row.get("candidate_id") or ""): row for row in trajectory_rows}
    pairs: list[dict[str, Any]] = []
    for ready in ready_rows:
        candidate_id = str(ready.get("candidate_id") or "")
        task = task_by_id.get(candidate_id)
        trajectory = trajectory_by_id.get(candidate_id)
        if task is None or trajectory is None:
            blockers.append("ready_candidate_missing_task_or_trajectory_identity")
            continue
        identity = task.get("task_identity") if isinstance(task.get("task_identity"), dict) else {}
        certificate = ready.get("checkout_object_certificate")
        certificate = certificate if isinstance(certificate, dict) else {}
        fields = trajectory.get("resolved_fields")
        fields = fields if isinstance(fields, dict) else {}
        task_key = ready.get("task_key")
        if not (
            task.get("task_key") == task_key
            and isinstance(task_key, list) and len(task_key) == 4
            and task_key[3] == identity.get("instance_id")
            and task.get("policy_split") == "train"
            and task.get("protected_from_training") is False
            and canonical_repo(identity.get("canonical_repo")) == canonical_repo(certificate.get("canonical_repo"))
            and str(identity.get("base_commit") or "").lower() == str(certificate.get("base_commit") or "").lower()
        ):
            blockers.append("ready_task_exact_identity_pair_mismatch")
        dataset = value(trajectory, "trajectory_dataset")
        revision = value(trajectory, "trajectory_revision")
        config = value(trajectory, "trajectory_config")
        split = value(trajectory, "trajectory_split")
        shard = value(trajectory, "trajectory_shard_id")
        shard_sha = value(trajectory, "trajectory_shard_sha256")
        ordinal = value(trajectory, "trajectory_ordinal")
        trajectory_id = value(trajectory, "trajectory_id")
        expected_key = [dataset, revision, config, split, shard, ordinal, trajectory_id]
        expected_path = Path(f"/arxiv/datasets/nvidia--Open-SWE-Traces/data/{split}_{config}_trajectories/{shard}")
        parquet_fields = (
            "canonical_repo", "model_patch_sha256", "source_row_sha256",
            "trajectory_id", "trajectory_instance_id", "trajectory_ordinal",
        )
        source_binding_exact = all(source(trajectory, field) == expected_path for field in parquet_fields)
        trajectory_exact = (
            trajectory.get("namespaced_trajectory_key") == expected_key
            and dataset == "nvidia/Open-SWE-Traces"
            and revision == PINNED_OPEN_SWE_REVISION
            and shard_sha == PINNED_OPEN_SWE_SHARD_SHA256
            and isinstance(value(trajectory, "source_row_sha256"), str)
            and DIGEST.fullmatch(value(trajectory, "source_row_sha256")) is not None
            and isinstance(value(trajectory, "model_patch_sha256"), str)
            and DIGEST.fullmatch(value(trajectory, "model_patch_sha256")) is not None
            and value(trajectory, "trajectory_instance_id") == identity.get("instance_id")
            and canonical_repo(value(trajectory, "canonical_repo")) == canonical_repo(identity.get("canonical_repo"))
            and value(trajectory, "upstream_task_dataset") == identity.get("dataset")
            and source_binding_exact
        )
        if not trajectory_exact:
            blockers.append("trajectory_exact_source_binding_mismatch")
        trajectory_ref = f"trajectory:{dataset}@{revision}:{config}:{split}:{shard}:{shard_sha}"
        pairs.append({
            "candidate_id": candidate_id, "task_key": task_key,
            "canonical_repo": canonical_repo(identity.get("canonical_repo")),
            "base_commit": str(identity.get("base_commit") or "").lower(),
            "instance_id": identity.get("instance_id"), "policy_split": task.get("policy_split"),
            "ready": ready, "task": task, "trajectory": trajectory,
            "source_ids": [CANONICAL_OPEN_SWE_SOURCE_ID] if trajectory_exact else [],
            "provenance_refs": [trajectory_ref] if trajectory_exact else [],
            "authority_hashes": {},
            "parents": [ready, task, trajectory],
        })
    return sorted(pairs, key=lambda row: row["candidate_id"]), sorted(set(blockers))


def _commitment_blockers(value: dict[str, Any], pairs: list[dict[str, Any]], path: Path) -> list[str]:
    blockers = [f"stage12565_{reason}" for reason in _COMMITMENT.verify_envelope(value)]
    if file_sha256(path) != ATOMIC_COMMITMENT_SHA256:
        blockers.append("stage12565_atomic_commitment_artifact_digest_mismatch")
    contract = value.get("contract") if isinstance(value.get("contract"), dict) else {}
    records = value.get("atomic_records") if isinstance(value.get("atomic_records"), list) else []
    actual_sources = {
        "stage12555_exact_authority_bindings": file_sha256(TASKS),
        "stage12556_ready_rows": file_sha256(READY),
    }
    contract_sources = contract.get("authoritative_source_sha256")
    contract_sources = contract_sources if isinstance(contract_sources, dict) else {}
    if any(contract_sources.get(name) != digest for name, digest in actual_sources.items()):
        blockers.append("stage12565_authoritative_identity_source_hash_mismatch")
    if contract.get("selected_model") != _COMMITMENT.EXPECTED_MODEL:
        blockers.append("stage12565_selected_model_binding_mismatch")
    by_candidate = {str(row.get("candidate_id") or ""): row for row in records if isinstance(row, dict)}
    if set(by_candidate) != {row["candidate_id"] for row in pairs}:
        blockers.append("stage12565_committed_candidate_set_mismatch")
    for pair in pairs:
        atomic = by_candidate.get(pair["candidate_id"])
        if atomic is None:
            continue
        ready = pair["ready"]
        task = pair["task"]
        identity = task.get("task_identity") if isinstance(task.get("task_identity"), dict) else {}
        expected_source_rows = {
            "stage12555_exact_authority_binding": _COMMITMENT.stable_hash(_COMMITMENT.authority_row_projection(task)),
            "stage12556_ready_row": _COMMITMENT.stable_hash(_COMMITMENT.ready_row_projection(ready)),
        }
        exact_atomic = (
            atomic.get("candidate_id") == pair["candidate_id"]
            and atomic.get("task_key") == pair["task_key"]
            and canonical_repo(atomic.get("canonical_repo")) == pair["canonical_repo"]
            and str(atomic.get("base_commit") or "").lower() == pair["base_commit"]
            and atomic.get("instance_id") == pair["instance_id"]
            and atomic.get("policy_split") == pair["policy_split"]
            and atomic.get("task_identity_sha256") == task.get("task_identity_sha256")
            and task.get("task_identity_sha256") == _COMMITMENT.stable_hash(identity)
            and atomic.get("task_snapshot_sha256") == task.get("task_snapshot_sha256")
            and atomic.get("source_row_sha256") == expected_source_rows
            and atomic.get("source_artifact_sha256") == actual_sources
            and atomic.get("selected_model") == _COMMITMENT.EXPECTED_MODEL
        )
        if not exact_atomic:
            blockers.append("stage12565_atomic_binding_reconstruction_mismatch")
        pair["authority_hashes"].update({name: digest for name, digest in sorted(actual_sources.items()) if digest})
        pair["provenance_refs"].extend(
            [f"{name}:sha256:{digest}" for name, digest in sorted(actual_sources.items()) if digest]
        )
        pair["provenance_refs"].append(
            f"stage12565_commitment:sha256:{value.get('commitment_sha256')}"
        )
    return sorted(set(blockers))


def _source_adapter_blockers(
    value: dict[str, Any], pairs: list[dict[str, Any]], path: Path
) -> list[str]:
    blockers: list[str] = []
    body = {key: item for key, item in value.items() if key != "adapter_sha256"}
    if file_sha256(path) != SOURCE_ADAPTER_SHA256:
        blockers.append("stage12568_adapter_artifact_hash_mismatch")
    if value.get("adapter_sha256") != SOURCE_ADAPTER_SEMANTIC_SHA256:
        blockers.append("stage12568_adapter_semantic_hash_mismatch")
    if value.get("adapter_sha256") != stable_hash(body):
        blockers.append("stage12568_adapter_self_hash_mismatch")
    exact_top_level = (
        value.get("record_type") == "stage12568_source_lineage_reference_adapter_v1"
        and value.get("reference_mapping_valid") is True
        and value.get("source_known") is True
        and value.get("canonical_source_id") == CANONICAL_OPEN_SWE_SOURCE_ID
        and value.get("base_registry_sha256") == BASE_REGISTRY_SHA256
        and value.get("base_registry_mutated") is False
        and value.get("protected_clearance") is False
        and value.get("effective_train_eligible") is False
        and value.get("control_plane_blocker") == "stage12564_stage12557_attestation_dependency_cycle"
        and value.get("blocking_reasons") == []
    )
    if not exact_top_level:
        blockers.append("stage12568_adapter_top_level_semantics_invalid")
    authorization_fields = set(ZERO) | {"execution_authorized"}
    if any(value.get(name) is not False for name in authorization_fields):
        blockers.append("stage12568_adapter_authorization_not_all_false")

    authority_hashes = value.get("authority_hashes")
    authority_hashes = authority_hashes if isinstance(authority_hashes, dict) else {}
    expected_authority_hashes = {
        "stage12554_resolved_trajectory_bindings": "98a7f396868d2c7672129c71b7a0c7d62337ee389bdde8e0e37de153ef76dcbd",
        "stage12555_exact_authority_bindings": "b423a417dc2f0a65c808a4edd2b3e4b7cdd8f90c0f3af8de8a92e8a5575bbeae",
        "stage12556_ready_rows": "ad7f205b0b757437c073ca88e014bdd0140083bbbeb5b93b6e088e1f55b91511",
        "stage12565_paired_commitment": ATOMIC_COMMITMENT_SHA256,
    }
    if authority_hashes != expected_authority_hashes:
        blockers.append("stage12568_adapter_authority_hashes_invalid")
    expected_refs = [
        f"{name}:sha256:{digest}" for name, digest in sorted(expected_authority_hashes.items())
    ]
    bindings = value.get("bindings") if isinstance(value.get("bindings"), list) else []
    binding_ids = [str(row.get("candidate_id") or "") for row in bindings if isinstance(row, dict)]
    pair_ids = [str(pair.get("candidate_id") or "") for pair in pairs]
    if len(bindings) != 8 or len(binding_ids) != len(set(binding_ids)) or set(binding_ids) != set(pair_ids):
        blockers.append("stage12568_adapter_candidate_set_invalid")
    for binding in bindings:
        if not isinstance(binding, dict):
            blockers.append("stage12568_adapter_binding_invalid")
            continue
        if (
            binding.get("source_ids") != [CANONICAL_OPEN_SWE_SOURCE_ID]
            or binding.get("source_known") is not True
            or binding.get("provenance_refs") != expected_refs
            or binding.get("authority_hashes") != expected_authority_hashes
            or any(binding.get(name) is not False for name in authorization_fields)
        ):
            blockers.append("stage12568_adapter_binding_semantics_invalid")
    blockers = sorted(set(blockers))
    if blockers:
        for pair in pairs:
            pair["source_ids"] = []
    return blockers


def _lineage_state_blockers(value: dict[str, Any], path: Path) -> list[str]:
    blockers: list[str] = []
    if file_sha256(path) != LINEAGE_STATE_SHA256:
        blockers.append("stage12564_state_artifact_digest_mismatch")
    if value.get("record_type") != "stage12564_authoritative_protected_lineage_preflight_summary_v1":
        blockers.append("stage12564_state_schema_invalid")
    required_true = (
        "legacy_source_anchors_valid", "locked_pack_exact_semantics_valid",
        "active_protected_manifest_anchored", "stage12561_active_protected_disjointness_proven",
        "stage12562_commitment_envelope_valid", "stage12562_commitment_sources_current",
        "committed_candidate_selection_exact", "candidate_repo_commit_provenance_complete",
        "operational_ingestion_hooks_verified", "all_authorization_requirements_demonstrated",
        "protected_lineage_enforcement_authoritative",
    )
    if any(value.get(key) is not True for key in required_true):
        blockers.append("stage12564_fail_closed_state")
    if value.get("candidate_count") != EXPECTED_CANDIDATE_COUNT:
        blockers.append("stage12564_candidate_count_not_exactly_eight")
    if value.get("unresolved_protected_root_count") != 0 or value.get("blocking_reasons"):
        blockers.append("stage12564_protected_lineage_unresolved")
    if any(value.get(key) is not True for key in ("admission_allowed", "training_allowed", "replay_allowed")):
        blockers.append("stage12564_replay_authorization_absent")
    return sorted(set(blockers))


def _recursive_lineage_blockers(pairs: list[dict[str, Any]]) -> tuple[list[str], list[dict[str, Any]]]:
    if file_sha256(_GUARD.DEFAULT_LINEAGE) != BASE_REGISTRY_SHA256:
        return ["base_source_registry_artifact_hash_mismatch"], []
    registry = load_source_registry()
    decisions = [evaluate_row_source_lineage(pair, registry) for pair in pairs]
    blockers = [] if decisions and all(row.get("source_ids") and row.get("train_eligible_lineage") is True for row in decisions) else ["recursive_source_lineage_guard_denied"]
    return blockers, decisions


def _denied_result(
    ready_rows: list[dict[str, Any]], blockers: list[str], decisions: list[dict[str, Any]]
) -> dict[str, Any]:
    reason = blockers[0] if blockers else "pre_read_guard_denied"
    records = []
    for ready in ready_rows:
        record = base_record(ready)
        record["blocking_reasons"] = blockers
        record["stop_continue"] = {"decision": "stop", "reason": reason}
        record["pre_read_guard"] = {"allowed": False, "sensitive_reads_performed": False}
        records.append(record)
    summary = {
        "stage": STAGE,
        "record_type": "stage12557_private_train_replay_pilot_summary_v2",
        "input_ready_count": len(ready_rows), "record_count": len(records),
        "pre_read_guard_allowed": False, "pre_read_guard_denied_count": len(records),
        "blocking_reasons": blockers, "recursive_lineage_decisions": decisions,
        "task_identity_columns": list(TASK_IDENTITY_COLUMNS),
        "task_verifier_columns_read": [], "trajectory_columns_read": [],
        "verifier_bearing_parquet_read": False, "trajectory_model_patch_read": False,
        "subprocess_invoked": False, "executed_count": 0,
        "all_ingestion_routes_integrated": False,
        "global_ingestion_coverage_claimed": False,
        "default_disposition": "fail_closed_before_sensitive_reads",
        **ZERO,
    }
    return {"records": records, "summary": summary}



def base_record(ready: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_type": "stage12557_private_train_replay_pilot_v1",
        "candidate_id": ready.get("candidate_id"), "task_key": ready.get("task_key"),
        "candidate_action_set": ["continue_to_attested_disposable_replay", "stop_fail_closed"],
        "chosen_action": "stop_fail_closed",
        "state_delta": {"status": "not_executed", "before_tree": None, "after_tree": None, "changed_paths": []},
        "stop_continue": {"decision": "stop", "reason": "preflight_not_complete"},
        "protected_content_used": False, "forbidden_fields_read": [], **ZERO,
    }


def build(
    ready_rows: list[dict[str, Any]], trajectory_rows: list[dict[str, Any]], task_rows: list[dict[str, Any]],
    task_parquet: Path, expected_task_sha: str, execute_instance: str | None = None,
    private_root: Path = PRIVATE, timeout: int = 120, attestation: dict[str, Any] | None = None,
    *, commitment_path: Path = ATOMIC_COMMITMENT, lineage_state_path: Path = LINEAGE_STATE,
    source_adapter_path: Path = SOURCE_ADAPTER,
) -> dict[str, Any]:
    """Public replay boundary: deny before verifier-bearing or patch reads unless every guard passes."""
    pairs, blockers = _identity_pairs(ready_rows, task_rows, trajectory_rows)
    try:
        commitment = read_json(commitment_path)
        blockers.extend(_commitment_blockers(commitment, pairs, commitment_path))
    except (OSError, ValueError, json.JSONDecodeError):
        blockers.append("stage12565_atomic_commitment_missing_or_invalid")
    try:
        source_adapter = read_json(source_adapter_path)
        blockers.extend(_source_adapter_blockers(source_adapter, pairs, source_adapter_path))
    except (OSError, ValueError, json.JSONDecodeError):
        for pair in pairs:
            pair["source_ids"] = []
        blockers.append("stage12568_adapter_missing_or_invalid")
    try:
        lineage_state = read_json(lineage_state_path)
        blockers.extend(_lineage_state_blockers(lineage_state, lineage_state_path))
    except (OSError, ValueError, json.JSONDecodeError):
        blockers.append("stage12564_state_missing_or_invalid")
    try:
        lineage_blockers, decisions = _recursive_lineage_blockers(pairs)
        blockers.extend(lineage_blockers)
    except (OSError, ValueError, json.JSONDecodeError):
        decisions = []
        blockers.append("recursive_source_lineage_guard_unavailable")
    blockers = sorted(set(blockers))
    if blockers:
        return _denied_result(ready_rows, blockers, decisions)

    def parquet_rows(path: Path, columns: tuple[str, ...]) -> list[dict[str, Any]]:
        if NEVER_READ.intersection(columns):
            raise ValueError("prohibited column requested")
        import pyarrow.parquet as pq  # type: ignore
        parquet = pq.ParquetFile(path)
        missing = set(columns) - set(parquet.schema_arrow.names)
        if missing:
            raise ValueError(f"missing allowlisted columns: {sorted(missing)}")
        return parquet.read(columns=list(columns)).to_pylist()


    def exact_trajectory_patch(binding: dict[str, Any]) -> tuple[str | None, list[str]]:
        errors: list[str] = []
        path = source(binding, "trajectory_ordinal")
        ordinal = value(binding, "trajectory_ordinal")
        expected_shard = str(value(binding, "trajectory_shard_sha256") or "")
        if file_sha256(path) != expected_shard:
            return None, ["trajectory_shard_digest_mismatch_or_missing"]
        rows = parquet_rows(path, TRAJECTORY_COLUMNS)
        if not isinstance(ordinal, int) or isinstance(ordinal, bool) or not 0 <= ordinal < len(rows):
            return None, ["trajectory_ordinal_out_of_range"]
        row = rows[ordinal]
        checks = {
            "instance_id": (row.get("instance_id"), value(binding, "trajectory_instance_id")),
            "trajectory_id": (row.get("trajectory_id"), value(binding, "trajectory_id")),
            "canonical_repo": (canonical_repo(row.get("repo")), canonical_repo(value(binding, "canonical_repo"))),
        }
        errors.extend(f"trajectory_{name}_exact_join_mismatch" for name, pair in checks.items() if pair[0] != pair[1])
        patch = str(row.get("model_patch") or "")
        if digest_bytes(patch.encode()) != str(value(binding, "model_patch_sha256") or ""):
            errors.append("model_patch_digest_mismatch")
        return (patch if not errors else None), errors


    def task_authority_by_instance(path: Path, expected_sha: str) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
        if file_sha256(path) != expected_sha:
            return {}, ["task_snapshot_digest_mismatch_or_missing"]
        identity_rows = parquet_rows(path, TASK_IDENTITY_COLUMNS)
        verifier_rows = parquet_rows(path, TASK_VERIFIER_COLUMNS)
        return _join_task_projections(identity_rows, verifier_rows)

    def sensitive_after_guard(ready_rows: list[dict[str, Any]], trajectory_rows: list[dict[str, Any]], task_rows: list[dict[str, Any]],
              task_parquet: Path, expected_task_sha: str, execute_instance: str | None = None,
              private_root: Path = PRIVATE, timeout: int = 120, attestation: dict[str, Any] | None = None) -> dict[str, Any]:
        trajectories = {row.get("candidate_id"): row for row in trajectory_rows}
        tasks = {row.get("candidate_id"): row for row in task_rows}
        fixed: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]] = []
        records: list[dict[str, Any]] = []
        for ready in ready_rows:
            record = base_record(ready)
            trajectory, task = trajectories.get(ready.get("candidate_id")), tasks.get(ready.get("candidate_id"))
            errors = []
            if not trajectory or not task:
                errors.append("prior_exact_binding_missing")
            elif task.get("policy_split") != "train" or task.get("protected_from_training") is not False:
                errors.append("train_split_not_fixed")
            elif task.get("task_key") != ready.get("task_key"):
                errors.append("stage12555_stage12556_task_identity_mismatch")
            if errors:
                record["blocking_reasons"] = errors
                record["stop_continue"] = {"decision": "stop", "reason": errors[0]}
                records.append(record)
            else:
                fixed.append((ready, trajectory, task, record))

        # Verifier-bearing task columns are not touched until the split gate above is complete.
        task_index, source_errors = task_authority_by_instance(task_parquet, expected_task_sha) if fixed else ({}, ["no_train_rows"])
        for ready, trajectory, task, record in fixed:
            instance = str(task["task_identity"]["instance_id"])
            candidates = task_index.get(instance, [])
            errors = list(source_errors)
            if len(candidates) != 1:
                errors.append("authoritative_task_exact_identity_not_unique")
            authority = candidates[0] if len(candidates) == 1 else {}
            identity = task["task_identity"]
            if authority and (canonical_repo(authority.get("repo")) != canonical_repo(identity.get("canonical_repo")) or
                              str(authority.get("base_commit") or "").lower() != str(identity.get("base_commit") or "").lower()):
                errors.append("authoritative_task_exact_identity_mismatch")
            patch, patch_errors = exact_trajectory_patch(trajectory)
            errors.extend(patch_errors)
            config = authority.get("install_config") or {}
            command = str(config.get("test_cmd") or "")
            identifiers = authority.get("FAIL_TO_PASS") or []
            if not command or not isinstance(identifiers, list) or not identifiers:
                errors.append("verifier_contract_incomplete")
            record["join_proof"] = {"policy_split_fixed_before_task_verifier_read": True, "task_identity_join": "exact_instance_repo_base_commit",
                                    "trajectory_identity_join": "exact_ordinal_instance_repo_trajectory_id", "model_patch_sha256": value(trajectory, "model_patch_sha256")}
            record["verifier_contract"] = {"command": command, "command_sha256": digest_bytes(command.encode()),
                                           "fail_to_pass_identifiers": identifiers, "base_image_name": config.get("base_image_name"),
                                           "install_config_sha256": stable_hash(config)}
            record["patch_apply"] = {"status": "not_attempted", "engine": "git_apply", "fuzz_allowed": False, "fuzz_observed": False}
            if errors:
                record["blocking_reasons"] = sorted(set(errors))
                record["stop_continue"] = {"decision": "stop", "reason": sorted(set(errors))[0]}
            elif execute_instance == instance:
                record["blocking_reasons"] = [
                    "protected_universe_clearance_unadjudicated",
                    "untrusted_command_sandbox_not_implemented",
                    "network_and_secret_isolation_not_attested",
                    "fail_apply_pass_revert_fail_executor_not_implemented",
                    "environment_failure_classifier_not_implemented",
                    "independent_policy_action_label_not_materialized",
                ]
                record["stop_continue"] = {"decision": "stop", "reason": "execution_disabled_pending_safety_and_split_clearance"}
            else:
                record["chosen_action"] = "stop_fail_closed"
                record["stop_continue"] = {"decision": "stop", "reason": "environment_not_attested_execution_not_requested"}
            records.append(record)

        level3 = sum(bool(row["level3_credit"]) for row in records)
        summary = {
            "stage": STAGE, "record_type": "stage12557_private_train_replay_pilot_summary_v1",
            "input_ready_count": len(ready_rows), "train_split_fixed_count": len(fixed), "record_count": len(records),
            "preflight_exact_join_count": sum(not row.get("blocking_reasons") for row in records),
            "executed_count": sum("verifier_before" in row for row in records), "level3_count_increment": level3,
            "schema_placeholders_present": all(all(k in row for k in ("state_delta", "candidate_action_set", "chosen_action", "stop_continue")) for row in records),
            "causal_state_action_stop_complete_count": 0,
            "trajectory_columns_read": list(TRAJECTORY_COLUMNS), "task_columns_read_after_train_split_fixed": list(TASK_IDENTITY_COLUMNS + TASK_VERIFIER_COLUMNS),
            "forbidden_fields_read": [], "gold_or_reference_fields_read": False, "protected_rows_enumerated": False,
            "default_disposition": "fail_closed_preflight_only_without_attested_execution", **ZERO,
        }
        summary["level3_credit"] = level3 > 0
        return {"records": records, "summary": summary}

    result = sensitive_after_guard(
        ready_rows, trajectory_rows, task_rows, task_parquet, expected_task_sha,
        execute_instance, private_root, timeout, attestation,
    )
    result["summary"].update({
        "pre_read_guard_allowed": True,
        "pre_read_guard_denied_count": 0,
        "recursive_lineage_decisions": decisions,
        "task_identity_columns": list(TASK_IDENTITY_COLUMNS),
        "task_verifier_columns_read": list(TASK_VERIFIER_COLUMNS),
        "global_ingestion_coverage_claimed": False,
    })
    return result



def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ready", type=Path, default=READY)
    parser.add_argument("--trajectories", type=Path, default=TRAJECTORIES)
    parser.add_argument("--tasks", type=Path, default=TASKS)
    parser.add_argument("--task-parquet", type=Path, default=TASK_PARQUET)
    parser.add_argument("--expected-task-sha256", default=TASK_PARQUET_SHA256)
    parser.add_argument("--execute-instance")
    parser.add_argument("--environment-attestation", type=Path)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--output-dir", type=Path, default=OUT)
    parser.add_argument("--private-dir", type=Path, default=PRIVATE)
    parser.add_argument("--summary", type=Path, default=SUMMARY)
    args = parser.parse_args()
    attestation = json.loads(args.environment_attestation.read_text()) if args.environment_attestation else None
    ready_rows = read_jsonl(args.ready)
    ready_ids = {str(row.get("candidate_id") or "") for row in ready_rows}
    trajectory_rows = [row for row in read_jsonl(args.trajectories) if str(row.get("candidate_id") or "") in ready_ids]
    task_rows = [row for row in read_jsonl(args.tasks) if str(row.get("candidate_id") or "") in ready_ids]
    result = build(ready_rows, trajectory_rows, task_rows, args.task_parquet,
                   args.expected_task_sha256, args.execute_instance, args.private_dir, args.timeout, attestation)
    write_jsonl(args.output_dir / "replay_pilot_records.jsonl", result["records"])
    write_json(args.output_dir / "summary.json", result["summary"])
    write_json(args.summary, result["summary"])
    write_json(args.private_dir / "preflight_manifest.json", {"stage": STAGE, "record_count": len(result["records"]), "private_patch_material_persisted": False})
    print(json.dumps(result["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
