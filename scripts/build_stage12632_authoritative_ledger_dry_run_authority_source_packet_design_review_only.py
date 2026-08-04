#!/usr/bin/env python3
# Build Stage12632 dry-run authority source-packet creation only.
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12632_authoritative_ledger_dry_run_authority_source_packet_creation_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
S12631 = ROOT / "runs/local/artifacts/stage12631_authoritative_ledger_dry_run_authority_source_packet_design_preflight_only"
S12631_SUMMARY = ROOT / "runs/summaries/stage12631_authoritative_ledger_dry_run_authority_source_packet_design_preflight_only.json"

EXPECTED_HASHES = {
    "stage12631_summary": "6d9ab41a5c00e60206af036e1d9e7031dde1ad17683d9663847e9bb0fc0b5749",
    "stage12631_contract": "52000cbad1ae4de6ef896cbd5fa00a3dfb14a0802c532a05a1977ff241fda801",
    "stage12631_pointer": "081fbc913e0573c54a0a62ae21a3e0a3b854cc4d7476f35c9a2326e3f4d20764",
    "stage12631_private": "a7cc508076fd7ce48667f67287c271eb5bb98d6e0cc8fce9ee4181c80f0c0edd",
    "stage12631_design_preflight": "ed0cd105746c087c7521ed1623132777717f17e6931ba4647ef365c0fcd729cd",
    "stage12631_authority_packet_design": "9389f674c76fc358875619608b7969f6bb01015600fcc0ef1e4780ed5093feb9",
    "stage12626_update_plan": "2ebc45d3c86e6a51d3011b8b5b95f6bb7c19823cbaa54d8815ebffea66e24f99",
}

FALSE_FIELDS = (
    "implementation_ready", "dataset_admission_allowed", "dataset_rows_admitted", "new_rows_admitted",
    "frontier_100m_training_dataset_ready", "source_packet_implementation_allowed", "source_packet_executable",
    "stage12629_allowed", "stage12630_allowed", "stage12631_allowed", "stage12632_allowed", "stage12633_allowed",
    "stage12631_authoritative_ledger_dry_run_authority_source_packet_allowed",
    "stage12632_authoritative_ledger_dry_run_authority_source_packet_allowed",
    "stage12632_authoritative_ledger_update_dry_run_only_allowed",
    "stage12633_authoritative_ledger_update_dry_run_only_allowed",
    "vm_branch_active", "vm_runner_execution_allowed", "execution_performed", "storage_write_performed", "replay_trustworthy",
    "causal_transition_atoms_present", "causal_transition_atoms_allowed", "level3_preflight_allowed", "level_3_materialized",
    "level_3_materialization_allowed", "gpu_allocation_requested", "cuda2_training_allowed",
    "training_admission_allowed", "training_admission_preflight_allowed", "training_admitted", "training_allowed", "training_run_allowed",
    "strict_eval_admitted", "sealed_eval_admitted", "strict_eval_eligible", "sealed_eval_eligible",
    "admission_allowed", "ranking_allowed", "positive_stop", "authoritative_ledger_updated",
    "authoritative_ledger_update_allowed", "authoritative_ledger_dry_run_performed", "authoritative_ledger_dry_run_allowed",
    "authoritative_ledger_update_dry_run_materialized", "row_artifacts_written", "summary_artifact_written",
    "ledger_update_materialized", "candidate_ledger_materialized", "candidate_rows_materialized",
    "dry_run_candidate_artifacts_written", "dry_run_authorized", "dry_run_ready", "dry_run_authorization_granted",
)
PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "agentkernel_vm_replay", "/dev/", "selector", "raw_stream", "stdout.raw", "stderr.raw",
    "before_commit_oid", "after_commit_oid", "production_path", "production_patch_sha256", "manual_executor_slot_contracts",
    "slot_1.patch", "slot_2.patch", "repository_root", "patch_path", "slot_1/", "slot_2/", "combined_selected_test_rows",
    "combined_train_support_rows", "direct_verifier_log_train_support_manifest", "direct_verifier_log_train_support_rows",
    "guardrail_scan.json", "combined_train_support_ledger", "jsonl", "row_id", "stable_lineage_key",
)

class SourcePacketCreationError(RuntimeError):
    pass

def stable_hash(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(data).hexdigest()

def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SourcePacketCreationError("json_object_required:" + path.name)
    return value

def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True).encode("ascii") + b"\n"
    with path.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())

def no_claim_fields() -> dict[str, Any]:
    return {field: False for field in FALSE_FIELDS}

def check_false(record: Mapping[str, Any], label: str) -> None:
    for field in FALSE_FIELDS:
        if field in record and record[field] is not False:
            raise SourcePacketCreationError(f"{label}_gate_drift:{field}")

def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise SourcePacketCreationError(f"{label}_public_leak:{needle}")

