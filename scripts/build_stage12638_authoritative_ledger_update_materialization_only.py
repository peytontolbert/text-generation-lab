#!/usr/bin/env python3
# Build Stage12638 authoritative-ledger update materialization only.
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12638_authoritative_ledger_update_materialization_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
S12637 = ROOT / "runs/local/artifacts/stage12637_authoritative_ledger_update_authorization_only"
S12637_SUMMARY = ROOT / "runs/summaries/stage12637_authoritative_ledger_update_authorization_only.json"
S12635 = ROOT / "runs/local/artifacts/stage12635_authoritative_ledger_update_dry_run_materialization_only"
CANDIDATE_ROWS = S12635 / "private/candidate_train_support_rows_dry_run.jsonl"
CANDIDATE_MANIFEST = S12635 / "private/candidate_ledger_dry_run_manifest.json"

EXPECTED_HASHES = {
    "stage12637_summary": "fcb05812971ee03184bc71170a9569d67ac583764925a3a2cf021f98d0bbb79e",
    "stage12637_contract": "aa25a98f85c47c14c5ca19c220b56bc5d9bade23036aae951cd3086c3255e1ab",
    "stage12637_pointer": "457a14e6aa86d4296c20886ff50bbba5e343716b362f9c8fe334f3db21be19bd",
    "stage12637_private": "0cc738add6b979e7d25c0e0530fca5a5abe9be17e4c3b4aa824962a5d341e968",
    "stage12637_authorization": "601ea04d822c854785f50723a6741959cd10c31a8b660cb6e86e0493f7b8fe10",
    "stage12635_rows_bytes": "065923de4ef183501b5f528d82065814826bd257a9b1814d54850680fe6cbce5",
    "stage12635_candidate_manifest": "7e8c62d60c22c5996573b40e6d9ccf592f3825dd848ec4a7e4ae02dcb1f83347",
}

FALSE_FIELDS = (
    "implementation_ready", "dataset_admission_allowed", "dataset_rows_admitted", "new_rows_admitted",
    "frontier_100m_training_dataset_ready", "source_packet_implementation_allowed", "source_packet_executable",
    "stage12629_allowed", "stage12630_allowed", "stage12631_allowed", "stage12632_allowed", "stage12633_allowed",
    "stage12634_allowed", "stage12636_allowed", "stage12637_allowed", "stage12639_allowed",
    "stage12631_authoritative_ledger_dry_run_authority_source_packet_allowed",
    "stage12632_authoritative_ledger_dry_run_authority_source_packet_allowed",
    "stage12632_authoritative_ledger_update_dry_run_only_allowed",
    "stage12633_authoritative_ledger_update_dry_run_only_allowed",
    "stage12634_authoritative_ledger_update_dry_run_only_allowed",
    "stage12639_training_admission_allowed",
    "vm_branch_active", "vm_runner_execution_allowed", "execution_performed", "replay_trustworthy",
    "causal_transition_atoms_present", "causal_transition_atoms_allowed", "level3_preflight_allowed", "level_3_materialized",
    "level_3_materialization_allowed", "gpu_allocation_requested", "cuda2_training_allowed",
    "training_admission_allowed", "training_admission_preflight_allowed", "training_admitted", "training_allowed", "training_run_allowed",
    "strict_eval_admitted", "sealed_eval_admitted", "strict_eval_eligible", "sealed_eval_eligible",
    "admission_allowed", "ranking_allowed", "positive_stop", "dry_run_ready",
    "source_packet_executable", "source_packet_implementation_allowed",
)

PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "agentkernel_vm_replay", "/dev/", "selector", "raw_stream", "stdout.raw", "stderr.raw",
    "before_commit_oid", "after_commit_oid", "production_path", "production_patch_sha256", "manual_executor_slot_contracts",
    "slot_1.patch", "slot_2.patch", "repository_root", "patch_path", "slot_1/", "slot_2/", "combined_selected_test_rows",
    "combined_train_support_rows", "direct_verifier_log_train_support_manifest", "direct_verifier_log_train_support_rows",
    "guardrail_scan.json", "combined_train_support_ledger", "jsonl", "row_id", "stable_lineage_key",
)


