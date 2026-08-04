#!/usr/bin/env python3
# Build Stage12635 candidate-ledger dry-run materialization only.
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12635_authoritative_ledger_update_dry_run_materialization_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
S12634 = ROOT / "runs/local/artifacts/stage12634_authoritative_ledger_dry_run_authorization_only"
S12634_SUMMARY = ROOT / "runs/summaries/stage12634_authoritative_ledger_dry_run_authorization_only.json"
STAGE12417 = ROOT / "runs/local/artifacts/stage12417_combined_train_support_ledger_v16"
SOURCE_ROWS = STAGE12417 / "combined_train_support_rows_v16.jsonl"
SOURCE_LEDGER = STAGE12417 / "combined_train_support_ledger_v16.json"
SOURCE_GUARDRAIL = STAGE12417 / "guardrail_scan.json"

EXPECTED_HASHES = {
    "stage12634_summary": "9889cb6c972c5a3d4fbe710aba2d11bf7ca813ec16ee3b0247ec5ca888ce0a62",
    "stage12634_contract": "8859f5b0665d76511cb8d85c926d85b73b03a279849b50e5300ebad8c383e64a",
    "stage12634_pointer": "86c02e7b78747b06d0d4bdff3c244dd165dfbc66fed6b810895db69e373c6ee6",
    "stage12634_private": "cbd0a3d7f313e3c112012241457d2d594bfa268bf02927d40b80b51c994b2d5f",
    "stage12634_authorization": "5736cc592b79db588df019a0b498a0abf1fbec8486ae1411ac5ee6457aafdcf4",
    "stage12417_ledger": "c9a872e36c12888b7f3fd45218cb69aa7d75b238378368289483ba54c483721a",
    "stage12417_rows_bytes": "065923de4ef183501b5f528d82065814826bd257a9b1814d54850680fe6cbce5",
    "stage12417_guardrail_bytes": "7f069101a9fa734c90fa23c93a562dc8de9eb4fc8cc78eb6f90676c504b5ce8c",
}

FALSE_FIELDS = (
    "implementation_ready", "dataset_admission_allowed", "dataset_rows_admitted", "new_rows_admitted",
    "frontier_100m_training_dataset_ready", "source_packet_implementation_allowed", "source_packet_executable",
    "stage12629_allowed", "stage12630_allowed", "stage12631_allowed", "stage12632_allowed", "stage12633_allowed",
    "stage12634_allowed", "stage12636_allowed",
    "stage12631_authoritative_ledger_dry_run_authority_source_packet_allowed",
    "stage12632_authoritative_ledger_dry_run_authority_source_packet_allowed",
    "stage12632_authoritative_ledger_update_dry_run_only_allowed",
    "stage12633_authoritative_ledger_update_dry_run_only_allowed",
    "stage12634_authoritative_ledger_update_dry_run_only_allowed",
    "stage12636_authoritative_ledger_update_allowed",
    "vm_branch_active", "vm_runner_execution_allowed", "execution_performed", "storage_write_performed", "replay_trustworthy",
    "causal_transition_atoms_present", "causal_transition_atoms_allowed", "level3_preflight_allowed", "level_3_materialized",
    "level_3_materialization_allowed", "gpu_allocation_requested", "cuda2_training_allowed",
    "training_admission_allowed", "training_admission_preflight_allowed", "training_admitted", "training_allowed", "training_run_allowed",
    "strict_eval_admitted", "sealed_eval_admitted", "strict_eval_eligible", "sealed_eval_eligible",
    "admission_allowed", "ranking_allowed", "positive_stop", "authoritative_ledger_updated",
    "authoritative_ledger_update_allowed", "row_artifacts_written", "summary_artifact_written",
    "ledger_update_materialized", "dry_run_ready",
)
PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "agentkernel_vm_replay", "/dev/", "selector", "raw_stream", "stdout.raw", "stderr.raw",
    "before_commit_oid", "after_commit_oid", "production_path", "production_patch_sha256", "manual_executor_slot_contracts",
    "slot_1.patch", "slot_2.patch", "repository_root", "patch_path", "slot_1/", "slot_2/", "combined_selected_test_rows",
    "combined_train_support_rows", "direct_verifier_log_train_support_manifest", "direct_verifier_log_train_support_rows",
    "guardrail_scan.json", "combined_train_support_ledger", "jsonl", "row_id", "stable_lineage_key",
)


