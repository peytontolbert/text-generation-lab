#!/usr/bin/env python3
# Build Stage12633 dry-run authority source-packet independent review only.
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12633_authoritative_ledger_dry_run_authority_source_packet_independent_review_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
S12632 = ROOT / "runs/local/artifacts/stage12632_authoritative_ledger_dry_run_authority_source_packet_creation_only"
S12632_SUMMARY = ROOT / "runs/summaries/stage12632_authoritative_ledger_dry_run_authority_source_packet_creation_only.json"

EXPECTED_HASHES = {
    "stage12632_summary": "1f79e185a00fe8450616c535c5e73799535ae306390a5f7151f4eabcb17bf0f0",
    "stage12632_contract": "7dfc0e2d82679325c60f13f54d491be3af9f8ef836f888f3c271dc24ad1da63c",
    "stage12632_pointer": "368e731dd7c813095d3ded5bbb999d6c7c5c480ce9178fdddd79da6ae3dd4e31",
    "stage12632_private": "5519577846a8e125364e82a8717e143f016bb154ea76546404f33e0c34a72044",
    "stage12632_source_packet_creation": "6dd4e12246298c1dc2d07526370de17c47a38ac86cfd98c839d343e9540d95c7",
    "stage12632_authority_source_packet": "e684e8437947608c68afd3567f7ec8a2ccacc41aa6c4d65f8cf7eb54bafa8ff7",
}