def load_stage12631() -> dict[str, Any]:
    summary = read_json(S12631 / "summary.json")
    external = read_json(S12631_SUMMARY)
    contract = read_json(S12631 / "contract.json")
    pointer = read_json(S12631 / "digest_pointer.json")
    private = read_json(S12631 / "private/authoritative_ledger_dry_run_authority_source_packet_design_preflight_only.json")
    if summary != external:
        raise SourcePacketCreationError("stage12631_external_summary_mismatch")
    for label, value in (("stage12631_summary", summary), ("stage12631_contract", contract), ("stage12631_pointer", pointer), ("stage12631_private", private)):
        if stable_hash(value) != EXPECTED_HASHES[label]:
            raise SourcePacketCreationError("stage12631_pin_drift:" + label)
    preflight = private.get("design_preflight") or {}
    design = preflight.get("authority_packet_design") or {}
    if stable_hash(preflight) != EXPECTED_HASHES["stage12631_design_preflight"]:
        raise SourcePacketCreationError("stage12631_design_preflight_hash_drift")
    if stable_hash(design) != EXPECTED_HASHES["stage12631_authority_packet_design"]:
        raise SourcePacketCreationError("stage12631_design_hash_drift")
    for field in ("dry_run_authority_source_packet_present", "dry_run_authorization_granted", "dry_run_authorized", "stage12632_authoritative_ledger_dry_run_authority_source_packet_allowed", "stage12632_authoritative_ledger_update_dry_run_only_allowed", "stage12632_allowed"):
        if summary.get(field) is not False:
            raise SourcePacketCreationError("stage12631_gate_drift:" + field)
    if summary.get("authoritative_admitted_train_support_tasks_after_preflight") != 158:
        raise SourcePacketCreationError("stage12631_count_drift")
    if summary.get("authoritative_gap_to_500_after_preflight") != 342:
        raise SourcePacketCreationError("stage12631_gap_drift")
    return {"summary": summary, "private": private, "preflight": preflight, "design": design}

def authority_source_packet(stage12631: Mapping[str, Any]) -> dict[str, Any]:
    design = stage12631["design"]
    return {
        "record_type": "stage12632_candidate_ledger_dry_run_authority_source_packet_v1",
        "packet_scope": "candidate_ledger_dry_run_authority_source_packet_non_executable",
        "source_design_sha256": EXPECTED_HASHES["stage12631_authority_packet_design"],
        "source_update_plan_sha256": EXPECTED_HASHES["stage12626_update_plan"],
        "included_design_requirements": list(design["future_packet_must_include"]),
        "explicitly_not_granted": list(design["future_packet_must_not_grant"]),
        "authorized_future_action": "review_this_packet_before_any_candidate_ledger_dry_run",
        "candidate_dry_run_authorization_granted_now": False,
        "dry_run_execution_allowed_now": False,
        "authoritative_ledger_update_allowed_now": False,
        "dataset_admission_allowed_now": False,
        "training_allowed_now": False,
        "vm_replay_allowed_now": False,
    }

def build_creation(stage12631: Mapping[str, Any]) -> dict[str, Any]:
    packet = authority_source_packet(stage12631)
    checks = [
        {"check_id": "predecessor_design_pinned", "status": "passed"},
        {"check_id": "packet_created_as_non_executable_authority_source", "status": "passed", "dry_run_authority_source_packet_present": True},
        {"check_id": "packet_does_not_grant_dry_run", "status": "passed", "dry_run_authorization_granted": False},
        {"check_id": "packet_does_not_grant_update_admission_training", "status": "passed", "training_allowed": False},
        {"check_id": "dataset_counts_preserved", "status": "passed", "authoritative_count": 158, "authoritative_gap": 342},
    ]
    return {
        "record_type": "stage12632_authoritative_ledger_dry_run_authority_source_packet_creation_v1",
        "creation_scope": "dry_run_authority_source_packet_creation_only",
        "authority_source_packet": packet,
        "authority_source_packet_sha256": stable_hash(packet),
        "creation_checks": checks,
        "creation_check_count": len(checks),
        "creation_status": "non_executable_authority_source_packet_created_no_authorization_granted",
        "dry_run_authorization_status": "not_granted_packet_review_required",
        "authoritative_count_after_creation": 158,
        "authoritative_gap_after_creation": 342,
        "conditional_candidate_count_if_later_authority_and_dry_run_pass": 190,
        "conditional_candidate_gap_if_later_authority_and_dry_run_pass": 310,
        "reviewed_plan_delta_total": 32,
        "candidate_artifacts_written": 0,
        "summary_artifacts_updated": 0,
        "dry_run_authority_source_packet_creation_only": True,
        "dry_run_authority_source_packet_present": True,
        "dry_run_authorization_granted": False,
        "dry_run_performed": False,
        "authoritative_ledger_update_performed": False,
        "new_admission_performed": False,
        "training_allowed_after_creation": False,
    }