class DryRunMaterializationError(RuntimeError):
    pass


def stable_hash(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(data).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise DryRunMaterializationError("json_object_required:" + path.name)
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line:
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise DryRunMaterializationError(f"jsonl_object_required:{path.name}:{line_number}")
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


def no_claim_fields() -> dict[str, Any]:
    return {field: False for field in FALSE_FIELDS}


def check_false(record: Mapping[str, Any], label: str) -> None:
    for field in FALSE_FIELDS:
        if field in record and record[field] is not False:
            raise DryRunMaterializationError(f"{label}_gate_drift:{field}")


def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise DryRunMaterializationError(f"{label}_public_leak:{needle}")


def load_authorization() -> dict[str, Any]:
    summary = read_json(S12634 / "summary.json")
    external = read_json(S12634_SUMMARY)
    contract = read_json(S12634 / "contract.json")
    pointer = read_json(S12634 / "digest_pointer.json")
    private = read_json(S12634 / "private/authoritative_ledger_dry_run_authorization_only.json")
    if summary != external:
        raise DryRunMaterializationError("stage12634_external_summary_mismatch")
    for label, value in (("stage12634_summary", summary), ("stage12634_contract", contract), ("stage12634_pointer", pointer), ("stage12634_private", private)):
        if stable_hash(value) != EXPECTED_HASHES[label]:
            raise DryRunMaterializationError("stage12634_pin_drift:" + label)
    authorization = private.get("dry_run_authorization") or {}
    if stable_hash(authorization) != EXPECTED_HASHES["stage12634_authorization"]:
        raise DryRunMaterializationError("stage12634_authorization_hash_drift")
    for field in ("dry_run_authorization_granted", "dry_run_authorized", "authoritative_ledger_dry_run_allowed", "stage12635_authoritative_ledger_update_dry_run_only_allowed"):
        if summary.get(field) is not True:
            raise DryRunMaterializationError("stage12634_authorization_gate_missing:" + field)
    for field in ("authoritative_ledger_dry_run_performed", "candidate_ledger_materialized", "candidate_rows_materialized", "authoritative_ledger_updated", "training_allowed"):
        if summary.get(field) is not False:
            raise DryRunMaterializationError("stage12634_prior_materialization_drift:" + field)
    return {"summary": summary, "private": private, "authorization": authorization}


def load_candidate_source() -> dict[str, Any]:
    rows_bytes = SOURCE_ROWS.read_bytes()
    if sha256_bytes(rows_bytes) != EXPECTED_HASHES["stage12417_rows_bytes"]:
        raise DryRunMaterializationError("stage12417_rows_hash_drift")
    ledger = read_json(SOURCE_LEDGER)
    guardrail_bytes = SOURCE_GUARDRAIL.read_bytes()
    guardrail = read_json(SOURCE_GUARDRAIL)
    rows = read_jsonl(SOURCE_ROWS)
    if stable_hash(ledger) != EXPECTED_HASHES["stage12417_ledger"]:
        raise DryRunMaterializationError("stage12417_ledger_hash_drift")
    if sha256_bytes(guardrail_bytes) != EXPECTED_HASHES["stage12417_guardrail_bytes"]:
        raise DryRunMaterializationError("stage12417_guardrail_hash_drift")
    if ledger.get("current_admitted_train_support_tasks") != 190 or ledger.get("remaining_gap_to_500") != 310:
        raise DryRunMaterializationError("stage12417_candidate_count_drift")
    if len(rows) != 99:
        raise DryRunMaterializationError("stage12417_projection_row_count_drift")
    row_ids = [row.get("row_id") for row in rows]
    if len(set(row_ids)) != len(row_ids):
        raise DryRunMaterializationError("stage12417_duplicate_row_id_drift")
    if ledger.get("guardrail_scan_passed") is not True or guardrail.get("scan_passed") is not True:
        raise DryRunMaterializationError("stage12417_guardrail_not_passed")
    for field in ("raw_leak_count", "overclaim_count", "strict_eval_eligible", "source_heldout_admissible", "repair_claim_admitted", "patch_trace_admitted", "level3_admitted"):
        if ledger.get(field) not in (0, False):
            raise DryRunMaterializationError("stage12417_risky_claim_drift:" + field)
    if ledger.get("training_allowed") is not False:
        raise DryRunMaterializationError("stage12417_training_gate_drift")
    return {"rows_bytes": rows_bytes, "rows": rows, "ledger": ledger, "guardrail": guardrail}


def build_public_diff(source: Mapping[str, Any]) -> dict[str, Any]:
    ledger = source["ledger"]
    return {
        "record_type": "stage12635_public_candidate_ledger_dry_run_summary_diff_v1",
        **no_claim_fields(),
        "diff_scope": "candidate_count_projection_only",
        "authoritative_count_before_dry_run": 158,
        "authoritative_gap_before_dry_run": 342,
        "candidate_count_after_dry_run": 190,
        "candidate_gap_after_dry_run": 310,
        "materialized_projection_rows": 99,
        "event_local_base_rows_referenced": 91,
        "candidate_delta_total": 32,
        "materialized_projection_rows": 99,
        "event_local_base_rows_referenced": 91,
        "selected_lineage_delta": 14,
        "direct_real_log_delta": 18,
        "source_component_count": len(ledger.get("source_counts") or {}),
        "guardrail_scan_passed": True,
        "training_allowed_after_dry_run": False,
        "authoritative_update_performed": False,
        "new_admission_performed": False,
    }


def build_private_manifest(source: Mapping[str, Any]) -> dict[str, Any]:
    rows = source["rows"]
    ledger = source["ledger"]
    return {
        "record_type": "stage12635_private_candidate_ledger_dry_run_manifest_v1",
        "manifest_scope": "candidate_ledger_dry_run_materialization_only",
        "candidate_projection_row_count": len(rows),
        "candidate_total_count_after_dry_run": 190,
        "candidate_gap_to_500": 310,
        "candidate_delta_total": 32,
        "candidate_rows_sha256": EXPECTED_HASHES["stage12417_rows_bytes"],
        "candidate_ledger_sha256": EXPECTED_HASHES["stage12417_ledger"],
        "candidate_guardrail_sha256": EXPECTED_HASHES["stage12417_guardrail_bytes"],
        "source_counts": ledger.get("source_counts"),
        "language_counts": ledger.get("language_counts"),
        "task_family_or_record_type_counts": ledger.get("task_family_or_record_type_counts"),
        "materialized_private_manifest_requirements": {
            "merged_row_manifest": {"projection_rows": 99, "event_local_base_rows_referenced": 91, "candidate_total_count": 190, "candidate_gap_to_500": 310},
            "supersession_manifest": {"source_transition": "stage12376_to_stage12385", "rows_before": 67, "rows_after": 81, "row_ids_added": 30, "row_ids_removed_or_superseded": 6, "prior_duplicate_extra_rows_removed": 10, "net_delta": 14},
            "direct_log_merge_manifest": {"source_transition": "stage12385_plus_stage12416_to_stage12417", "direct_log_projection_rows": 18, "net_delta": 18, "forbidden_claims_admitted": 0},
            "duplicate_policy_manifest": {"stage12385_prior_duplicate_rows_removed": 10, "post_update_duplicate_extra_rows_required": 0, "duplicate_row_ids_after_dry_run": 0},
            "guardrail_manifest": {"scan_passed": True, "raw_leak_count": 0, "overclaim_count": 0},
        },
        "duplicate_row_ids_should_be_zero": ledger.get("duplicate_row_ids_should_be_zero"),
        "raw_leak_count": ledger.get("raw_leak_count"),
        "overclaim_count": ledger.get("overclaim_count"),
        "training_allowed_after_dry_run": False,
        "authoritative_ledger_update_performed": False,
        "new_admission_performed": False,
            "candidate_projection_rows_materialized": True,
    }


def build_materialization(authorization: Mapping[str, Any], source: Mapping[str, Any]) -> dict[str, Any]:
    auth = authorization["authorization"]
    if auth.get("authorization_scope") != "candidate_ledger_dry_run_only":
        raise DryRunMaterializationError("stage12634_authorization_scope_drift")
    if auth.get("authorized_candidate_count") != 190 or auth.get("authorized_candidate_gap") != 310:
        raise DryRunMaterializationError("stage12634_authorized_count_drift")
    public_diff = build_public_diff(source)
    private_manifest = build_private_manifest(source)
    checks = [
        {"check_id": "stage12634_dry_run_authorization_pinned", "status": "passed"},
        {"check_id": "candidate_projection_rows_hash_pinned", "status": "passed", "projection_row_count": 99, "candidate_total_count": 190},
        {"check_id": "candidate_ledger_metadata_pinned", "status": "passed", "candidate_gap": 310},
        {"check_id": "candidate_guardrail_scan_passed", "status": "passed"},
        {"check_id": "candidate_artifacts_are_dry_run_only", "status": "passed"},
        {"check_id": "authoritative_update_admission_training_eval_replay_level3_forbidden", "status": "passed"},
    ]
    return {
        "record_type": "stage12635_authoritative_ledger_update_dry_run_materialization_v1",
        "materialization_scope": "candidate_ledger_dry_run_materialization_only",
        "source_authorization_sha256": EXPECTED_HASHES["stage12634_authorization"],
        "candidate_rows_sha256": EXPECTED_HASHES["stage12417_rows_bytes"],
        "candidate_ledger_sha256": EXPECTED_HASHES["stage12417_ledger"],
        "candidate_guardrail_sha256": EXPECTED_HASHES["stage12417_guardrail_bytes"],
        "public_summary_diff_sha256": stable_hash(public_diff),
        "private_candidate_manifest_sha256": stable_hash(private_manifest),
        "materialization_checks": checks,
        "materialization_check_count": len(checks),
        "materialization_status": "candidate_ledger_dry_run_materialized_no_authoritative_update_or_admission",
        "authoritative_count_after_dry_run": 158,
        "authoritative_gap_after_dry_run": 342,
        "candidate_count_after_dry_run": 190,
        "candidate_gap_after_dry_run": 310,
        "candidate_delta_total": 32,
        "candidate_artifacts_written": 3,
        "summary_artifacts_updated": 0,
        "dry_run_authorization_granted": True,
        "dry_run_authorized": True,
        "authoritative_ledger_dry_run_allowed": True,
        "stage12635_authoritative_ledger_update_dry_run_only_allowed": True,
        "authoritative_ledger_dry_run_performed": True,
        "authoritative_ledger_update_dry_run_materialized": True,
        "candidate_ledger_materialized": True,
        "candidate_rows_materialized": True,
        "dry_run_candidate_artifacts_written": True,
        "candidate_projection_rows_materialized": True,
        "authoritative_ledger_update_performed": False,
        "new_admission_performed": False,
        "training_allowed_after_dry_run": False,
    }, public_diff, private_manifest


def build_packet(authorization: Mapping[str, Any], source: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    materialization, public_diff, private_manifest = build_materialization(authorization, source)
    true_fields = {
        "dry_run_authorization_granted": True,
        "dry_run_authorized": True,
        "authoritative_ledger_dry_run_allowed": True,
        "stage12635_authoritative_ledger_update_dry_run_only_allowed": True,
        "authoritative_ledger_dry_run_performed": True,
        "authoritative_ledger_update_dry_run_materialized": True,
        "candidate_ledger_materialized": True,
        "candidate_rows_materialized": True,
        "dry_run_candidate_artifacts_written": True,
        "candidate_projection_rows_materialized": True,
        "vm_branch_remains_paused": True,
    }
    private = {
        "record_type": "stage12635_private_authoritative_ledger_update_dry_run_materialization_only_v1",
        **no_claim_fields(),
        **true_fields,
        "source_hashes": EXPECTED_HASHES,
        "candidate_manifest": private_manifest,
        "dry_run_materialization": materialization,
        "decision": "CANDIDATE_LEDGER_DRY_RUN_MATERIALIZED_NO_AUTHORITATIVE_UPDATE_OR_ADMISSION",
    }
    contract = {
        "record_type": "stage12635_public_authoritative_ledger_update_dry_run_materialization_only_contract_v1",
        **no_claim_fields(),
        **true_fields,
        "stage12634_authorization_sha256": EXPECTED_HASHES["stage12634_authorization"],
        "candidate_rows_sha256": EXPECTED_HASHES["stage12417_rows_bytes"],
        "candidate_ledger_sha256": EXPECTED_HASHES["stage12417_ledger"],
        "public_summary_diff_sha256": stable_hash(public_diff),
        "private_candidate_manifest_sha256": stable_hash(private_manifest),
        "dry_run_materialization_sha256": stable_hash(materialization),
        "private_dry_run_materialization_sha256": stable_hash(private),
        "claim_boundary": {"materialization": "candidate_dry_run_artifacts_only", "authoritative_ledger_update": "not_performed", "new_admission": "not_authorized", "training": "not_authorized", "eval": "not_authorized", "vm": "paused_not_used_for_dry_run", "replay": "not_executed", "level3": "not_materialized"},
    }
    summary = {
        "record_type": "stage12635_public_authoritative_ledger_update_dry_run_materialization_only_summary_v1",
        **no_claim_fields(),
        **true_fields,
        "stage": STAGE,
        "decision": "CANDIDATE_LEDGER_DRY_RUN_MATERIALIZED_NO_AUTHORITATIVE_UPDATE_OR_ADMISSION",
        "stage12634_authorization_sha256": EXPECTED_HASHES["stage12634_authorization"],
        "candidate_rows_sha256": EXPECTED_HASHES["stage12417_rows_bytes"],
        "candidate_ledger_sha256": EXPECTED_HASHES["stage12417_ledger"],
        "public_summary_diff_sha256": stable_hash(public_diff),
        "private_candidate_manifest_sha256": stable_hash(private_manifest),
        "dry_run_materialization_sha256": stable_hash(materialization),
        "private_dry_run_materialization_sha256": stable_hash(private),
        "materialization_status": "candidate_ledger_dry_run_materialized_no_authoritative_update_or_admission",
        "authoritative_admitted_train_support_tasks_after_dry_run": 158,
        "authoritative_gap_to_500_after_dry_run": 342,
        "candidate_train_support_tasks_after_dry_run": 190,
        "candidate_gap_to_500_after_dry_run": 310,
        "materialized_projection_rows": 99,
        "event_local_base_rows_referenced": 91,
        "candidate_delta_total": 32,
        "candidate_artifacts_written": 3,
        "summary_artifacts_updated": 0,
        "frontier_100m_training_dataset_ready": False,
        "downstream_blockers": ["authoritative_ledger_update_not_authorized", "new_train_support_rows_not_admitted", "authoritative_gap_still_342", "training_admission_forbidden"],
        "next_required_action": "independent_review_of_candidate_ledger_dry_run_before_authoritative_update_decision",
    }
    for label, record in (("summary", summary), ("contract", contract), ("public_diff", public_diff)):
        check_false(record, "stage12635_" + label)
        assert_public_sanitized(record, "stage12635_" + label)
    check_false(private, "stage12635_private")
    return summary, contract, private, public_diff, private_manifest


def fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    authorization = load_authorization()
    source = load_candidate_source()
    summary, contract, private, public_diff, private_manifest = build_packet(authorization, source)
    pointer = {
        "record_type": "stage12635_public_private_authoritative_ledger_update_dry_run_materialization_pointer_v1",
        **no_claim_fields(),
        "stage12634_summary_sha256": EXPECTED_HASHES["stage12634_summary"],
        "contract_sha256": stable_hash(contract),
        "private_dry_run_materialization_sha256": stable_hash(private),
        "dry_run_materialization_sha256": stable_hash(private["dry_run_materialization"]),
        "candidate_rows_sha256": EXPECTED_HASHES["stage12417_rows_bytes"],
        "candidate_ledger_sha256": EXPECTED_HASHES["stage12417_ledger"],
        "dry_run_authorization_granted": True,
        "dry_run_authorized": True,
        "authoritative_ledger_dry_run_allowed": True,
        "stage12635_authoritative_ledger_update_dry_run_only_allowed": True,
        "authoritative_ledger_dry_run_performed": True,
        "authoritative_ledger_update_dry_run_materialized": True,
        "candidate_ledger_materialized": True,
        "candidate_rows_materialized": True,
        "dry_run_candidate_artifacts_written": True,
        "candidate_projection_rows_materialized": True,
        "vm_branch_remains_paused": True,
    }
    check_false(pointer, "stage12635_pointer")
    assert_public_sanitized(pointer, "stage12635_pointer")
    write_bytes(out / "private/candidate_train_support_rows_dry_run.jsonl", source["rows_bytes"])
    write_json(out / "private/candidate_ledger_dry_run_manifest.json", private_manifest)
    write_json(out / "candidate_summary_diff.json", public_diff)
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "private/authoritative_ledger_update_dry_run_materialization_only.json", private)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    fsync_dir(out)
    fsync_dir(summary_path.parent)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
