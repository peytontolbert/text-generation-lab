#!/usr/bin/env python3
"""Build Stage12628 authoritative ledger dry-run authorization review only.

Stage12627 confirmed dry-run preflight completeness, but it also kept the
Stage12628 authorization-review gate and every dry-run/update/admission/training
gate false. This stage records that authorization review and blocks the dry run
until a separate explicit authority source packet exists. It does not perform a
dry run, write candidate ledger files, update the authoritative ledger, admit
rows, train, resume VM/replay, materialize Level-3, or authorize a successor.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12628_authoritative_ledger_dry_run_authorization_review_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
S12627 = ROOT / "runs/local/artifacts/stage12627_authoritative_ledger_update_dry_run_preflight_review_only"
S12627_SUMMARY = ROOT / "runs/summaries/stage12627_authoritative_ledger_update_dry_run_preflight_review_only.json"

EXPECTED_HASHES = {
    "stage12627_summary": "507f96995c23b4cbe9f50754087a6fb0220bd51ae47969a65cf6f1e80f953309",
    "stage12627_contract": "289d518275c42a4e6b92fb61fefa635db8ea7160433029664660802543f3038d",
    "stage12627_pointer": "101b62dc1ec7afbe7c6ed1c7c6927f1b660e79cf858b972ec3ac2600daac391e",
    "stage12627_private": "0794476e65f53fe2f80572e1e80d91cd3a2ae5065da5efc6c9bafbf595da44a0",
    "stage12627_preflight_review": "c179438a28968df23d51a0b25b0f0f00082af83f45721d499f52343eb4d9e59f",
    "stage12626_update_plan": "2ebc45d3c86e6a51d3011b8b5b95f6bb7c19823cbaa54d8815ebffea66e24f99",
    "stage12376": "a7aa3bcae28c5741f1955d2b954744143266bb61d2e824d78343e932cc3b695e",
    "stage12417": "c9a872e36c12888b7f3fd45218cb69aa7d75b238378368289483ba54c483721a",
}

FALSE_FIELDS = (
    "implementation_ready", "dataset_admission_allowed", "dataset_rows_admitted", "new_rows_admitted",
    "frontier_100m_training_dataset_ready", "source_packet_implementation_allowed", "source_packet_executable",
    "stage12620_allowed", "stage12621_allowed", "stage12622_allowed", "stage12623_allowed", "stage12624_allowed",
    "stage12625_allowed", "stage12626_allowed", "stage12627_allowed", "stage12628_allowed", "stage12629_allowed",
    "stage12627_authoritative_ledger_update_dry_run_only_allowed",
    "stage12628_authoritative_ledger_dry_run_authorization_review_allowed",
    "stage12629_authoritative_ledger_update_dry_run_only_allowed",
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
)

PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "agentkernel_vm_replay", "/dev/", "selector", "raw_stream",
    "stdout.raw", "stderr.raw", "before_commit_oid", "after_commit_oid", "production_path",
    "production_patch_sha256", "manual_executor_slot_contracts", "slot_1.patch", "slot_2.patch",
    "repository_root", "patch_path", "slot_1/", "slot_2/", "combined_selected_test_rows",
    "combined_train_support_rows", "direct_verifier_log_train_support_manifest", "direct_verifier_log_train_support_rows",
    "guardrail_scan.json", "combined_train_support_ledger", "jsonl", "row_id", "stable_lineage_key",
)


class DryRunAuthorizationReviewError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def stable_hash(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise DryRunAuthorizationReviewError("json_object_required:" + path.name)
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
            raise DryRunAuthorizationReviewError(f"{label}_gate_drift:{field}")


def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise DryRunAuthorizationReviewError(f"{label}_public_leak:{needle}")


def load_stage12627() -> dict[str, Any]:
    summary = read_json(S12627 / "summary.json")
    external = read_json(S12627_SUMMARY)
    contract = read_json(S12627 / "contract.json")
    pointer = read_json(S12627 / "digest_pointer.json")
    private = read_json(S12627 / "private/authoritative_ledger_dry_run_preflight_review_only.json")
    if summary != external:
        raise DryRunAuthorizationReviewError("stage12627_external_summary_mismatch")
    for label, value in (
        ("stage12627_summary", summary),
        ("stage12627_contract", contract),
        ("stage12627_pointer", pointer),
        ("stage12627_private", private),
    ):
        if stable_hash(value) != EXPECTED_HASHES[label]:
            raise DryRunAuthorizationReviewError("stage12627_pin_drift:" + label)
    preflight_review = private.get("dry_run_preflight_review") or {}
    if stable_hash(preflight_review) != EXPECTED_HASHES["stage12627_preflight_review"]:
        raise DryRunAuthorizationReviewError("stage12627_preflight_review_hash_drift")
    if summary.get("stage12628_authoritative_ledger_dry_run_authorization_review_allowed") is not False:
        raise DryRunAuthorizationReviewError("stage12627_authorization_review_gate_drift")
    if summary.get("stage12628_allowed") is not False:
        raise DryRunAuthorizationReviewError("stage12627_broad_successor_gate_drift")
    if summary.get("dry_run_authorized") is not False or summary.get("dry_run_ready") is not False:
        raise DryRunAuthorizationReviewError("stage12627_dry_run_authorization_drift")
    if summary.get("authoritative_admitted_train_support_tasks_after_review") != 158:
        raise DryRunAuthorizationReviewError("stage12627_authoritative_count_drift")
    if summary.get("authoritative_gap_to_500_after_review") != 342:
        raise DryRunAuthorizationReviewError("stage12627_authoritative_gap_drift")
    if preflight_review.get("minimum_next_review") != "stage12628_authoritative_ledger_dry_run_authorization_review_only":
        raise DryRunAuthorizationReviewError("stage12627_next_review_missing")
    if preflight_review.get("review_status") != "preflight_requirements_complete_but_dry_run_not_authorized":
        raise DryRunAuthorizationReviewError("stage12627_preflight_status_drift")
    return {"summary": summary, "contract": contract, "pointer": pointer, "private": private, "preflight_review": preflight_review}


def build_authorization_review(stage12627: Mapping[str, Any]) -> dict[str, Any]:
    summary = stage12627["summary"]
    preflight = stage12627["preflight_review"]
    if preflight.get("candidate_artifacts_written") != 0 or summary.get("candidate_artifacts_written") != 0:
        raise DryRunAuthorizationReviewError("stage12627_candidate_artifact_drift")
    if preflight.get("summary_artifacts_updated") != 0 or summary.get("summary_artifacts_updated") != 0:
        raise DryRunAuthorizationReviewError("stage12627_summary_update_drift")
    if preflight.get("conditional_candidate_count_if_later_dry_run_and_update_authorized") != 190:
        raise DryRunAuthorizationReviewError("stage12627_conditional_count_drift")
    if preflight.get("reviewed_plan_delta_total") != 32:
        raise DryRunAuthorizationReviewError("stage12627_reviewed_delta_drift")

    authorization_checks = [
        {"check_id": "predecessor_named_this_review_as_minimum_next_review", "status": "passed", "review_only": True},
        {"check_id": "predecessor_broad_successor_gate_absent", "status": "passed", "stage12628_allowed": False},
        {
            "check_id": "predecessor_specific_authorization_review_gate_absent",
            "status": "blocked",
            "stage12628_authoritative_ledger_dry_run_authorization_review_allowed": False,
        },
        {"check_id": "dry_run_authority_source_packet_absent", "status": "blocked", "dry_run_authority_source_packet_present": False},
        {"check_id": "candidate_artifacts_not_materialized", "status": "passed", "candidate_artifacts_written": 0},
        {"check_id": "authoritative_dataset_counts_preserved", "status": "passed", "authoritative_count": 158, "authoritative_gap": 342},
        {"check_id": "training_admission_remains_separate", "status": "passed", "training_allowed": False},
    ]
    return {
        "record_type": "stage12628_authoritative_ledger_dry_run_authorization_review_v1",
        "review_scope": "dry_run_authorization_review_only",
        "source_preflight_review_sha256": EXPECTED_HASHES["stage12627_preflight_review"],
        "authorization_checks": authorization_checks,
        "authorization_check_count": len(authorization_checks),
        "blocked_check_count": sum(1 for check in authorization_checks if check["status"] == "blocked"),
        "review_status": "authorization_review_complete_but_authorization_blocked",
        "authorization_review_outcome": "blocked",
        "dry_run_authorization_status": "blocked_missing_explicit_dry_run_authority_source_packet",
        "authoritative_count_before_review": 158,
        "authoritative_gap_before_review": 342,
        "authoritative_count_after_review": 158,
        "authoritative_gap_after_review": 342,
        "conditional_candidate_count_if_later_authorized": 190,
        "conditional_candidate_gap_if_later_authorized": 310,
        "reviewed_plan_delta_total": 32,
        "reviewed_selected_lineage_delta": 14,
        "reviewed_direct_real_log_delta": 18,
        "stage12418_countable_rows": 0,
        "candidate_artifacts_written": 0,
        "summary_artifacts_updated": 0,
        "required_private_manifest_count": 3,
        "minimum_unblock_condition": "separate_explicit_dry_run_authority_source_packet_required",
        "dry_run_authorization_review_only": True,
        "dry_run_authorization_granted": False,
        "dry_run_authority_source_packet_present": False,
        "dry_run_performed": False,
        "authoritative_ledger_update_performed": False,
        "new_admission_performed": False,
        "training_allowed_after_review": False,
    }


def build_packet(stage12627: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    review = build_authorization_review(stage12627)
    private = {
        "record_type": "stage12628_private_authoritative_ledger_dry_run_authorization_review_only_v1",
        **no_claim_fields(),
        "source_hashes": EXPECTED_HASHES,
        "dry_run_authorization_review_only": True,
        "vm_branch_remains_paused": True,
        "dry_run_authorization_review": review,
        "decision": "DRY_RUN_AUTHORIZATION_REVIEW_RECORDED_AUTHORIZATION_BLOCKED_NO_DRY_RUN",
    }
    contract = {
        "record_type": "stage12628_public_authoritative_ledger_dry_run_authorization_review_only_contract_v1",
        **no_claim_fields(),
        "stage12627_summary_sha256": EXPECTED_HASHES["stage12627_summary"],
        "stage12627_preflight_review_sha256": EXPECTED_HASHES["stage12627_preflight_review"],
        "stage12626_update_plan_sha256": EXPECTED_HASHES["stage12626_update_plan"],
        "stage12376_summary_sha256": EXPECTED_HASHES["stage12376"],
        "stage12417_summary_sha256": EXPECTED_HASHES["stage12417"],
        "dry_run_authorization_review_sha256": stable_hash(review),
        "private_dry_run_authorization_review_sha256": stable_hash(private),
        "dry_run_authorization_review_only": True,
        "vm_branch_remains_paused": True,
        "claim_boundary": {
            "review": "dry_run_authorization_review_only",
            "authorization": "blocked_not_granted",
            "dry_run": "not_authorized_or_performed",
            "authoritative_ledger_update": "not_performed",
            "new_admission": "not_authorized",
            "training": "not_authorized",
            "vm": "paused_not_used_for_authorization_review",
            "replay": "not_executed",
            "level3": "not_materialized",
        },
    }
    summary = {
        "record_type": "stage12628_public_authoritative_ledger_dry_run_authorization_review_only_summary_v1",
        **no_claim_fields(),
        "stage": STAGE,
        "decision": "DRY_RUN_AUTHORIZATION_REVIEW_RECORDED_AUTHORIZATION_BLOCKED_NO_DRY_RUN",
        "stage12627_summary_sha256": EXPECTED_HASHES["stage12627_summary"],
        "stage12627_preflight_review_sha256": EXPECTED_HASHES["stage12627_preflight_review"],
        "stage12626_update_plan_sha256": EXPECTED_HASHES["stage12626_update_plan"],
        "stage12376_summary_sha256": EXPECTED_HASHES["stage12376"],
        "stage12417_summary_sha256": EXPECTED_HASHES["stage12417"],
        "dry_run_authorization_review_sha256": stable_hash(review),
        "private_dry_run_authorization_review_sha256": stable_hash(private),
        "dry_run_authorization_review_only": True,
        "vm_branch_remains_paused": True,
        "review_status": "authorization_review_complete_but_authorization_blocked",
        "authorization_review_outcome": "blocked",
        "dry_run_authorization_status": "blocked_missing_explicit_dry_run_authority_source_packet",
        "authoritative_admitted_train_support_tasks_after_review": 158,
        "authoritative_gap_to_500_after_review": 342,
        "conditional_candidate_count_if_later_authorized": 190,
        "conditional_candidate_gap_if_later_authorized": 310,
        "reviewed_plan_delta_total": 32,
        "reviewed_selected_lineage_delta": 14,
        "reviewed_direct_real_log_delta": 18,
        "stage12418_derived_projection_countable_rows": 0,
        "required_private_manifest_count": 3,
        "authorization_check_count": review["authorization_check_count"],
        "blocked_check_count": review["blocked_check_count"],
        "candidate_artifacts_written": 0,
        "summary_artifacts_updated": 0,
        "frontier_100m_training_dataset_ready": False,
        "downstream_blockers": [
            "explicit_dry_run_authority_source_packet_absent",
            "authoritative_ledger_update_dry_run_not_materialized",
            "candidate_ledger_artifacts_not_written",
            "authoritative_ledger_not_updated_in_stage12628",
            "new_train_support_rows_not_admitted",
            "authoritative_gap_still_342",
            "training_admission_forbidden",
        ],
    }
    for label, record in (("summary", summary), ("contract", contract)):
        check_false(record, "stage12628_" + label)
        assert_public_sanitized(record, "stage12628_" + label)
    check_false(private, "stage12628_private")
    return summary, contract, private


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    stage12627 = load_stage12627()
    summary, contract, private = build_packet(stage12627)
    pointer = {
        "record_type": "stage12628_public_private_authoritative_ledger_dry_run_authorization_review_pointer_v1",
        **no_claim_fields(),
        "stage12627_summary_sha256": EXPECTED_HASHES["stage12627_summary"],
        "contract_sha256": stable_hash(contract),
        "private_dry_run_authorization_review_sha256": stable_hash(private),
        "dry_run_authorization_review_sha256": stable_hash(private["dry_run_authorization_review"]),
        "dry_run_authorization_review_only": True,
        "vm_branch_remains_paused": True,
    }
    check_false(pointer, "stage12628_pointer")
    assert_public_sanitized(pointer, "stage12628_pointer")
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "private/authoritative_ledger_dry_run_authorization_review_only.json", private)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
