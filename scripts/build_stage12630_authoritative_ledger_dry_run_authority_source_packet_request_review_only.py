#!/usr/bin/env python3
"""Build Stage12630 dry-run authority source-packet request review only."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12630_authoritative_ledger_dry_run_authority_source_packet_request_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
S12629 = ROOT / "runs/local/artifacts/stage12629_authoritative_ledger_dry_run_authority_source_packet_request_only"
S12629_SUMMARY = ROOT / "runs/summaries/stage12629_authoritative_ledger_dry_run_authority_source_packet_request_only.json"

EXPECTED_HASHES = {
    "stage12629_summary": "e4195a3ee90232974ef252a22944a303f8360ceed699941c6cea823d8935991d",
    "stage12629_contract": "d8cb074f930a5ba9025ff9fb1f95ac4a8565bbe8ab800166bb5d82bb8df2dbf4",
    "stage12629_pointer": "b28f4a9fbaa7934278dd10cfb65715adb1fcd8d7d43d1ac40042717410d1640d",
    "stage12629_private": "bcd3e2b38992ad1f2f535ea3784170544295c74e7b84464aaebe4dc1daa3249f",
    "stage12629_request_scope": "b122eb2189ea43d5c75b943204e220e6cbaf8ac281e79bacd770007a4b72cfaf",
    "stage12628_summary": "0b84b1ee422e70057982782f52a770a50f2bd8ca3571f624d4b5d6ed47e152d0",
    "stage12628_authorization_review": "91c6c96f7afc8eee8833bbfe4593bf5cbd7c5bc0d0f7d7e3b0c343a5790f42ad",
    "stage12626_update_plan": "2ebc45d3c86e6a51d3011b8b5b95f6bb7c19823cbaa54d8815ebffea66e24f99",
}

FALSE_FIELDS = (
    "implementation_ready", "dataset_admission_allowed", "dataset_rows_admitted", "new_rows_admitted",
    "frontier_100m_training_dataset_ready", "source_packet_implementation_allowed", "source_packet_executable",
    "stage12620_allowed", "stage12621_allowed", "stage12622_allowed", "stage12623_allowed", "stage12624_allowed",
    "stage12625_allowed", "stage12626_allowed", "stage12627_allowed", "stage12628_allowed", "stage12629_allowed",
    "stage12630_allowed", "stage12631_allowed",
    "stage12627_authoritative_ledger_update_dry_run_only_allowed",
    "stage12628_authoritative_ledger_dry_run_authorization_review_allowed",
    "stage12629_authoritative_ledger_update_dry_run_only_allowed",
    "stage12630_authoritative_ledger_update_dry_run_only_allowed",
    "stage12631_authoritative_ledger_dry_run_authority_source_packet_allowed",
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


class RequestReviewError(RuntimeError):
    pass


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def stable_hash(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RequestReviewError("json_object_required:" + path.name)
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
            raise RequestReviewError(f"{label}_gate_drift:{field}")


def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise RequestReviewError(f"{label}_public_leak:{needle}")


def load_stage12629() -> dict[str, Any]:
    summary = read_json(S12629 / "summary.json")
    external = read_json(S12629_SUMMARY)
    contract = read_json(S12629 / "contract.json")
    pointer = read_json(S12629 / "digest_pointer.json")
    private = read_json(S12629 / "private/authoritative_ledger_dry_run_authority_source_packet_request_only.json")
    if summary != external:
        raise RequestReviewError("stage12629_external_summary_mismatch")
    for label, value in (
        ("stage12629_summary", summary),
        ("stage12629_contract", contract),
        ("stage12629_pointer", pointer),
        ("stage12629_private", private),
    ):
        if stable_hash(value) != EXPECTED_HASHES[label]:
            raise RequestReviewError("stage12629_pin_drift:" + label)
    request_scope = private.get("request_scope") or {}
    if stable_hash(request_scope) != EXPECTED_HASHES["stage12629_request_scope"]:
        raise RequestReviewError("stage12629_request_scope_hash_drift")
    if summary.get("dry_run_authority_source_packet_request_only") is not True:
        raise RequestReviewError("stage12629_request_marker_missing")
    if summary.get("dry_run_authority_source_packet_present") is not False:
        raise RequestReviewError("stage12629_source_packet_presence_drift")
    if summary.get("dry_run_authorization_granted") is not False or summary.get("dry_run_authorized") is not False:
        raise RequestReviewError("stage12629_authorization_drift")
    if summary.get("stage12630_authoritative_ledger_update_dry_run_only_allowed") is not False:
        raise RequestReviewError("stage12629_dry_run_gate_drift")
    if summary.get("stage12630_allowed") is not False:
        raise RequestReviewError("stage12629_broad_successor_gate_drift")
    if summary.get("authoritative_admitted_train_support_tasks_after_request") != 158:
        raise RequestReviewError("stage12629_authoritative_count_drift")
    if summary.get("authoritative_gap_to_500_after_request") != 342:
        raise RequestReviewError("stage12629_authoritative_gap_drift")
    return {"summary": summary, "contract": contract, "pointer": pointer, "private": private, "request_scope": request_scope}


def build_request_review(stage12629: Mapping[str, Any]) -> dict[str, Any]:
    scope = stage12629["request_scope"]
    required = (
        "candidate_ledger_files_only_authority_source_packet",
        "candidate_summary_diff_only_authority_source_packet",
        "pinned_stage12626_plan_input_recount_contract",
        "private_supersession_merge_duplicate_manifest_contract",
    )
    if tuple(scope.get("request_only_items") or ()) != required:
        raise RequestReviewError("stage12629_request_items_drift")
    checks = [
        {"check_id": "request_marker_present", "status": "passed", "request_only": True},
        {"check_id": "authority_source_packet_absent", "status": "passed", "dry_run_authority_source_packet_present": False},
        {"check_id": "dry_run_authorization_absent", "status": "passed", "dry_run_authorization_granted": False},
        {"check_id": "future_authority_requires_independent_review", "status": "passed", "independent_review_required": True},
        {"check_id": "candidate_counts_remain_conditional", "status": "passed", "conditional_count": 190, "conditional_gap": 310},
        {"check_id": "training_admission_remains_separate", "status": "passed", "training_allowed": False},
    ]
    return {
        "record_type": "stage12630_authoritative_ledger_dry_run_authority_source_packet_request_review_v1",
        "review_scope": "dry_run_authority_source_packet_request_only",
        "source_request_scope_sha256": EXPECTED_HASHES["stage12629_request_scope"],
        "review_checks": checks,
        "review_check_count": len(checks),
        "review_status": "request_coherent_but_authority_source_packet_still_absent",
        "dry_run_authorization_status": "not_granted_request_review_only",
        "authoritative_count_after_review": 158,
        "authoritative_gap_after_review": 342,
        "conditional_candidate_count_if_later_authority_and_dry_run_pass": 190,
        "conditional_candidate_gap_if_later_authority_and_dry_run_pass": 310,
        "reviewed_plan_delta_total": 32,
        "reviewed_selected_lineage_delta": 14,
        "reviewed_direct_real_log_delta": 18,
        "stage12418_countable_rows": 0,
        "candidate_artifacts_written": 0,
        "summary_artifacts_updated": 0,
        "minimum_unblock_condition": "separate_explicit_dry_run_authority_source_packet_still_required",
        "dry_run_authority_source_packet_request_only": True,
        "dry_run_authority_source_packet_present": False,
        "dry_run_authorization_granted": False,
        "dry_run_performed": False,
        "authoritative_ledger_update_performed": False,
        "new_admission_performed": False,
        "training_allowed_after_review": False,
    }


def build_packet(stage12629: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    review = build_request_review(stage12629)
    private = {
        "record_type": "stage12630_private_authoritative_ledger_dry_run_authority_source_packet_request_only_v1",
        **no_claim_fields(),
        "source_hashes": EXPECTED_HASHES,
        "dry_run_authority_source_packet_request_only": True,
        "vm_branch_remains_paused": True,
        "request_review": review,
        "decision": "DRY_RUN_AUTHORITY_SOURCE_PACKET_REQUEST_REVIEW_RECORDED_AUTHORITY_STILL_NOT_GRANTED",
    }
    contract = {
        "record_type": "stage12630_public_authoritative_ledger_dry_run_authority_source_packet_request_only_contract_v1",
        **no_claim_fields(),
        "stage12629_summary_sha256": EXPECTED_HASHES["stage12629_summary"],
        "stage12629_request_scope_sha256": EXPECTED_HASHES["stage12629_request_scope"],
        "request_review_sha256": stable_hash(review),
        "private_request_review_sha256": stable_hash(private),
        "dry_run_authority_source_packet_request_only": True,
        "vm_branch_remains_paused": True,
        "claim_boundary": {
            "review": "request_review_only",
            "authority": "not_created_or_granted",
            "dry_run": "not_authorized_or_performed",
            "authoritative_ledger_update": "not_authorized",
            "new_admission": "not_authorized",
            "training": "not_authorized",
            "vm": "paused_not_used_for_request_review",
            "replay": "not_executed",
            "level3": "not_materialized",
        },
    }
    summary = {
        "record_type": "stage12630_public_authoritative_ledger_dry_run_authority_source_packet_request_only_summary_v1",
        **no_claim_fields(),
        "stage": STAGE,
        "decision": "DRY_RUN_AUTHORITY_SOURCE_PACKET_REQUEST_REVIEW_RECORDED_AUTHORITY_STILL_NOT_GRANTED",
        "stage12629_summary_sha256": EXPECTED_HASHES["stage12629_summary"],
        "stage12629_request_scope_sha256": EXPECTED_HASHES["stage12629_request_scope"],
        "request_review_sha256": stable_hash(review),
        "private_request_review_sha256": stable_hash(private),
        "dry_run_authority_source_packet_request_only": True,
        "vm_branch_remains_paused": True,
        "review_status": "request_coherent_but_authority_source_packet_still_absent",
        "dry_run_authorization_status": "not_granted_request_review_only",
        "authoritative_admitted_train_support_tasks_after_review": 158,
        "authoritative_gap_to_500_after_review": 342,
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
            "authoritative_ledger_not_updated_in_stage12630",
            "new_train_support_rows_not_admitted",
            "authoritative_gap_still_342",
            "training_admission_forbidden",
        ],
    }
    for label, record in (("summary", summary), ("contract", contract)):
        check_false(record, "stage12630_" + label)
        assert_public_sanitized(record, "stage12630_" + label)
    check_false(private, "stage12630_private")
    return summary, contract, private


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    stage12629 = load_stage12629()
    summary, contract, private = build_packet(stage12629)
    pointer = {
        "record_type": "stage12630_public_private_authoritative_ledger_dry_run_authority_source_packet_request_review_pointer_v1",
        **no_claim_fields(),
        "stage12629_summary_sha256": EXPECTED_HASHES["stage12629_summary"],
        "contract_sha256": stable_hash(contract),
        "private_request_review_sha256": stable_hash(private),
        "request_review_sha256": stable_hash(private["request_review"]),
        "dry_run_authority_source_packet_request_only": True,
        "vm_branch_remains_paused": True,
    }
    check_false(pointer, "stage12630_pointer")
    assert_public_sanitized(pointer, "stage12630_pointer")
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "private/authoritative_ledger_dry_run_authority_source_packet_request_only.json", private)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