FALSE_FIELDS = (
    "implementation_ready", "dataset_admission_allowed", "dataset_rows_admitted", "new_rows_admitted",
    "frontier_100m_training_dataset_ready", "source_packet_implementation_allowed", "source_packet_executable",
    "stage12629_allowed", "stage12630_allowed", "stage12631_allowed", "stage12632_allowed", "stage12633_allowed",
    "stage12634_allowed",
    "stage12631_authoritative_ledger_dry_run_authority_source_packet_allowed",
    "stage12632_authoritative_ledger_dry_run_authority_source_packet_allowed",
    "stage12632_authoritative_ledger_update_dry_run_only_allowed",
    "stage12633_authoritative_ledger_update_dry_run_only_allowed",
    "stage12634_authoritative_ledger_update_dry_run_only_allowed",
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


class SourcePacketReviewError(RuntimeError):
    pass


def stable_hash(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SourcePacketReviewError("json_object_required:" + path.name)
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
            raise SourcePacketReviewError(f"{label}_gate_drift:{field}")


def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise SourcePacketReviewError(f"{label}_public_leak:{needle}")


def load_stage12632() -> dict[str, Any]:
    summary = read_json(S12632 / "summary.json")
    external = read_json(S12632_SUMMARY)
    contract = read_json(S12632 / "contract.json")
    pointer = read_json(S12632 / "digest_pointer.json")
    private = read_json(S12632 / "private/authoritative_ledger_dry_run_authority_source_packet_creation_only.json")
    if summary != external:
        raise SourcePacketReviewError("stage12632_external_summary_mismatch")
    for label, value in (("stage12632_summary", summary), ("stage12632_contract", contract), ("stage12632_pointer", pointer), ("stage12632_private", private)):
        if stable_hash(value) != EXPECTED_HASHES[label]:
            raise SourcePacketReviewError("stage12632_pin_drift:" + label)
    creation = private.get("source_packet_creation") or {}
    packet = creation.get("authority_source_packet") or {}
    if stable_hash(creation) != EXPECTED_HASHES["stage12632_source_packet_creation"]:
        raise SourcePacketReviewError("stage12632_source_packet_creation_hash_drift")
    if stable_hash(packet) != EXPECTED_HASHES["stage12632_authority_source_packet"]:
        raise SourcePacketReviewError("stage12632_authority_source_packet_hash_drift")
    for field in ("dry_run_authority_source_packet_creation_only", "dry_run_authority_source_packet_present", "vm_branch_remains_paused"):
        if summary.get(field) is not True:
            raise SourcePacketReviewError("stage12632_true_marker_drift:" + field)
    for field in ("dry_run_authorization_granted", "dry_run_authorized", "stage12633_authoritative_ledger_update_dry_run_only_allowed", "stage12633_allowed", "training_allowed"):
        if summary.get(field) is not False:
            raise SourcePacketReviewError("stage12632_gate_drift:" + field)
    if summary.get("authoritative_admitted_train_support_tasks_after_creation") != 158:
        raise SourcePacketReviewError("stage12632_count_drift")
    if summary.get("authoritative_gap_to_500_after_creation") != 342:
        raise SourcePacketReviewError("stage12632_gap_drift")
    return {"summary": summary, "contract": contract, "pointer": pointer, "private": private, "creation": creation, "packet": packet}


def build_review(stage12632: Mapping[str, Any]) -> dict[str, Any]:
    packet = stage12632["packet"]
    if packet.get("authorized_future_action") != "review_this_packet_before_any_candidate_ledger_dry_run":
        raise SourcePacketReviewError("source_packet_future_action_drift")
    if packet.get("packet_scope") != "candidate_ledger_dry_run_authority_source_packet_non_executable":
        raise SourcePacketReviewError("source_packet_scope_drift")
    for field in ("candidate_dry_run_authorization_granted_now", "dry_run_execution_allowed_now", "authoritative_ledger_update_allowed_now", "dataset_admission_allowed_now", "training_allowed_now", "vm_replay_allowed_now"):
        if packet.get(field) is not False:
            raise SourcePacketReviewError("source_packet_authority_drift:" + field)
    checks = [
        {"check_id": "source_packet_hash_pinned", "status": "passed"},
        {"check_id": "source_packet_present", "status": "passed"},
        {"check_id": "source_packet_is_non_executable", "status": "passed"},
        {"check_id": "source_packet_requests_review_before_dry_run", "status": "passed"},
        {"check_id": "source_packet_does_not_grant_dry_run", "status": "passed"},
        {"check_id": "source_packet_does_not_grant_update_admission_training_or_vm_replay", "status": "passed"},
        {"check_id": "dataset_counts_preserved", "status": "passed", "authoritative_count": 158, "authoritative_gap": 342},
        {"check_id": "review_scope_does_not_execute_or_materialize_candidate_artifacts", "status": "passed"},
    ]
    return {
        "record_type": "stage12633_authoritative_ledger_dry_run_authority_source_packet_independent_review_v1",
        "review_scope": "dry_run_authority_source_packet_independent_review_only",
        "reviewed_stage": "stage12632_authoritative_ledger_dry_run_authority_source_packet_creation_only",
        "reviewed_hashes": EXPECTED_HASHES,
        "review_checks": checks,
        "review_check_count": len(checks),
        "review_status": "independent_review_passed_packet_remains_non_authorizing",
        "dry_run_authorization_status": "not_granted_after_independent_source_packet_review",
        "source_packet_independent_review_conclusion": "packet_is_well_formed_non_executable_authority_source_but_not_authorization",
        "authoritative_count_after_review": 158,
        "authoritative_gap_after_review": 342,
        "conditional_candidate_count_if_later_authority_and_dry_run_pass": 190,
        "conditional_candidate_gap_if_later_authority_and_dry_run_pass": 310,
        "reviewed_plan_delta_total": 32,
        "candidate_artifacts_written": 0,
        "summary_artifacts_updated": 0,
        "dry_run_authority_source_packet_independent_review_only": True,
        "dry_run_authority_source_packet_present": True,
        "dry_run_authorization_granted": False,
        "dry_run_performed": False,
        "authoritative_ledger_update_performed": False,
        "new_admission_performed": False,
        "training_allowed_after_review": False,
    }


def build_packet(stage12632: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    review = build_review(stage12632)
    private = {
        "record_type": "stage12633_private_authoritative_ledger_dry_run_authority_source_packet_independent_review_only_v1",
        **no_claim_fields(),
        "source_hashes": EXPECTED_HASHES,
        "dry_run_authority_source_packet_independent_review_only": True,
        "dry_run_authority_source_packet_present": True,
        "vm_branch_remains_paused": True,
        "source_packet_independent_review": review,
        "decision": "DRY_RUN_AUTHORITY_SOURCE_PACKET_INDEPENDENT_REVIEW_PASSED_NO_DRY_RUN_AUTHORIZATION",
    }
    contract = {
        "record_type": "stage12633_public_authoritative_ledger_dry_run_authority_source_packet_independent_review_only_contract_v1",
        **no_claim_fields(),
        "stage12632_summary_sha256": EXPECTED_HASHES["stage12632_summary"],
        "stage12632_source_packet_creation_sha256": EXPECTED_HASHES["stage12632_source_packet_creation"],
        "authority_source_packet_sha256": EXPECTED_HASHES["stage12632_authority_source_packet"],
        "source_packet_independent_review_sha256": stable_hash(review),
        "private_source_packet_independent_review_sha256": stable_hash(private),
        "dry_run_authority_source_packet_independent_review_only": True,
        "dry_run_authority_source_packet_present": True,
        "vm_branch_remains_paused": True,
        "claim_boundary": {"source_packet": "independently_reviewed_as_non_executable_and_non_authorizing", "dry_run": "not_authorized_or_performed", "authoritative_ledger_update": "not_authorized", "new_admission": "not_authorized", "training": "not_authorized", "vm": "paused_not_used_for_packet_review", "replay": "not_executed", "level3": "not_materialized"},
    }
    summary = {
        "record_type": "stage12633_public_authoritative_ledger_dry_run_authority_source_packet_independent_review_only_summary_v1",
        **no_claim_fields(),
        "stage": STAGE,
        "decision": "DRY_RUN_AUTHORITY_SOURCE_PACKET_INDEPENDENT_REVIEW_PASSED_NO_DRY_RUN_AUTHORIZATION",
        "stage12632_summary_sha256": EXPECTED_HASHES["stage12632_summary"],
        "stage12632_source_packet_creation_sha256": EXPECTED_HASHES["stage12632_source_packet_creation"],
        "authority_source_packet_sha256": EXPECTED_HASHES["stage12632_authority_source_packet"],
        "source_packet_independent_review_sha256": stable_hash(review),
        "private_source_packet_independent_review_sha256": stable_hash(private),
        "dry_run_authority_source_packet_independent_review_only": True,
        "dry_run_authority_source_packet_present": True,
        "vm_branch_remains_paused": True,
        "review_status": "independent_review_passed_packet_remains_non_authorizing",
        "dry_run_authorization_status": "not_granted_after_independent_source_packet_review",
        "authoritative_admitted_train_support_tasks_after_review": 158,
        "authoritative_gap_to_500_after_review": 342,
        "conditional_candidate_count_if_later_authority_and_dry_run_pass": 190,
        "conditional_candidate_gap_if_later_authority_and_dry_run_pass": 310,
        "reviewed_plan_delta_total": 32,
        "candidate_artifacts_written": 0,
        "summary_artifacts_updated": 0,
        "frontier_100m_training_dataset_ready": False,
        "downstream_blockers": ["dry_run_authorization_not_granted", "candidate_ledger_dry_run_not_materialized", "candidate_ledger_artifacts_not_written", "authoritative_ledger_not_updated_in_stage12633", "new_train_support_rows_not_admitted", "authoritative_gap_still_342", "training_admission_forbidden"],
        "next_required_action": "separate_dry_run_authorization_decision_before_any_candidate_ledger_dry_run",
    }
    for label, record in (("summary", summary), ("contract", contract)):
        check_false(record, "stage12633_" + label)
        assert_public_sanitized(record, "stage12633_" + label)
    check_false(private, "stage12633_private")
    return summary, contract, private


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    stage12632 = load_stage12632()
    summary, contract, private = build_packet(stage12632)
    pointer = {
        "record_type": "stage12633_public_private_authoritative_ledger_dry_run_authority_source_packet_independent_review_pointer_v1",
        **no_claim_fields(),
        "stage12632_summary_sha256": EXPECTED_HASHES["stage12632_summary"],
        "contract_sha256": stable_hash(contract),
        "private_source_packet_independent_review_sha256": stable_hash(private),
        "source_packet_independent_review_sha256": stable_hash(private["source_packet_independent_review"]),
        "dry_run_authority_source_packet_independent_review_only": True,
        "dry_run_authority_source_packet_present": True,
        "vm_branch_remains_paused": True,
    }
    check_false(pointer, "stage12633_pointer")
    assert_public_sanitized(pointer, "stage12633_pointer")
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "private/authoritative_ledger_dry_run_authority_source_packet_independent_review_only.json", private)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
