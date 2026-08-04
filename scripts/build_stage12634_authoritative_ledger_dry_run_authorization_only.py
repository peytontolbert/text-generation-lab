#!/usr/bin/env python3
# Build Stage12634 scoped authorization for candidate-ledger dry run only.
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12634_authoritative_ledger_dry_run_authorization_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
S12627 = ROOT / "runs/local/artifacts/stage12627_authoritative_ledger_update_dry_run_preflight_review_only"
S12627_SUMMARY = ROOT / "runs/summaries/stage12627_authoritative_ledger_update_dry_run_preflight_review_only.json"
S12633 = ROOT / "runs/local/artifacts/stage12633_authoritative_ledger_dry_run_authority_source_packet_independent_review_only"
S12633_SUMMARY = ROOT / "runs/summaries/stage12633_authoritative_ledger_dry_run_authority_source_packet_independent_review_only.json"

EXPECTED_HASHES = {
    "stage12627_summary": "507f96995c23b4cbe9f50754087a6fb0220bd51ae47969a65cf6f1e80f953309",
    "stage12627_private": "0794476e65f53fe2f80572e1e80d91cd3a2ae5065da5efc6c9bafbf595da44a0",
    "stage12627_preflight_review": "c179438a28968df23d51a0b25b0f0f00082af83f45721d499f52343eb4d9e59f",
    "stage12633_summary": "bda8fb4592e96eb1aff798463aa4b36b3dc03ff122c2a8d92b3dfddfff5a4f11",
    "stage12633_contract": "f811707c1cea3737e506b7849a7562de63e9a9a818b4963ef9cca95dd796ff6f",
    "stage12633_pointer": "7aa55f7fe7d6d6fd521ae477059406212a0ff6155c21678e7fe2eb8243428cc8",
    "stage12633_private": "f7964e8ce582b300a24e3b5bafd97ee70e68dd0c18bb4fab1b79c29671fd4a72",
    "stage12633_source_packet_review": "e7d81c2b2037560c7bd8574743130abe41d8faa1e0384e41d543906d557e33fb",
    "stage12626_update_plan": "2ebc45d3c86e6a51d3011b8b5b95f6bb7c19823cbaa54d8815ebffea66e24f99",
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
    "authoritative_ledger_update_allowed", "authoritative_ledger_dry_run_performed",
    "authoritative_ledger_update_dry_run_materialized", "row_artifacts_written", "summary_artifact_written",
    "ledger_update_materialized", "candidate_ledger_materialized", "candidate_rows_materialized",
    "dry_run_candidate_artifacts_written", "dry_run_ready",
)
PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "agentkernel_vm_replay", "/dev/", "selector", "raw_stream", "stdout.raw", "stderr.raw",
    "before_commit_oid", "after_commit_oid", "production_path", "production_patch_sha256", "manual_executor_slot_contracts",
    "slot_1.patch", "slot_2.patch", "repository_root", "patch_path", "slot_1/", "slot_2/", "combined_selected_test_rows",
    "combined_train_support_rows", "direct_verifier_log_train_support_manifest", "direct_verifier_log_train_support_rows",
    "guardrail_scan.json", "combined_train_support_ledger", "jsonl", "row_id", "stable_lineage_key",
)


class DryRunAuthorizationError(RuntimeError):
    pass