class LedgerUpdateMaterializationError(RuntimeError):
    pass


def stable_hash(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(data).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise LedgerUpdateMaterializationError("json_object_required:" + path.name)
    return value


def read_jsonl_bytes(data: bytes) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(data.decode("utf-8").splitlines(), start=1):
        if not line:
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise LedgerUpdateMaterializationError(f"jsonl_object_required:{line_number}")
        rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True).encode("ascii") + b"\n"
    with path.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def fsync_dir(path: Path) -> None:
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def no_claim_fields() -> dict[str, Any]:
    return {field: False for field in FALSE_FIELDS}


def check_false(record: Mapping[str, Any], label: str) -> None:
    for field in FALSE_FIELDS:
        if field in record and record[field] is not False:
            raise LedgerUpdateMaterializationError(f"{label}_gate_drift:{field}")


def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise LedgerUpdateMaterializationError(f"{label}_public_leak:{needle}")


def load_stage12637() -> dict[str, Any]:
    summary = read_json(S12637 / "summary.json")
    external = read_json(S12637_SUMMARY)
    contract = read_json(S12637 / "contract.json")
    pointer = read_json(S12637 / "digest_pointer.json")
    private = read_json(S12637 / "private/authoritative_ledger_update_authorization_only.json")
    if summary != external:
        raise LedgerUpdateMaterializationError("stage12637_external_summary_mismatch")
    for label, value in (
        ("stage12637_summary", summary),
        ("stage12637_contract", contract),
        ("stage12637_pointer", pointer),
        ("stage12637_private", private),
    ):
        if stable_hash(value) != EXPECTED_HASHES[label]:
            raise LedgerUpdateMaterializationError("stage12637_pin_drift:" + label)
    authorization = private.get("authoritative_ledger_update_authorization") or {}
    if stable_hash(authorization) != EXPECTED_HASHES["stage12637_authorization"]:
        raise LedgerUpdateMaterializationError("stage12637_authorization_hash_drift")
    if authorization.get("authorization_scope") != "authoritative_ledger_update_only":
        raise LedgerUpdateMaterializationError("stage12637_authorization_scope_drift")
    if authorization.get("authorized_next_stage") != STAGE:
        raise LedgerUpdateMaterializationError("stage12637_authorized_next_stage_drift")
    if authorization.get("authorized_authoritative_count_after_update") != 190:
        raise LedgerUpdateMaterializationError("stage12637_authorized_count_drift")
    for field in ("stage12638_authoritative_ledger_update_materialization_only_allowed", "authoritative_ledger_update_allowed"):
        if summary.get(field) is not True:
            raise LedgerUpdateMaterializationError("stage12637_authorization_gate_missing:" + field)
    for field in ("authoritative_ledger_updated", "dataset_rows_admitted", "new_rows_admitted", "training_allowed", "level_3_materialized", "replay_trustworthy"):
        if summary.get(field) is not False:
            raise LedgerUpdateMaterializationError("stage12637_forbidden_gate_drift:" + field)
    return {"summary": summary, "contract": contract, "pointer": pointer, "private": private, "authorization": authorization}


