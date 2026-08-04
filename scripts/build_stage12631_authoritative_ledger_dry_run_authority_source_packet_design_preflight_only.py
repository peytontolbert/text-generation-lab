#!/usr/bin/env python3
"""Build Stage12631 dry-run authority source-packet design preflight only."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12631_authoritative_ledger_dry_run_authority_source_packet_design_preflight_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
S12630 = ROOT / "runs/local/artifacts/stage12630_authoritative_ledger_dry_run_authority_source_packet_request_only"
S12630_SUMMARY = ROOT / "runs/summaries/stage12630_authoritative_ledger_dry_run_authority_source_packet_request_only.json"

EXPECTED_HASHES = {
    "stage12630_summary": "e627d1a2f8f0f716861701208475aa2e2c290346538f5652303e9663053c252d",
    "stage12630_contract": "3851a6401a6b898ab39f8381063636873413ab00f01002188476b07b884880b1",
    "stage12630_pointer": "c1354660afc4c5d2bde1d434dc90ee339a6c164a46484c9566d673ab493f2251",
    "stage12630_private": "6bfb436628086964dd1abd1f9c89bbcb1544b0dccd5a2d3288ada753b8ca26e3",
    "stage12630_request_review": "7f4a7ad68a073dbf1ab68a97782ebd4afb6ae6f561945f36129f221595ac3b11",
    "stage12629_request_scope": "b122eb2189ea43d5c75b943204e220e6cbaf8ac281e79bacd770007a4b72cfaf",
    "stage12626_update_plan": "2ebc45d3c86e6a51d3011b8b5b95f6bb7c19823cbaa54d8815ebffea66e24f99",
}

FALSE_FIELDS = (
    "implementation_ready", "dataset_admission_allowed", "dataset_rows_admitted", "new_rows_admitted",
    "frontier_100m_training_dataset_ready", "source_packet_implementation_allowed", "source_packet_executable",
    "stage12620_allowed", "stage12621_allowed", "stage12622_allowed", "stage12623_allowed", "stage12624_allowed",
    "stage12625_allowed", "stage12626_allowed", "stage12627_allowed", "stage12628_allowed", "stage12629_allowed",
    "stage12630_allowed", "stage12631_allowed", "stage12632_allowed",
    "stage12629_authoritative_ledger_update_dry_run_only_allowed",
    "stage12630_authoritative_ledger_update_dry_run_only_allowed",
    "stage12631_authoritative_ledger_dry_run_authority_source_packet_allowed",
    "stage12632_authoritative_ledger_dry_run_authority_source_packet_allowed",
    "stage12632_authoritative_ledger_update_dry_run_only_allowed",
    "vm_branch_active", "vm_runner_implementation_allowed", "vm_runner_implementation_ready", "vm_runner_execution_allowed",
    "vm_runner_evidence_present", "vm_runner_trustworthy", "storage_root_created", "storage_write_performed",
    "execution_performed", "replay_trustworthy", "raw_replay_evidence_present", "trusted_replay_raw_evidence_present",
    "causal_transition_atoms_present", "causal_transition_atoms_allowed", "level3_preflight_allowed",
    "level_3_materialized", "level_3_materialization_allowed", "training_admission_preflight_allowed",
    "training_admission_allowed", "training_admitted", "training_allowed", "training_run_allowed",
    "gpu_allocation_requested", "cuda2_training_allowed", "strict_eval_admitted", "sealed_eval_admitted",
    "strict_eval_eligible", "sealed_eval_eligible", "admission_allowed", "ranking_allowed", "positive_stop",
    "authoritative_ledger_updated", "authoritative_ledger_update_allowed", "authoritative_ledger_dry_run_performed",
    "authoritative_ledger_dry_run_allowed", "control_board_promoted_to_authoritative", "control_board_promotion_allowed",
    "row_artifacts_written", "summary_artifact_written", "ledger_update_materialized", "candidate_ledger_materialized",
    "candidate_rows_materialized", "dry_run_candidate_artifacts_written", "dry_run_authorized", "dry_run_ready",
    "dry_run_authorization_granted", "dry_run_authority_source_packet_present",
    "authoritative_ledger_update_dry_run_materialized",
)

PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "agentkernel_vm_replay", "/dev/", "selector", "raw_stream",
    "stdout.raw", "stderr.raw", "before_commit_oid", "after_commit_oid", "production_path",
    "production_patch_sha256", "manual_executor_slot_contracts", "slot_1.patch", "slot_2.patch",
    "repository_root", "patch_path", "slot_1/", "slot_2/", "combined_selected_test_rows",
    "combined_train_support_rows", "direct_verifier_log_train_support_manifest", "direct_verifier_log_train_support_rows",
    "guardrail_scan.json", "combined_train_support_ledger", "jsonl", "row_id", "stable_lineage_key",
)


class DesignPreflightError(RuntimeError):
    pass


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def stable_hash(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise DesignPreflightError("json_object_required:" + path.name)
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
            raise DesignPreflightError(f"{label}_gate_drift:{field}")


def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise DesignPreflightError(f"{label}_public_leak:{needle}")


def load_stage12630() -> dict[str, Any]:
    summary = read_json(S12630 / "summary.json")
    external = read_json(S12630_SUMMARY)
    contract = read_json(S12630 / "contract.json")
    pointer = read_json(S12630 / "digest_pointer.json")
    private = read_json(S12630 / "private/authoritative_ledger_dry_run_authority_source_packet_request_only.json")
    if summary != external:
        raise DesignPreflightError("stage12630_external_summary_mismatch")
    for label, value in (
        ("stage12630_summary", summary),
        ("stage12630_contract", contract),
        ("stage12630_pointer", pointer),
        ("stage12630_private", private),
    ):
        if stable_hash(value) != EXPECTED_HASHES[label]:
            raise DesignPreflightError("stage12630_pin_drift:" + label)
    request_review = private.get("request_review") or {}
    if stable_hash(request_review) != EXPECTED_HASHES["stage12630_request_review"]:
        raise DesignPreflightError("stage12630_request_review_hash_drift")
    if summary.get("dry_run_authority_source_packet_request_only") is not True:
        raise DesignPreflightError("stage12630_request_marker_missing")
    for field in (
        "dry_run_authority_source_packet_present",
        "dry_run_authorization_granted",
        "dry_run_authorized",
        "stage12631_authoritative_ledger_dry_run_authority_source_packet_allowed",
        "stage12631_allowed",
    ):
        if summary.get(field) is not False:
            raise DesignPreflightError("stage12630_gate_drift:" + field)
    if summary.get("authoritative_admitted_train_support_tasks_after_review") != 158:
        raise DesignPreflightError("stage12630_authoritative_count_drift")
    if summary.get("authoritative_gap_to_500_after_review") != 342:
        raise DesignPreflightError("stage12630_authoritative_gap_drift")
    return {"summary": summary, "contract": contract, "pointer": pointer, "private": private, "request_review": request_review}


def authority_packet_design() -> dict[str, Any]:
    return {
        "record_type": "stage12631_candidate_ledger_dry_run_authority_source_packet_design_v1",
        "design_scope": "future_authority_source_packet_shape_only",
        "future_packet_must_include": [
            "pinned_stage12626_update_plan_hash",
            "candidate_only_output_inventory",
            "no_authoritative_replacement_clause",
            "no_dataset_admission_clause",
            "no_training_eval_gpu_vm_replay_clause",
            "independent_review_before_any_dry_run_clause",
        ],
        "future_packet_must_not_grant": [
            "authoritative_ledger_update",
            "dataset_admission",
            "training_or_eval_admission",
            "vm_or_replay_execution",
            "level3_materialization",
        ],
        "stage12631_outputs": [
            "design_preflight_record_only",
            "public_private_digest_pointer",
            "no_authority_source_packet",
            "no_candidate_files",
        ],
    }


def build_design_preflight(stage12630: Mapping[str, Any]) -> dict[str, Any]:
    if stage12630["request_review"].get("minimum_unblock_condition") != "separate_explicit_dry_run_authority_source_packet_still_required":
        raise DesignPreflightError("stage12630_unblock_condition_drift")
    design = authority_packet_design()
    checks = [
        {"check_id": "predecessor_request_review_pinned", "status": "passed", "request_review_sha256": EXPECTED_HASHES["stage12630_request_review"]},
        {"check_id": "predecessor_does_not_grant_authority", "status": "passed", "dry_run_authority_source_packet_present": False},
        {"check_id": "future_packet_design_is_candidate_dry_run_only", "status": "passed", "design_sha256": stable_hash(design)},
        {"check_id": "stage12631_is_design_preflight_only", "status": "passed", "authority_created": False},
        {"check_id": "dataset_counts_preserved", "status": "passed", "authoritative_count": 158, "authoritative_gap": 342},
        {"check_id": "training_admission_remains_separate", "status": "passed", "training_allowed": False},
    ]
    return {
        "record_type": "stage12631_authoritative_ledger_dry_run_authority_source_packet_design_preflight_v1",
        "preflight_scope": "dry_run_authority_source_packet_design_preflight_only",
        "source_request_review_sha256": EXPECTED_HASHES["stage12630_request_review"],
        "authority_packet_design": design,
        "authority_packet_design_sha256": stable_hash(design),
        "preflight_checks": checks,
        "preflight_check_count": len(checks),
        "preflight_status": "design_recorded_authority_source_packet_still_absent",
        "dry_run_authorization_status": "not_granted_design_preflight_only",
        "authoritative_count_after_preflight": 158,
        "authoritative_gap_after_preflight": 342,
        "conditional_candidate_count_if_later_authority_and_dry_run_pass": 190,
        "conditional_candidate_gap_if_later_authority_and_dry_run_pass": 310,
        "reviewed_plan_delta_total": 32,
        "reviewed_selected_lineage_delta": 14,
        "reviewed_direct_real_log_delta": 18,
        "stage12418_countable_rows": 0,
        "candidate_artifacts_written": 0,
        "summary_artifacts_updated": 0,
        "dry_run_authority_source_packet_design_preflight_only": True,
        "dry_run_authority_source_packet_present": False,
        "dry_run_authorization_granted": False,
        "dry_run_performed": False,
        "authoritative_ledger_update_performed": False,
        "new_admission_performed": False,
        "training_allowed_after_preflight": False,
    }


def build_packet(stage12630: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    preflight = build_design_preflight(stage12630)
    private = {
        "record_type": "stage12631_private_authoritative_ledger_dry_run_authority_source_packet_design_preflight_only_v1",
        **no_claim_fields(),
        "source_hashes": EXPECTED_HASHES,
        "dry_run_authority_source_packet_design_preflight_only": True,
        "vm_branch_remains_paused": True,
        "design_preflight": preflight,
        "decision": "DRY_RUN_AUTHORITY_SOURCE_PACKET_DESIGN_PREFLIGHT_RECORDED_NO_AUTHORITY_GRANTED",
    }
    contract = {
        "record_type": "stage12631_public_authoritative_ledger_dry_run_authority_source_packet_design_preflight_only_contract_v1",
        **no_claim_fields(),
        "stage12630_summary_sha256": EXPECTED_HASHES["stage12630_summary"],
        "stage12630_request_review_sha256": EXPECTED_HASHES["stage12630_request_review"],
        "design_preflight_sha256": stable_hash(preflight),
        "private_design_preflight_sha256": stable_hash(private),
        "dry_run_authority_source_packet_design_preflight_only": True,
        "vm_branch_remains_paused": True,
        "claim_boundary": {
            "design": "future_authority_source_packet_shape_only",
            "authority": "not_created_or_granted",
            "dry_run": "not_authorized_or_performed",
            "authoritative_ledger_update": "not_authorized",
            "new_admission": "not_authorized",
            "training": "not_authorized",
            "vm": "paused_not_used_for_design_preflight",
            "replay": "not_executed",
            "level3": "not_materialized",
        },
    }
    summary = {
        "record_type": "stage12631_public_authoritative_ledger_dry_run_authority_source_packet_design_preflight_only_summary_v1",
        **no_claim_fields(),
        "stage": STAGE,
        "decision": "DRY_RUN_AUTHORITY_SOURCE_PACKET_DESIGN_PREFLIGHT_RECORDED_NO_AUTHORITY_GRANTED",
        "stage12630_summary_sha256": EXPECTED_HASHES["stage12630_summary"],
        "stage12630_request_review_sha256": EXPECTED_HASHES["stage12630_request_review"],
        "design_preflight_sha256": stable_hash(preflight),
        "private_design_preflight_sha256": stable_hash(private),
        "dry_run_authority_source_packet_design_preflight_only": True,
        "vm_branch_remains_paused": True,
        "preflight_status": "design_recorded_authority_source_packet_still_absent",
        "dry_run_authorization_status": "not_granted_design_preflight_only",
        "authoritative_admitted_train_support_tasks_after_preflight": 158,
        "authoritative_gap_to_500_after_preflight": 342,
        "conditional_candidate_count_if_later_authority_and_dry_run_pass": 190,
        "conditional_candidate_gap_if_later_authority_and_dry_run_pass": 310,
        "reviewed_plan_delta_total": 32,
        "reviewed_selected_lineage_delta": 14,
        "reviewed_direct_real_log_delta": 18,
        "stage12418_derived_projection_countable_rows": 0,
        "candidate_artifacts_written": 0,
        "summary_artifacts_updated": 0,
        "frontier_100m_training_dataset_ready": False,
        "downstream_blockers": [
            "explicit_dry_run_authority_source_packet_still_absent",
            "dry_run_authorization_not_granted",
            "candidate_ledger_dry_run_not_materialized",
            "candidate_ledger_artifacts_not_written",
            "authoritative_ledger_not_updated_in_stage12631",
            "new_train_support_rows_not_admitted",
            "authoritative_gap_still_342",
            "training_admission_forbidden",
        ],
    }
    for label, record in (("summary", summary), ("contract", contract)):
        check_false(record, "stage12631_" + label)
        assert_public_sanitized(record, "stage12631_" + label)
    check_false(private, "stage12631_private")
    return summary, contract, private


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    stage12630 = load_stage12630()
    summary, contract, private = build_packet(stage12630)
    pointer = {
        "record_type": "stage12631_public_private_authoritative_ledger_dry_run_authority_source_packet_design_preflight_pointer_v1",
        **no_claim_fields(),
        "stage12630_summary_sha256": EXPECTED_HASHES["stage12630_summary"],
        "contract_sha256": stable_hash(contract),
        "private_design_preflight_sha256": stable_hash(private),
        "design_preflight_sha256": stable_hash(private["design_preflight"]),
        "dry_run_authority_source_packet_design_preflight_only": True,
        "vm_branch_remains_paused": True,
    }
    check_false(pointer, "stage12631_pointer")
    assert_public_sanitized(pointer, "stage12631_pointer")
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "private/authoritative_ledger_dry_run_authority_source_packet_design_preflight_only.json", private)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