def stable_hash(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise DryRunAuthorizationError("json_object_required:" + path.name)
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
            raise DryRunAuthorizationError(f"{label}_gate_drift:{field}")


def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise DryRunAuthorizationError(f"{label}_public_leak:{needle}")


def load_predecessors() -> dict[str, Any]:
    s12627_summary = read_json(S12627 / "summary.json")
    s12627_external = read_json(S12627_SUMMARY)
    s12627_private = read_json(S12627 / "private/authoritative_ledger_dry_run_preflight_review_only.json")
    s12633_summary = read_json(S12633 / "summary.json")
    s12633_external = read_json(S12633_SUMMARY)
    s12633_contract = read_json(S12633 / "contract.json")
    s12633_pointer = read_json(S12633 / "digest_pointer.json")
    s12633_private = read_json(S12633 / "private/authoritative_ledger_dry_run_authority_source_packet_independent_review_only.json")
    if s12627_summary != s12627_external:
        raise DryRunAuthorizationError("stage12627_external_summary_mismatch")
    if s12633_summary != s12633_external:
        raise DryRunAuthorizationError("stage12633_external_summary_mismatch")
    values = {
        "stage12627_summary": s12627_summary,
        "stage12627_private": s12627_private,
        "stage12633_summary": s12633_summary,
        "stage12633_contract": s12633_contract,
        "stage12633_pointer": s12633_pointer,
        "stage12633_private": s12633_private,
    }
    for label, value in values.items():
        if stable_hash(value) != EXPECTED_HASHES[label]:
            raise DryRunAuthorizationError("predecessor_pin_drift:" + label)
    preflight = s12627_private.get("dry_run_preflight_review") or {}
    review = s12633_private.get("source_packet_independent_review") or {}
    if stable_hash(preflight) != EXPECTED_HASHES["stage12627_preflight_review"]:
        raise DryRunAuthorizationError("stage12627_preflight_review_hash_drift")
    if stable_hash(review) != EXPECTED_HASHES["stage12633_source_packet_review"]:
        raise DryRunAuthorizationError("stage12633_source_packet_review_hash_drift")
    if s12627_summary.get("review_status") != "preflight_requirements_complete_but_dry_run_not_authorized":
        raise DryRunAuthorizationError("stage12627_preflight_status_drift")
    if s12633_summary.get("review_status") != "independent_review_passed_packet_remains_non_authorizing":
        raise DryRunAuthorizationError("stage12633_review_status_drift")
    if s12633_summary.get("next_required_action") != "separate_dry_run_authorization_decision_before_any_candidate_ledger_dry_run":
        raise DryRunAuthorizationError("stage12633_next_action_drift")
    for summary, label in ((s12627_summary, "stage12627"), (s12633_summary, "stage12633")):
        for field in ("dry_run_authorization_granted", "dry_run_authorized", "authoritative_ledger_dry_run_performed", "authoritative_ledger_updated", "training_allowed"):
            if field in summary and summary[field] is not False:
                raise DryRunAuthorizationError(f"{label}_gate_drift:{field}")
    return {"preflight": preflight, "source_packet_review": review, "stage12627_summary": s12627_summary, "stage12633_summary": s12633_summary}


def build_authorization(predecessors: Mapping[str, Any]) -> dict[str, Any]:
    preflight = predecessors["preflight"]
    review = predecessors["source_packet_review"]
    if preflight.get("conditional_candidate_count_if_later_dry_run_and_update_authorized") != 190:
        raise DryRunAuthorizationError("preflight_candidate_count_drift")
    if review.get("conditional_candidate_count_if_later_authority_and_dry_run_pass") != 190:
        raise DryRunAuthorizationError("source_packet_review_candidate_count_drift")
    checks = [
        {"check_id": "dry_run_preflight_review_pinned", "status": "passed"},
        {"check_id": "source_packet_independent_review_pinned", "status": "passed"},
        {"check_id": "candidate_source_rows_pinned_for_later_dry_run", "status": "passed"},
        {"check_id": "authorization_scope_is_candidate_dry_run_only", "status": "passed"},
        {"check_id": "authoritative_update_admission_training_eval_replay_level3_forbidden", "status": "passed"},
    ]
    return {
        "record_type": "stage12634_authoritative_ledger_dry_run_authorization_v1",
        "authorization_scope": "candidate_ledger_dry_run_only",
        "authorized_next_stage": "stage12635_authoritative_ledger_update_dry_run_materialization_only",
        "authorization_checks": checks,
        "authorization_check_count": len(checks),
        "authorization_status": "candidate_ledger_dry_run_authorized_no_authoritative_update_or_admission",
        "authoritative_count_at_authorization": 158,
        "authoritative_gap_at_authorization": 342,
        "authorized_candidate_count": 190,
        "authorized_candidate_gap": 310,
        "authorized_delta_total": 32,
        "candidate_rows_source_sha256": EXPECTED_HASHES["stage12417_rows_bytes"],
        "candidate_ledger_source_sha256": EXPECTED_HASHES["stage12417_ledger"],
        "candidate_guardrail_source_sha256": EXPECTED_HASHES["stage12417_guardrail_bytes"],
        "dry_run_authorization_decision_only": True,
        "dry_run_authorization_granted": True,
        "dry_run_authorized": True,
        "authoritative_ledger_dry_run_allowed": True,
        "stage12635_authoritative_ledger_update_dry_run_only_allowed": True,
        "dry_run_performed": False,
        "authoritative_ledger_update_performed": False,
        "new_admission_performed": False,
        "training_allowed_after_authorization": False,
    }


def build_packet(predecessors: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    authorization = build_authorization(predecessors)
    true_fields = {
        "dry_run_authorization_decision_only": True,
        "dry_run_authorization_granted": True,
        "dry_run_authorized": True,
        "authoritative_ledger_dry_run_allowed": True,
        "stage12635_authoritative_ledger_update_dry_run_only_allowed": True,
        "vm_branch_remains_paused": True,
    }
    private = {
        "record_type": "stage12634_private_authoritative_ledger_dry_run_authorization_only_v1",
        **no_claim_fields(),
        **true_fields,
        "source_hashes": EXPECTED_HASHES,
        "dry_run_authorization": authorization,
        "decision": "CANDIDATE_LEDGER_DRY_RUN_AUTHORIZED_NO_AUTHORITATIVE_UPDATE_OR_ADMISSION",
    }
    contract = {
        "record_type": "stage12634_public_authoritative_ledger_dry_run_authorization_only_contract_v1",
        **no_claim_fields(),
        **true_fields,
        "stage12627_preflight_review_sha256": EXPECTED_HASHES["stage12627_preflight_review"],
        "stage12633_source_packet_review_sha256": EXPECTED_HASHES["stage12633_source_packet_review"],
        "dry_run_authorization_sha256": stable_hash(authorization),
        "private_dry_run_authorization_sha256": stable_hash(private),
        "claim_boundary": {"authorization": "candidate_ledger_dry_run_only", "candidate_materialization": "not_performed_in_stage12634", "authoritative_ledger_update": "not_authorized", "new_admission": "not_authorized", "training": "not_authorized", "eval": "not_authorized", "vm": "paused_not_used_for_authorization", "replay": "not_executed", "level3": "not_materialized"},
    }
    summary = {
        "record_type": "stage12634_public_authoritative_ledger_dry_run_authorization_only_summary_v1",
        **no_claim_fields(),
        **true_fields,
        "stage": STAGE,
        "decision": "CANDIDATE_LEDGER_DRY_RUN_AUTHORIZED_NO_AUTHORITATIVE_UPDATE_OR_ADMISSION",
        "stage12627_preflight_review_sha256": EXPECTED_HASHES["stage12627_preflight_review"],
        "stage12633_source_packet_review_sha256": EXPECTED_HASHES["stage12633_source_packet_review"],
        "dry_run_authorization_sha256": stable_hash(authorization),
        "private_dry_run_authorization_sha256": stable_hash(private),
        "authorization_status": "candidate_ledger_dry_run_authorized_no_authoritative_update_or_admission",
        "authoritative_admitted_train_support_tasks_after_authorization": 158,
        "authoritative_gap_to_500_after_authorization": 342,
        "authorized_candidate_count": 190,
        "authorized_candidate_gap": 310,
        "authorized_delta_total": 32,
        "candidate_artifacts_written": 0,
        "summary_artifacts_updated": 0,
        "frontier_100m_training_dataset_ready": False,
        "downstream_blockers": ["candidate_ledger_dry_run_not_materialized", "authoritative_ledger_not_updated_in_stage12634", "new_train_support_rows_not_admitted", "authoritative_gap_still_342", "training_admission_forbidden"],
        "next_required_action": "stage12635_candidate_ledger_dry_run_materialization_only",
    }
    for label, record in (("summary", summary), ("contract", contract)):
        check_false(record, "stage12634_" + label)
        assert_public_sanitized(record, "stage12634_" + label)
    check_false(private, "stage12634_private")
    return summary, contract, private


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    predecessors = load_predecessors()
    summary, contract, private = build_packet(predecessors)
    pointer = {
        "record_type": "stage12634_public_private_authoritative_ledger_dry_run_authorization_pointer_v1",
        **no_claim_fields(),
        "stage12633_summary_sha256": EXPECTED_HASHES["stage12633_summary"],
        "contract_sha256": stable_hash(contract),
        "private_dry_run_authorization_sha256": stable_hash(private),
        "dry_run_authorization_sha256": stable_hash(private["dry_run_authorization"]),
        "dry_run_authorization_decision_only": True,
        "dry_run_authorization_granted": True,
        "dry_run_authorized": True,
        "authoritative_ledger_dry_run_allowed": True,
        "stage12635_authoritative_ledger_update_dry_run_only_allowed": True,
        "vm_branch_remains_paused": True,
    }
    check_false(pointer, "stage12634_pointer")
    assert_public_sanitized(pointer, "stage12634_pointer")
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "private/authoritative_ledger_dry_run_authorization_only.json", private)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