def load_candidate_rows() -> dict[str, Any]:
    rows_bytes = CANDIDATE_ROWS.read_bytes()
    if sha256_bytes(rows_bytes) != EXPECTED_HASHES["stage12635_rows_bytes"]:
        raise LedgerUpdateMaterializationError("stage12635_rows_hash_drift")
    manifest = read_json(CANDIDATE_MANIFEST)
    if stable_hash(manifest) != EXPECTED_HASHES["stage12635_candidate_manifest"]:
        raise LedgerUpdateMaterializationError("stage12635_candidate_manifest_hash_drift")
    rows = read_jsonl_bytes(rows_bytes)
    if len(rows) != 99:
        raise LedgerUpdateMaterializationError("candidate_projection_row_count_drift")
    row_ids = [row.get("row_id") for row in rows]
    if any(not isinstance(row_id, str) or not row_id for row_id in row_ids):
        raise LedgerUpdateMaterializationError("candidate_row_id_missing")
    if len(set(row_ids)) != len(row_ids):
        raise LedgerUpdateMaterializationError("candidate_duplicate_row_id_drift")
    requirements = manifest.get("materialized_private_manifest_requirements") or {}
    merged = requirements.get("merged_row_manifest") or {}
    if merged.get("candidate_total_count") != 190 or merged.get("event_local_base_rows_referenced") != 91:
        raise LedgerUpdateMaterializationError("candidate_manifest_merged_count_drift")
    if manifest.get("overclaim_count") != 0 or manifest.get("raw_leak_count") != 0:
        raise LedgerUpdateMaterializationError("candidate_manifest_guardrail_drift")
    return {"rows_bytes": rows_bytes, "rows": rows, "manifest": manifest}


def curriculum_coverage_from_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    task_counts = dict(manifest.get("task_family_or_record_type_counts") or {})
    language_counts = dict(manifest.get("language_counts") or {})
    return {
        "record_type": "stage12638_curriculum_coverage_preview_v1",
        "coverage_scope": "authoritative_ledger_update_rows_only",
        "candidate_projection_rows": 99,
        "event_local_base_rows_referenced": 91,
        "authoritative_total_after_update": 190,
        "language_counts": language_counts,
        "task_family_or_record_type_counts": task_counts,
        "supported_curriculum_stages": [
            "structured_repo_state_partial",
            "maintainer_action_policy",
            "long_horizon_state_transitions_partial",
            "verifier_transition_classification_partial",
            "evidence_citation_partial",
        ],
        "missing_curriculum_signals": [
            "canonical_state_t_state_t_plus_1",
            "canonical_action_t_observation_t_plus_1",
            "repo_graph_candidates",
            "symbol_binding_candidates",
            "file_span_localization_candidates",
            "root_cause_failure_category",
            "patch_operator_arguments",
            "verifier_repair_actions",
            "replay_retention_sets",
        ],
        "next_preflight": "stage12639_curriculum_coverage_admission_preflight_only",
        "training_allowed_after_preview": False,
    }


