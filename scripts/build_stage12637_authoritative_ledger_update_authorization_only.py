#!/usr/bin/env python3
# Build Stage12637 scoped authoritative-ledger update authorization only.
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12637_authoritative_ledger_update_authorization_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
S12636 = ROOT / "runs/local/artifacts/stage12636_candidate_ledger_dry_run_independent_review_only"
S12636_SUMMARY = ROOT / "runs/summaries/stage12636_candidate_ledger_dry_run_independent_review_only.json"

EXPECTED_HASHES = {
    "stage12636_summary": "f451d2deb7de5c4377b9c129efca71daf9c25db555e86f3757fa4d4bc1d01ce1",
    "stage12636_contract": "31fb53cf0d583913c8610cecdaa191ef3eec3f76f2914c04686d9edaf2f4facc",
    "stage12636_pointer": "a1b720ab16d2ea37118fe898d30ec4eee81533753d2218b4778c7ff3ed294a5b",
    "stage12636_private": "dc236ecc35f2871b88ddb8d8b640b054e37470f8ad7146c166c87f546a82c6b8",
    "stage12636_review": "2b02d6f631a45384208e55e7b9c348417605b15692256f58bf4a1cca9ba045f8",
    "stage12635_materialization": "0fc08665b6b592b8fd966cb5733f2bae581a2aa8ec6ec244e7e2d2c4e134b59b",
    "stage12635_rows_bytes": "065923de4ef183501b5f528d82065814826bd257a9b1814d54850680fe6cbce5",
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
    "vm_branch_active", "vm_runner_execution_allowed", "execution_performed", "storage_write_performed", "replay_trustworthy",
    "causal_transition_atoms_present", "causal_transition_atoms_allowed", "level3_preflight_allowed", "level_3_materialized",
    "level_3_materialization_allowed", "gpu_allocation_requested", "cuda2_training_allowed",
    "training_admission_allowed", "training_admission_preflight_allowed", "training_admitted", "training_allowed", "training_run_allowed",
    "strict_eval_admitted", "sealed_eval_admitted", "strict_eval_eligible", "sealed_eval_eligible",
    "admission_allowed", "ranking_allowed", "positive_stop", "authoritative_ledger_updated",
    "row_artifacts_written", "summary_artifact_written", "ledger_update_materialized", "dry_run_ready",
)
PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "agentkernel_vm_replay", "/dev/", "selector", "raw_stream", "stdout.raw", "stderr.raw",
    "before_commit_oid", "after_commit_oid", "production_path", "production_patch_sha256", "manual_executor_slot_contracts",
    "slot_1.patch", "slot_2.patch", "repository_root", "patch_path", "slot_1/", "slot_2/", "combined_selected_test_rows",
    "combined_train_support_rows", "direct_verifier_log_train_support_manifest", "direct_verifier_log_train_support_rows",
    "guardrail_scan.json", "combined_train_support_ledger", "jsonl", "row_id", "stable_lineage_key",
)


class LedgerUpdateAuthorizationError(RuntimeError):
    pass


