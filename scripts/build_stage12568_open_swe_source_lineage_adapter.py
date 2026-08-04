#!/usr/bin/env python3
"""Build a hash-bound Open-SWE evidence-to-canonical-source adapter."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12568_open_swe_source_lineage_adapter"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
REGISTRY = ROOT / "configs/software_maintainer/source_inventory_lineage_registry_stage8663.json"
TRAJECTORIES = ROOT / "runs/local/artifacts/stage12554_authority_inventory_and_overlap_gate/resolved_authority_fields.jsonl"
TASKS = ROOT / "runs/local/artifacts/stage12555_swe_rebench_identity_adapter/exact_task_authority_bindings.jsonl"
READY = ROOT / "runs/local/artifacts/stage12556_local_checkout_readiness_census/checkout_object_ready.jsonl"
COMMITMENT = ROOT / "runs/local/artifacts/stage12565_paired_pre_outcome_candidate_commitment_v2/paired_candidate_commitment_v2.json"
STAGE12564 = ROOT / "runs/local/artifacts/stage12564_authoritative_protected_lineage_preflight/authoritative_protected_lineage_preflight.json"
OPEN_SWE_REF = Path("/data/.cache/huggingface/hub/datasets--nvidia--Open-SWE-Traces/refs/main")
OPEN_SWE_ROOT = Path("/arxiv/datasets/nvidia--Open-SWE-Traces")
OPEN_SWE_DATASET = "nvidia/Open-SWE-Traces"
CANONICAL_SOURCE_ID = "src_53e6cea43bf6fbb6"
PINNED_REGISTRY_SHA256 = "98b50df0083fea7be08ccf513b361e78669a2d1be03db7948a2f0a3a90bab807"
PINNED_OPEN_SWE_REVISION = "f6689f56f1af2e2082861738071d4c4278b1922a"
PINNED_SHARD_SHA256 = "5befb7356a4bce7c13bc5a8313fdd42df0488c567eeaf42a668dcf307642320e"
PINNED_SHARD_PATH = OPEN_SWE_ROOT / "data/minimax_m25_openhands_trajectories/train-00000-of-00020.parquet"
PINNED_STAGE12554_SHA256 = "98a7f396868d2c7672129c71b7a0c7d62337ee389bdde8e0e37de153ef76dcbd"
PINNED_COMMITMENT_ARTIFACT_SHA256 = "f90d9a972f4e2029c97344f8ed17fa9d2f1ce8f143651901f7d21a4d3bd53e1a"
PINNED_COMMITMENT_SHA256 = "d9ae7fcc9865f811cf3355d8f3f9e597ad930f4d2184939e3a4d53ccf6c97e71"
PINNED_STAGE12564_SHA256 = "c9e95cbab0eac344e8be5e595067114ef380730fb17baa627c1868451d99aede"
DIGEST = re.compile(r"^[0-9a-f]{64}\Z")
REVISION = re.compile(r"^[0-9a-f]{40}\Z")
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
AUTHORITY_NAMES = {
    "stage12554_resolved_trajectory_bindings": TRAJECTORIES,
    "stage12555_exact_authority_bindings": TASKS,
    "stage12556_ready_rows": READY,
    "stage12565_paired_commitment": COMMITMENT,
}

_STAGE12565_SPEC = importlib.util.spec_from_file_location(
    "stage12565_contract_for_stage12568",
    ROOT / "scripts/build_stage12565_paired_pre_outcome_candidate_commitment_v2.py",
)
if not _STAGE12565_SPEC or not _STAGE12565_SPEC.loader:
    raise ImportError("Stage12565 commitment verifier unavailable")
STAGE12565 = importlib.util.module_from_spec(_STAGE12565_SPEC)
_STAGE12565_SPEC.loader.exec_module(STAGE12565)
SHARD_FIELDS = (
    "canonical_repo",
    "model_patch_sha256",
    "source_row_sha256",
    "trajectory_id",
    "trajectory_instance_id",
    "trajectory_ordinal",
)


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


def _field(row: dict[str, Any], name: str) -> dict[str, Any]:
    fields = row.get("resolved_fields")
    item = fields.get(name) if isinstance(fields, dict) else None
    return item if isinstance(item, dict) else {}


def _duplicates(values: list[str]) -> bool:
    return any(not value for value in values) or len(values) != len(set(values))


def _canonical_record(registry: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    records = registry.get("records")
    if not isinstance(records, list):
        return None, ["base_registry_records_missing"]
    ids = [str(row.get("source_id") or "") for row in records if isinstance(row, dict)]
    blockers: list[str] = []
    if _duplicates(ids):
        blockers.append("duplicate_or_conflicting_source_id")
    matching = [
        row for row in records
        if isinstance(row, dict) and row.get("path") == str(OPEN_SWE_ROOT)
    ]
    if len(matching) != 1:
        blockers.append("canonical_open_swe_registry_record_not_unique")
        return None, blockers
    record = matching[0]
    source_id = record.get("source_id")
    if not isinstance(source_id, str) or not source_id.startswith("src_"):
        blockers.append("canonical_open_swe_source_id_invalid")
    if record.get("locked_eval") is not False or record.get("hidden_final") is not False:
        blockers.append("canonical_open_swe_source_protected")
    return record, blockers


def _validate_commitment(
    commitment: dict[str, Any],
    commitment_path: Path,
    authority_hashes: dict[str, str | None],
    ready_rows: list[dict[str, Any]],
    task_rows: list[dict[str, Any]],
) -> list[str]:
    blockers = [f"stage12565_{reason}" for reason in STAGE12565.verify_envelope(commitment)]
    if file_sha256(commitment_path) != PINNED_COMMITMENT_ARTIFACT_SHA256:
        blockers.append("stage12565_artifact_hash_mismatch")
    if commitment.get("commitment_sha256") != PINNED_COMMITMENT_SHA256:
        blockers.append("stage12565_commitment_hash_mismatch")

    records = commitment.get("atomic_records") if isinstance(commitment.get("atomic_records"), list) else []
    ready_ids = [str(row.get("candidate_id") or "") for row in ready_rows]
    task_ids = [str(row.get("candidate_id") or "") for row in task_rows]
    atomic_ids = [str(row.get("candidate_id") or "") for row in records if isinstance(row, dict)]
    if not (len(ready_rows) == len(task_rows) == len(records) == 8):
        blockers.append("candidate_task_atomic_count_not_exactly_eight")
    if _duplicates(ready_ids) or _duplicates(task_ids) or _duplicates(atomic_ids):
        blockers.append("candidate_task_atomic_id_missing_or_duplicate")
    if set(ready_ids) != set(task_ids) or set(ready_ids) != set(atomic_ids):
        blockers.append("candidate_task_atomic_set_mismatch")

    actual_sources = {
        "stage12555_exact_authority_bindings": authority_hashes.get("stage12555_exact_authority_bindings"),
        "stage12556_ready_rows": authority_hashes.get("stage12556_ready_rows"),
    }
    by_task = {str(row.get("candidate_id") or ""): row for row in task_rows}
    by_atomic = {str(row.get("candidate_id") or ""): row for row in records if isinstance(row, dict)}
    for ready in ready_rows:
        candidate_id = str(ready.get("candidate_id") or "")
        task = by_task.get(candidate_id)
        atomic = by_atomic.get(candidate_id)
        if task is None or atomic is None:
            continue
        identity = task.get("task_identity") if isinstance(task.get("task_identity"), dict) else {}
        expected_rows = {
            "stage12555_exact_authority_binding": STAGE12565.stable_hash(STAGE12565.authority_row_projection(task)),
            "stage12556_ready_row": STAGE12565.stable_hash(STAGE12565.ready_row_projection(ready)),
        }
        exact = (
            atomic.get("task_key") == ready.get("task_key") == task.get("task_key")
            and atomic.get("canonical_repo") == identity.get("canonical_repo")
            and atomic.get("base_commit") == identity.get("base_commit")
            and atomic.get("instance_id") == identity.get("instance_id")
            and atomic.get("policy_split") == task.get("policy_split") == "train"
            and task.get("protected_from_training") is False
            and atomic.get("task_identity_sha256") == task.get("task_identity_sha256")
            and task.get("task_identity_sha256") == STAGE12565.stable_hash(identity)
            and atomic.get("task_snapshot_sha256") == task.get("task_snapshot_sha256")
            and atomic.get("source_artifact_sha256") == actual_sources
            and atomic.get("source_row_sha256") == expected_rows
            and atomic.get("selected_model") == STAGE12565.EXPECTED_MODEL
        )
        if not exact:
            blockers.append("stage12565_exact_atomic_projection_mismatch")
    return sorted(set(blockers))


def build_adapter(
    trajectory_rows: list[dict[str, Any]],
    task_rows: list[dict[str, Any]],
    ready_rows: list[dict[str, Any]],
    *,
    authority_hashes: dict[str, str | None],
    registry_path: Path = REGISTRY,
    commitment_path: Path = COMMITMENT,
    stage12564_path: Path = STAGE12564,
    open_swe_revision: str,
    shard_hasher: Callable[[Path], str | None] = file_sha256,
) -> dict[str, Any]:
    """Build a reference mapping. This API intentionally accepts no clearance input."""
    blockers: list[str] = []
    clearance_blockers: list[str] = []

    registry_hash = file_sha256(registry_path)
    if registry_hash != PINNED_REGISTRY_SHA256:
        blockers.append("base_registry_hash_mismatch")
    try:
        registry = read_json(registry_path)
    except (OSError, ValueError, json.JSONDecodeError):
        registry = {}
        blockers.append("base_registry_missing_or_invalid")
    record, registry_blockers = _canonical_record(registry)
    blockers.extend(registry_blockers)
    if record and record.get("source_id") != CANONICAL_SOURCE_ID:
        blockers.append("canonical_open_swe_source_id_substituted")

    try:
        commitment = read_json(commitment_path)
    except (OSError, ValueError, json.JSONDecodeError):
        commitment = {}
        blockers.append("stage12565_commitment_missing_or_invalid")

    if set(authority_hashes) != set(AUTHORITY_NAMES) or any(
        not isinstance(value, str) or DIGEST.fullmatch(value) is None
        for value in authority_hashes.values()
    ):
        blockers.append("authoritative_artifact_hash_missing_or_invalid")
    else:
        current_hashes = {name: file_sha256(path) for name, path in AUTHORITY_NAMES.items()}
        if authority_hashes != current_hashes:
            blockers.append("authoritative_artifact_hash_stale")
    if authority_hashes.get("stage12554_resolved_trajectory_bindings") != PINNED_STAGE12554_SHA256:
        blockers.append("stage12554_trajectory_binding_artifact_hash_mismatch")
    blockers.extend(_validate_commitment(commitment, commitment_path, authority_hashes, ready_rows, task_rows))

    if open_swe_revision != PINNED_OPEN_SWE_REVISION:
        blockers.append("open_swe_revision_stale_or_substituted")
    ready_ids = [str(row.get("candidate_id") or "") for row in ready_rows]
    task_ids = [str(row.get("candidate_id") or "") for row in task_rows]
    trajectory_ids = [str(row.get("candidate_id") or "") for row in trajectory_rows]
    if not (len(ready_rows) == len(task_rows) == len(trajectory_rows) == 8):
        blockers.append("ready_task_trajectory_count_not_exactly_eight")
    if _duplicates(ready_ids):
        blockers.append("ready_candidate_id_missing_or_duplicate")
    if _duplicates(task_ids) or set(task_ids) != set(ready_ids):
        blockers.append("task_candidate_set_not_exactly_ready")
    if _duplicates(trajectory_ids) or set(trajectory_ids) != set(ready_ids):
        blockers.append("trajectory_candidate_set_not_exactly_ready")

    by_trajectory = {str(row.get("candidate_id") or ""): row for row in trajectory_rows}
    by_task = {str(row.get("candidate_id") or ""): row for row in task_rows}
    atomic_rows = commitment.get("atomic_records") if isinstance(commitment.get("atomic_records"), list) else []
    by_atomic = {str(row.get("candidate_id") or ""): row for row in atomic_rows if isinstance(row, dict)}
    bindings: list[dict[str, Any]] = []
    for candidate_id in sorted(set(ready_ids)):
        row = by_trajectory.get(candidate_id)
        if row is None:
            continue
        task = by_task.get(candidate_id) or {}
        atomic = by_atomic.get(candidate_id) or {}
        identity = task.get("task_identity") if isinstance(task.get("task_identity"), dict) else {}
        dataset = _field(row, "trajectory_dataset").get("value")
        revision = _field(row, "trajectory_revision").get("value")
        config = _field(row, "trajectory_config").get("value")
        split = _field(row, "trajectory_split").get("value")
        shard = _field(row, "trajectory_shard_id").get("value")
        shard_sha = _field(row, "trajectory_shard_sha256").get("value")
        ordinal = _field(row, "trajectory_ordinal").get("value")
        trajectory_id = _field(row, "trajectory_id").get("value")
        shard_path = OPEN_SWE_ROOT / "data" / f"{split}_{config}_trajectories" / str(shard)
        expected_key = [dataset, revision, config, split, shard, ordinal, trajectory_id]
        source_revisions = {
            item.get("source_revision")
            for item in (row.get("resolved_fields") or {}).values()
            if isinstance(item, dict) and item.get("source_revision") is not None
        }
        row_blockers: list[str] = []
        if dataset != OPEN_SWE_DATASET:
            row_blockers.append("trajectory_dataset_mismatch")
        if revision != PINNED_OPEN_SWE_REVISION or source_revisions != {PINNED_OPEN_SWE_REVISION}:
            row_blockers.append("trajectory_revision_stale_or_mismatched")
        if row.get("namespaced_trajectory_key") != expected_key:
            row_blockers.append("trajectory_namespaced_key_mismatch")
        if (_field(row, "trajectory_instance_id").get("value") != identity.get("instance_id")
                or identity.get("instance_id") != atomic.get("instance_id")):
            row_blockers.append("trajectory_task_atomic_instance_mismatch")
        if (_field(row, "canonical_repo").get("value") != identity.get("canonical_repo")
                or identity.get("canonical_repo") != atomic.get("canonical_repo")):
            row_blockers.append("trajectory_task_atomic_repo_mismatch")
        task_key = task.get("task_key") if isinstance(task.get("task_key"), list) else []
        if (_field(row, "upstream_task_dataset").get("value") != identity.get("dataset")
                or not task_key or task_key[0] != identity.get("dataset")):
            row_blockers.append("trajectory_upstream_task_dataset_mismatch")
        if shard_path != PINNED_SHARD_PATH or any(
            _field(row, name).get("source") != str(PINNED_SHARD_PATH) for name in SHARD_FIELDS
        ):
            row_blockers.append("trajectory_shard_path_unknown_or_mismatched")
        if shard_sha != PINNED_SHARD_SHA256:
            row_blockers.append("trajectory_shard_hash_unknown_or_mismatched")
        elif shard_hasher(PINNED_SHARD_PATH) != PINNED_SHARD_SHA256:
            row_blockers.append("trajectory_shard_stale_or_tampered")
        if row_blockers:
            blockers.extend(row_blockers)
            continue
        bindings.append({
            "record_type": "stage12568_open_swe_source_reference_v1",
            "candidate_id": candidate_id,
            "source_ids": [CANONICAL_SOURCE_ID],
            "source_known": True,
            "source_train_eligible": bool(record and record.get("train_eligible") is True),
            "evidence": {
                "namespaced_trajectory_key": expected_key,
                "trajectory_shard_path": str(PINNED_SHARD_PATH),
                "trajectory_shard_sha256": PINNED_SHARD_SHA256,
                "stage12554_row_sha256": stable_hash(row),
            },
            "provenance_refs": [f"{name}:sha256:{digest}" for name, digest in sorted(authority_hashes.items())],
            "authority_hashes": dict(sorted(authority_hashes.items())),
            **ZERO,
        })

    if len(bindings) != 8:
        blockers.append("not_exactly_eight_trajectory_references_bound")

    try:
        stage12564 = read_json(stage12564_path)
    except (OSError, ValueError, json.JSONDecodeError):
        stage12564 = {}
        clearance_blockers.append("stage12564_missing_or_invalid")
    if file_sha256(stage12564_path) != PINNED_STAGE12564_SHA256:
        clearance_blockers.append("stage12564_artifact_hash_stale")
    stage12564_reasons = stage12564.get("blocking_reasons")
    stage12564_reasons = stage12564_reasons if isinstance(stage12564_reasons, list) else []
    if (
        stage12564.get("record_type") != "stage12564_authoritative_protected_lineage_preflight_summary_v1"
        or stage12564.get("unresolved_protected_root_count") != 0
        or stage12564.get("protected_lineage_enforcement_authoritative") is not True
        or stage12564_reasons
    ):
        clearance_blockers.append("protected_legacy_lineage_unresolved")
    if any(stage12564.get(name) is not True for name in ("admission_allowed", "training_allowed", "replay_allowed")):
        clearance_blockers.append("stage12564_authorization_absent")
    clearance_blockers.append("stage12564_stage12557_attestation_dependency_cycle")

    blockers = sorted(set(blockers))
    clearance_blockers = sorted(set(clearance_blockers))
    mapping_valid = not blockers and record is not None and len(bindings) == 8
    result = {
        "stage": STAGE,
        "record_type": "stage12568_source_lineage_reference_adapter_v1",
        "base_registry_path": str(registry_path),
        "base_registry_sha256": registry_hash,
        "base_registry_mutated": False,
        "canonical_source_id": CANONICAL_SOURCE_ID,
        "canonical_source_path": str(OPEN_SWE_ROOT),
        "source_known": mapping_valid,
        "source_train_eligible": bool(mapping_valid and record and record.get("train_eligible") is True),
        "reference_mapping_valid": mapping_valid,
        "effective_train_eligible": False,
        "protected_clearance": False,
        "blocking_reasons": blockers,
        "clearance_blocking_reasons": clearance_blockers,
        "stage12564_current_blocking_reasons": stage12564_reasons,
        "stage12564_live_rebuild_report": "stage12562_to_stage12557_summary_binding_reported_stale_not_rebuilt_by_stage12568",
        "control_plane_blocker": "stage12564_stage12557_attestation_dependency_cycle",
        "authority_hashes": dict(sorted(authority_hashes.items())),
        "bindings": bindings if mapping_valid else [],
        "artifact_hashes_are_source_ids": False,
        "commitment_hashes_are_source_ids": False,
        "trajectory_hashes_are_source_ids": False,
        "caller_authorization_input_accepted": False,
        "model_patch_read": False,
        "verifier_output_read": False,
        **ZERO,
    }
    result["adapter_sha256"] = stable_hash({key: value for key, value in result.items() if key != "adapter_sha256"})
    return result

def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def main() -> int:
    authority_hashes = {name: file_sha256(path) for name, path in AUTHORITY_NAMES.items()}
    ready_rows = read_jsonl(READY)
    ready_ids = {str(row.get("candidate_id") or "") for row in ready_rows}
    trajectories = [row for row in read_jsonl(TRAJECTORIES) if str(row.get("candidate_id") or "") in ready_ids]
    tasks = [row for row in read_jsonl(TASKS) if str(row.get("candidate_id") or "") in ready_ids]
    revision = OPEN_SWE_REF.read_text(encoding="utf-8").strip() if OPEN_SWE_REF.is_file() else ""
    adapter = build_adapter(
        trajectories, tasks, ready_rows, authority_hashes=authority_hashes, open_swe_revision=revision,
    )
    write_json(OUT / "source_lineage_reference_adapter.json", adapter)
    write_jsonl(OUT / "trajectory_source_bindings.jsonl", adapter["bindings"])
    summary_keys = (
        "stage", "record_type", "canonical_source_id", "source_known", "source_train_eligible",
        "reference_mapping_valid", "effective_train_eligible", "protected_clearance",
        "blocking_reasons", "clearance_blocking_reasons", "stage12564_current_blocking_reasons",
        "stage12564_live_rebuild_report", "control_plane_blocker",
        "authority_hashes", "adapter_sha256", "base_registry_sha256", "base_registry_mutated",
        "artifact_hashes_are_source_ids", "commitment_hashes_are_source_ids",
        "trajectory_hashes_are_source_ids", "caller_authorization_input_accepted",
        "model_patch_read", "verifier_output_read",
    )
    summary = {key: adapter[key] for key in summary_keys}
    summary.update({"binding_count": len(adapter["bindings"]), **ZERO})
    write_json(OUT / "summary.json", summary)
    write_json(SUMMARY, summary)
    return 0 if adapter["reference_mapping_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