def build_packet(stage12631: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    creation = build_creation(stage12631)
    private = {
        "record_type": "stage12632_private_authoritative_ledger_dry_run_authority_source_packet_creation_only_v1",
        **no_claim_fields(),
        "source_hashes": EXPECTED_HASHES,
        "dry_run_authority_source_packet_creation_only": True,
        "dry_run_authority_source_packet_present": True,
        "vm_branch_remains_paused": True,
        "source_packet_creation": creation,
        "decision": "DRY_RUN_AUTHORITY_SOURCE_PACKET_CREATED_NO_AUTHORIZATION_GRANTED",
    }
    contract = {
        "record_type": "stage12632_public_authoritative_ledger_dry_run_authority_source_packet_creation_only_contract_v1",
        **no_claim_fields(),
        "stage12631_summary_sha256": EXPECTED_HASHES["stage12631_summary"],
        "stage12631_authority_packet_design_sha256": EXPECTED_HASHES["stage12631_authority_packet_design"],
        "authority_source_packet_sha256": creation["authority_source_packet_sha256"],
        "source_packet_creation_sha256": stable_hash(creation),
        "private_source_packet_creation_sha256": stable_hash(private),
        "dry_run_authority_source_packet_creation_only": True,
        "dry_run_authority_source_packet_present": True,
        "vm_branch_remains_paused": True,
        "claim_boundary": {"source_packet": "non_executable_packet_created", "dry_run": "not_authorized_or_performed", "authoritative_ledger_update": "not_authorized", "new_admission": "not_authorized", "training": "not_authorized", "vm": "paused_not_used_for_packet_creation", "replay": "not_executed", "level3": "not_materialized"},
    }
    summary = {
        "record_type": "stage12632_public_authoritative_ledger_dry_run_authority_source_packet_creation_only_summary_v1",
        **no_claim_fields(),
        "stage": STAGE,
        "decision": "DRY_RUN_AUTHORITY_SOURCE_PACKET_CREATED_NO_AUTHORIZATION_GRANTED",
        "stage12631_summary_sha256": EXPECTED_HASHES["stage12631_summary"],
        "stage12631_authority_packet_design_sha256": EXPECTED_HASHES["stage12631_authority_packet_design"],
        "authority_source_packet_sha256": creation["authority_source_packet_sha256"],
        "source_packet_creation_sha256": stable_hash(creation),
        "private_source_packet_creation_sha256": stable_hash(private),
        "dry_run_authority_source_packet_creation_only": True,
        "dry_run_authority_source_packet_present": True,
        "vm_branch_remains_paused": True,
        "creation_status": "non_executable_authority_source_packet_created_no_authorization_granted",
        "dry_run_authorization_status": "not_granted_packet_review_required",
        "authoritative_admitted_train_support_tasks_after_creation": 158,
        "authoritative_gap_to_500_after_creation": 342,
        "conditional_candidate_count_if_later_authority_and_dry_run_pass": 190,
        "conditional_candidate_gap_if_later_authority_and_dry_run_pass": 310,
        "reviewed_plan_delta_total": 32,
        "candidate_artifacts_written": 0,
        "summary_artifacts_updated": 0,
        "frontier_100m_training_dataset_ready": False,
        "downstream_blockers": ["authority_source_packet_independent_review_absent", "dry_run_authorization_not_granted", "candidate_ledger_dry_run_not_materialized", "candidate_ledger_artifacts_not_written", "authoritative_ledger_not_updated_in_stage12632", "new_train_support_rows_not_admitted", "authoritative_gap_still_342", "training_admission_forbidden"],
    }
    for label, record in (("summary", summary), ("contract", contract)):
        check_false(record, "stage12632_" + label)
        assert_public_sanitized(record, "stage12632_" + label)
    check_false(private, "stage12632_private")
    return summary, contract, private

def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    stage12631 = load_stage12631()
    summary, contract, private = build_packet(stage12631)
    pointer = {
        "record_type": "stage12632_public_private_authoritative_ledger_dry_run_authority_source_packet_creation_pointer_v1",
        **no_claim_fields(),
        "stage12631_summary_sha256": EXPECTED_HASHES["stage12631_summary"],
        "contract_sha256": stable_hash(contract),
        "private_source_packet_creation_sha256": stable_hash(private),
        "source_packet_creation_sha256": stable_hash(private["source_packet_creation"]),
        "dry_run_authority_source_packet_creation_only": True,
        "dry_run_authority_source_packet_present": True,
        "vm_branch_remains_paused": True,
    }
    check_false(pointer, "stage12632_pointer")
    assert_public_sanitized(pointer, "stage12632_pointer")
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "private/authoritative_ledger_dry_run_authority_source_packet_creation_only.json", private)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    return summary

if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