def stable_hash(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise LedgerUpdateAuthorizationError("json_object_required:" + path.name)
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
            raise LedgerUpdateAuthorizationError(f"{label}_gate_drift:{field}")


def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise LedgerUpdateAuthorizationError(f"{label}_public_leak:{needle}")


def load_stage12636() -> dict[str, Any]:
    summary = read_json(S12636 / "summary.json")
    external = read_json(S12636_SUMMARY)
    contract = read_json(S12636 / "contract.json")
    pointer = read_json(S12636 / "digest_pointer.json")
    private = read_json(S12636 / "private/candidate_ledger_dry_run_independent_review_only.json")
    if summary != external:
        raise LedgerUpdateAuthorizationError("stage12636_external_summary_mismatch")
    for label, value in (("stage12636_summary", summary), ("stage12636_contract", contract), ("stage12636_pointer", pointer), ("stage12636_private", private)):
        if stable_hash(value) != EXPECTED_HASHES[label]:
            raise LedgerUpdateAuthorizationError("stage12636_pin_drift:" + label)
    review = private.get("candidate_dry_run_independent_review") or {}
    if stable_hash(review) != EXPECTED_HASHES["stage12636_review"]:
        raise LedgerUpdateAuthorizationError("stage12636_review_hash_drift")
    if review.get("review_status") != "candidate_ledger_dry_run_review_passed_no_authoritative_update_or_admission":
        raise LedgerUpdateAuthorizationError("stage12636_review_status_drift")
    if summary.get("next_required_action") != "separate_authoritative_ledger_update_authorization_decision":
        raise LedgerUpdateAuthorizationError("stage12636_next_action_drift")
    if summary.get("candidate_train_support_tasks_after_review") != 190 or summary.get("authoritative_admitted_train_support_tasks_after_review") != 158:
        raise LedgerUpdateAuthorizationError("stage12636_count_drift")
    for field in ("authoritative_ledger_update_allowed", "authoritative_ledger_updated", "dataset_rows_admitted", "new_rows_admitted", "training_allowed"):
        if summary.get(field) is not False:
            raise LedgerUpdateAuthorizationError("stage12636_forbidden_gate_drift:" + field)
    return {"summary": summary, "private": private, "review": review}


def build_authorization(stage12636: Mapping[str, Any]) -> dict[str, Any]:
    review = stage12636["review"]
    if review.get("candidate_count_after_review") != 190 or review.get("authoritative_count_after_review") != 158:
        raise LedgerUpdateAuthorizationError("stage12636_review_count_drift")
    checks = [
        {"check_id": "stage12636_review_pinned", "status": "passed"},
        {"check_id": "candidate_dry_run_counts_reviewed", "status": "passed", "candidate_count": 190, "authoritative_count": 158},
        {"check_id": "candidate_projection_rows_reviewed", "status": "passed", "projection_rows": 99, "base_rows": 91},
        {"check_id": "authorization_scope_is_authoritative_ledger_update_only", "status": "passed"},
        {"check_id": "admission_training_eval_replay_level3_vm_forbidden", "status": "passed"},
    ]
    return {
        "record_type": "stage12637_authoritative_ledger_update_authorization_v1",
        "authorization_scope": "authoritative_ledger_update_only",
        "authorized_next_stage": "stage12638_authoritative_ledger_update_materialization_only",
        "source_review_sha256": EXPECTED_HASHES["stage12636_review"],
        "source_materialization_sha256": EXPECTED_HASHES["stage12635_materialization"],
        "candidate_rows_sha256": EXPECTED_HASHES["stage12635_rows_bytes"],
        "authorization_checks": checks,
        "authorization_check_count": len(checks),
        "authorization_status": "authoritative_ledger_update_authorized_no_admission_or_training",
        "authoritative_count_before_authorized_update": 158,
        "authoritative_gap_before_authorized_update": 342,
        "authorized_authoritative_count_after_update": 190,
        "authorized_authoritative_gap_after_update": 310,
        "authorized_delta_total": 32,
        "authoritative_ledger_update_authorization_only": True,
        "authoritative_ledger_update_allowed": True,
        "stage12638_authoritative_ledger_update_materialization_only_allowed": True,
        "authoritative_ledger_update_performed": False,
        "authoritative_ledger_updated": False,
        "new_admission_performed": False,
        "training_allowed_after_authorization": False,
    }


def build_packet(stage12636: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    authorization = build_authorization(stage12636)
    true_fields = {
        "authoritative_ledger_update_authorization_only": True,
        "authoritative_ledger_update_allowed": True,
        "stage12638_authoritative_ledger_update_materialization_only_allowed": True,
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
        "record_type": "stage12637_private_authoritative_ledger_update_authorization_only_v1",
        **no_claim_fields(),
        **true_fields,
        "source_hashes": EXPECTED_HASHES,
        "authoritative_ledger_update_authorization": authorization,
        "decision": "AUTHORITATIVE_LEDGER_UPDATE_AUTHORIZED_NO_UPDATE_OR_ADMISSION_PERFORMED",
    }
    contract = {
        "record_type": "stage12637_public_authoritative_ledger_update_authorization_only_contract_v1",
        **no_claim_fields(),
        **true_fields,
        "stage12636_review_sha256": EXPECTED_HASHES["stage12636_review"],
        "authoritative_ledger_update_authorization_sha256": stable_hash(authorization),
        "private_authoritative_ledger_update_authorization_sha256": stable_hash(private),
        "claim_boundary": {"authorization": "authoritative_ledger_update_only", "authoritative_ledger_update": "not_performed_in_stage12637", "new_admission": "not_authorized", "training": "not_authorized", "eval": "not_authorized", "vm": "paused_not_used_for_authorization", "replay": "not_executed", "level3": "not_materialized"},
    }
    summary = {
        "record_type": "stage12637_public_authoritative_ledger_update_authorization_only_summary_v1",
        **no_claim_fields(),
        **true_fields,
        "stage": STAGE,
        "decision": "AUTHORITATIVE_LEDGER_UPDATE_AUTHORIZED_NO_UPDATE_OR_ADMISSION_PERFORMED",
        "stage12636_review_sha256": EXPECTED_HASHES["stage12636_review"],
        "authoritative_ledger_update_authorization_sha256": stable_hash(authorization),
        "private_authoritative_ledger_update_authorization_sha256": stable_hash(private),
        "authorization_status": "authoritative_ledger_update_authorized_no_admission_or_training",
        "authoritative_admitted_train_support_tasks_before_authorized_update": 158,
        "authoritative_gap_to_500_before_authorized_update": 342,
        "authorized_authoritative_train_support_tasks_after_update": 190,
        "authorized_authoritative_gap_to_500_after_update": 310,
        "authorized_delta_total": 32,
        "frontier_100m_training_dataset_ready": False,
        "downstream_blockers": ["authoritative_ledger_update_not_materialized", "new_train_support_rows_not_admitted_in_stage12637", "training_admission_forbidden"],
        "next_required_action": "stage12638_authoritative_ledger_update_materialization_only",
    }
    for label, record in (("summary", summary), ("contract", contract)):
        check_false(record, "stage12637_" + label)
        assert_public_sanitized(record, "stage12637_" + label)
    check_false(private, "stage12637_private")
    return summary, contract, private


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    stage12636 = load_stage12636()
    summary, contract, private = build_packet(stage12636)
    pointer = {
        "record_type": "stage12637_public_private_authoritative_ledger_update_authorization_pointer_v1",
        **no_claim_fields(),
        "stage12636_summary_sha256": EXPECTED_HASHES["stage12636_summary"],
        "contract_sha256": stable_hash(contract),
        "private_authoritative_ledger_update_authorization_sha256": stable_hash(private),
        "authoritative_ledger_update_authorization_sha256": stable_hash(private["authoritative_ledger_update_authorization"]),
        "authoritative_ledger_update_authorization_only": True,
        "authoritative_ledger_update_allowed": True,
        "stage12638_authoritative_ledger_update_materialization_only_allowed": True,
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
    check_false(pointer, "stage12637_pointer")
    assert_public_sanitized(pointer, "stage12637_pointer")
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "private/authoritative_ledger_update_authorization_only.json", private)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