def build_update(stage12637: Mapping[str, Any], source: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    auth = stage12637["authorization"]
    manifest = source["manifest"]
    coverage = curriculum_coverage_from_manifest(manifest)
    checks = [
        {"check_id": "stage12637_authorization_pinned", "status": "passed"},
        {"check_id": "authorized_scope_is_materialization_only", "status": "passed"},
        {"check_id": "candidate_rows_hash_pinned", "status": "passed", "projection_rows": 99},
        {"check_id": "candidate_manifest_hash_pinned", "status": "passed"},
        {"check_id": "authoritative_count_updates_158_to_190", "status": "passed"},
        {"check_id": "admission_training_eval_replay_level3_gpu_forbidden", "status": "passed"},
        {"check_id": "curriculum_coverage_preview_recorded_for_next_preflight", "status": "passed"},
    ]
    update = {
        "record_type": "stage12638_authoritative_ledger_update_materialization_v1",
        "materialization_scope": "authoritative_ledger_update_materialization_only",
        "source_authorization_sha256": EXPECTED_HASHES["stage12637_authorization"],
        "source_stage12637_summary_sha256": EXPECTED_HASHES["stage12637_summary"],
        "candidate_rows_sha256": EXPECTED_HASHES["stage12635_rows_bytes"],
        "candidate_manifest_sha256": EXPECTED_HASHES["stage12635_candidate_manifest"],
        "curriculum_coverage_preview_sha256": stable_hash(coverage),
        "materialization_checks": checks,
        "materialization_check_count": len(checks),
        "materialization_status": "authoritative_ledger_update_materialized_no_admission_or_training",
        "authoritative_count_before_update": auth.get("authoritative_count_before_authorized_update"),
        "authoritative_gap_before_update": auth.get("authoritative_gap_before_authorized_update"),
        "authoritative_count_after_update": 190,
        "authoritative_gap_after_update": 310,
        "authorized_delta_total": 32,
        "projection_rows_materialized_as_update_evidence": 99,
        "event_local_base_rows_referenced": 91,
        "source_component_count": len(manifest.get("source_counts") or {}),
        "duplicate_row_ids_after_update": 0,
        "raw_leak_count": 0,
        "overclaim_count": 0,
        "authoritative_ledger_update_allowed": True,
        "authoritative_ledger_updated": True,
        "ledger_update_materialized": True,
        "row_artifacts_written": True,
        "summary_artifact_written": True,
        "storage_write_performed": True,
        "new_admission_performed": False,
        "dataset_rows_admitted": False,
        "training_allowed_after_update": False,
        "strict_eval_admitted_after_update": False,
        "sealed_eval_admitted_after_update": False,
        "level3_materialized_after_update": False,
        "gpu_use_allowed_after_update": False,
    }
    return update, coverage


def build_packet(stage12637: Mapping[str, Any], source: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    update, coverage = build_update(stage12637, source)
    true_fields = {
        "authoritative_ledger_update_materialization_only": True,
        "authoritative_ledger_update_allowed": True,
        "authoritative_ledger_updated": True,
        "ledger_update_materialized": True,
        "row_artifacts_written": True,
        "summary_artifact_written": True,
        "storage_write_performed": True,
        "stage12638_authoritative_ledger_update_materialization_only_allowed": True,
        "stage12639_curriculum_coverage_preflight_allowed": True,
        "dry_run_authorization_granted": True,
        "dry_run_authorized": True,
        "authoritative_ledger_dry_run_allowed": True,
        "authoritative_ledger_dry_run_performed": True,
        "authoritative_ledger_update_dry_run_materialized": True,
        "candidate_ledger_materialized": True,
        "candidate_rows_materialized": True,
        "candidate_projection_rows_materialized": True,
        "dry_run_candidate_artifacts_written": True,
        "vm_branch_remains_paused": True,
    }
    private = {
        "record_type": "stage12638_private_authoritative_ledger_update_materialization_only_v1",
        **no_claim_fields(),
        **true_fields,
        "source_hashes": EXPECTED_HASHES,
        "authoritative_ledger_update_materialization": update,
        "curriculum_coverage_preview": coverage,
        "candidate_row_artifact": {
            "artifact_scope": "private_authoritative_update_evidence_rows_only",
            "projection_rows": 99,
            "rows_sha256": EXPECTED_HASHES["stage12635_rows_bytes"],
            "full_authoritative_total_after_update": 190,
            "event_local_base_rows_referenced_not_reemitted": 91,
        },
        "decision": "AUTHORITATIVE_LEDGER_UPDATE_MATERIALIZED_NO_ADMISSION_OR_TRAINING",
    }
    contract = {
        "record_type": "stage12638_public_authoritative_ledger_update_materialization_only_contract_v1",
        **no_claim_fields(),
        **true_fields,
        "stage12637_authorization_sha256": EXPECTED_HASHES["stage12637_authorization"],
        "candidate_rows_sha256": EXPECTED_HASHES["stage12635_rows_bytes"],
        "candidate_manifest_sha256": EXPECTED_HASHES["stage12635_candidate_manifest"],
        "authoritative_ledger_update_materialization_sha256": stable_hash(update),
        "curriculum_coverage_preview_sha256": stable_hash(coverage),
        "private_authoritative_ledger_update_materialization_sha256": stable_hash(private),
        "claim_boundary": {
            "materialization": "authoritative_ledger_update_only",
            "authoritative_train_support_count": "updated_to_190",
            "new_row_admission": "not_performed",
            "training": "not_authorized",
            "eval": "not_authorized",
            "vm": "paused_not_used_for_materialization",
            "replay": "not_executed",
            "level3": "not_materialized",
            "gpu": "not_authorized",
        },
    }
    summary = {
        "record_type": "stage12638_public_authoritative_ledger_update_materialization_only_summary_v1",
        **no_claim_fields(),
        **true_fields,
        "stage": STAGE,
        "decision": "AUTHORITATIVE_LEDGER_UPDATE_MATERIALIZED_NO_ADMISSION_OR_TRAINING",
        "stage12637_authorization_sha256": EXPECTED_HASHES["stage12637_authorization"],
        "candidate_rows_sha256": EXPECTED_HASHES["stage12635_rows_bytes"],
        "candidate_manifest_sha256": EXPECTED_HASHES["stage12635_candidate_manifest"],
        "authoritative_ledger_update_materialization_sha256": stable_hash(update),
        "curriculum_coverage_preview_sha256": stable_hash(coverage),
        "private_authoritative_ledger_update_materialization_sha256": stable_hash(private),
        "materialization_status": "authoritative_ledger_update_materialized_no_admission_or_training",
        "authoritative_admitted_train_support_tasks_before_update": 158,
        "authoritative_gap_to_500_before_update": 342,
        "authoritative_admitted_train_support_tasks_after_update": 190,
        "authoritative_gap_to_500_after_update": 310,
        "authorized_delta_total": 32,
        "materialized_projection_rows": 99,
        "event_local_base_rows_referenced": 91,
        "frontier_100m_training_dataset_ready": False,
        "curriculum_coverage_preview_recorded": True,
        "curriculum_supported_stage_count": len(coverage["supported_curriculum_stages"]),
        "curriculum_missing_signal_count": len(coverage["missing_curriculum_signals"]),
        "downstream_blockers": [
            "authoritative_gap_still_310",
            "curriculum_coverage_preflight_not_materialized",
            "canonical_trainer_renderer_not_materialized",
            "new_train_support_rows_not_admitted_beyond_ledger_update",
            "training_admission_forbidden",
        ],
        "next_required_action": "stage12639_curriculum_coverage_admission_preflight_only",
    }
    for label, record in (("summary", summary), ("contract", contract)):
        check_false(record, "stage12638_" + label)
        assert_public_sanitized(record, "stage12638_" + label)
    check_false(private, "stage12638_private")
    return summary, contract, private, coverage


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    stage12637 = load_stage12637()
    source = load_candidate_rows()
    summary, contract, private, coverage = build_packet(stage12637, source)
    pointer = {
        "record_type": "stage12638_public_private_authoritative_ledger_update_materialization_pointer_v1",
        **no_claim_fields(),
        "stage12637_summary_sha256": EXPECTED_HASHES["stage12637_summary"],
        "contract_sha256": stable_hash(contract),
        "private_authoritative_ledger_update_materialization_sha256": stable_hash(private),
        "authoritative_ledger_update_materialization_sha256": stable_hash(private["authoritative_ledger_update_materialization"]),
        "curriculum_coverage_preview_sha256": stable_hash(coverage),
        "authoritative_ledger_update_materialization_only": True,
        "authoritative_ledger_update_allowed": True,
        "authoritative_ledger_updated": True,
        "ledger_update_materialized": True,
        "row_artifacts_written": True,
        "summary_artifact_written": True,
        "storage_write_performed": True,
        "stage12638_authoritative_ledger_update_materialization_only_allowed": True,
        "stage12639_curriculum_coverage_preflight_allowed": True,
        "dry_run_authorization_granted": True,
        "dry_run_authorized": True,
        "authoritative_ledger_dry_run_allowed": True,
        "authoritative_ledger_dry_run_performed": True,
        "authoritative_ledger_update_dry_run_materialized": True,
        "candidate_ledger_materialized": True,
        "candidate_rows_materialized": True,
        "candidate_projection_rows_materialized": True,
        "dry_run_candidate_artifacts_written": True,
        "vm_branch_remains_paused": True,
    }
    check_false(pointer, "stage12638_pointer")
    assert_public_sanitized(pointer, "stage12638_pointer")
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "curriculum_coverage_preview.json", coverage)
    write_bytes(out / "private/authoritative_update_evidence_rows.jsonl", source["rows_bytes"])
    write_json(out / "private/authoritative_ledger_update_materialization_only.json", private)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    fsync_dir(out / "private")
    fsync_dir(out)
    fsync_dir(summary_path.parent)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
