#!/usr/bin/env python3
"""Build Stage12627 authoritative ledger dry-run preflight review only.

Stage12626 recorded a ledger-update plan and explicitly did not authorize a dry
run. This stage reviews the dry-run preconditions described by that plan. It does
not perform a dry run, write candidate ledger files, update the authoritative
ledger, admit rows, train, resume VM/replay, materialize Level-3, or authorize a
successor stage.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12627_authoritative_ledger_update_dry_run_preflight_review_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
S12626 = ROOT / "runs/local/artifacts/stage12626_authoritative_ledger_update_plan_only"
S12626_SUMMARY = ROOT / "runs/summaries/stage12626_authoritative_ledger_update_plan_only.json"
EXPECTED_HASHES = {
    "stage12626_summary": "1d52e79c814995a09a522fa93a71a3452d133cb06bce7cd45ec93ccb9702a072",
    "stage12626_contract": "3e997555c7f421111de5076c91f6bfb1c48097098d73b47395e50e4c9af551a6",
    "stage12626_pointer": "7f0e0a136e50ff30f637c36c878d0c0a4aeca3cd39fd396f39daa8c960f1db43",
    "stage12626_private": "d0398c3dfb0ab947cb57b69d4e88d987c3998a24b3407827904dd8b6b6e31709",
    "stage12626_update_plan": "2ebc45d3c86e6a51d3011b8b5b95f6bb7c19823cbaa54d8815ebffea66e24f99",
    "stage12376": "a7aa3bcae28c5741f1955d2b954744143266bb61d2e824d78343e932cc3b695e",
    "stage12417": "c9a872e36c12888b7f3fd45218cb69aa7d75b238378368289483ba54c483721a",
}

FALSE_FIELDS = (
    "implementation_ready", "dataset_admission_allowed", "dataset_rows_admitted", "new_rows_admitted",
    "frontier_100m_training_dataset_ready", "source_packet_implementation_allowed", "source_packet_executable",
    "stage12620_allowed", "stage12621_allowed", "stage12622_allowed", "stage12623_allowed", "stage12624_allowed",
    "stage12625_allowed", "stage12626_allowed", "stage12627_allowed", "stage12628_allowed",
    "stage12627_authoritative_ledger_update_dry_run_only_allowed", "stage12628_authoritative_ledger_dry_run_authorization_review_allowed",
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
)
PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "agentkernel_vm_replay", "/dev/", "selector", "raw_stream",
    "stdout.raw", "stderr.raw", "before_commit_oid", "after_commit_oid", "production_path",
    "production_patch_sha256", "manual_executor_slot_contracts", "slot_1.patch", "slot_2.patch",
    "repository_root", "patch_path", "slot_1/", "slot_2/", "combined_selected_test_rows",
    "combined_train_support_rows", "direct_verifier_log_train_support_manifest", "direct_verifier_log_train_support_rows",
    "guardrail_scan.json", "combined_train_support_ledger", "jsonl", "row_id", "stable_lineage_key",
)


class DryRunPreflightReviewError(RuntimeError):
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
        raise DryRunPreflightReviewError("json_object_required:" + path.name)
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
            raise DryRunPreflightReviewError(f"{label}_gate_drift:{field}")


def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise DryRunPreflightReviewError(f"{label}_public_leak:{needle}")


def load_stage12626() -> dict[str, Any]:
    summary = read_json(S12626 / "summary.json")
    external = read_json(S12626_SUMMARY)
    contract = read_json(S12626 / "contract.json")
    pointer = read_json(S12626 / "digest_pointer.json")
    private = read_json(S12626 / "private/authoritative_ledger_update_plan_only.json")
    if summary != external:
        raise DryRunPreflightReviewError("stage12626_external_summary_mismatch")
    for label, value in (
        ("stage12626_summary", summary),
        ("stage12626_contract", contract),
        ("stage12626_pointer", pointer),
        ("stage12626_private", private),
    ):
        if stable_hash(value) != EXPECTED_HASHES[label]:
            raise DryRunPreflightReviewError("stage12626_pin_drift:" + label)
    update_plan = private.get("update_plan") or {}
    if stable_hash(update_plan) != EXPECTED_HASHES["stage12626_update_plan"]:
        raise DryRunPreflightReviewError("stage12626_update_plan_hash_drift")
    if summary.get("stage12627_authoritative_ledger_update_dry_run_only_allowed") is not False:
        raise DryRunPreflightReviewError("stage12626_dry_run_authorization_drift")
    if summary.get("stage12627_allowed") is not False:
        raise DryRunPreflightReviewError("stage12626_broad_successor_gate_drift")
    if summary.get("authoritative_admitted_train_support_tasks_after_plan") != 158:
        raise DryRunPreflightReviewError("stage12626_authoritative_count_drift")
    if summary.get("authoritative_gap_to_500_after_plan") != 342:
        raise DryRunPreflightReviewError("stage12626_authoritative_gap_drift")
    requirements = update_plan.get("future_stage_requirements") or {}
    if requirements.get("minimum_next_review") != "stage12627_authoritative_ledger_update_dry_run_preflight_review":
        raise DryRunPreflightReviewError("stage12626_next_review_missing")
    if update_plan.get("authoritative_ledger_update_performed") is not False:
        raise DryRunPreflightReviewError("stage12626_update_performed_drift")
    return {"summary": summary, "contract": contract, "pointer": pointer, "private": private, "update_plan": update_plan}


def build_preflight_review(stage12626: Mapping[str, Any]) -> dict[str, Any]:
    plan = stage12626["update_plan"]
    invariants = plan.get("invariants") or {}
    future = plan.get("future_stage_requirements") or {}
    manifests = plan.get("private_manifest_requirements") or {}
    if invariants.get("authoritative_count_after_stage12626") != 158 or invariants.get("authoritative_gap_after_stage12626") != 342:
        raise DryRunPreflightReviewError("stage12626_invariant_count_drift")
    if invariants.get("planned_candidate_count_after_later_update") != 190 or invariants.get("planned_delta_total") != 32:
        raise DryRunPreflightReviewError("stage12626_candidate_plan_drift")
    if invariants.get("row_artifacts_to_write_now") != 0 or invariants.get("summary_artifacts_to_update_now") != 0:
        raise DryRunPreflightReviewError("stage12626_write_plan_drift")
    required_future_flags = (
        "dry_run_must_emit_candidate_files_only",
        "dry_run_must_not_replace_authoritative_summary",
        "dry_run_must_recompute_all_counts_from_pinned_rows",
        "dry_run_must_include_public_summary_diff",
        "dry_run_must_keep_training_admission_separate",
        "dry_run_must_materialize_private_manifest_requirements",
    )
    missing_future_flags = [flag for flag in required_future_flags if future.get(flag) is not True]
    if missing_future_flags:
        raise DryRunPreflightReviewError("stage12626_future_requirement_missing:" + ",".join(missing_future_flags))
    required_manifests = ("supersession_manifest", "direct_log_merge_manifest", "duplicate_policy_manifest")
    missing_manifests = [name for name in required_manifests if not (manifests.get(name) or {}).get("required")]
    if missing_manifests:
        raise DryRunPreflightReviewError("stage12626_private_manifest_requirement_missing:" + ",".join(missing_manifests))
    if manifests["supersession_manifest"].get("net_delta") != 14:
        raise DryRunPreflightReviewError("stage12626_supersession_delta_drift")
    if manifests["direct_log_merge_manifest"].get("direct_log_projection_rows") != 18:
        raise DryRunPreflightReviewError("stage12626_direct_log_delta_drift")
    if manifests["duplicate_policy_manifest"].get("post_update_duplicate_extra_rows_required") != 0:
        raise DryRunPreflightReviewError("stage12626_duplicate_policy_drift")
    review_checks = [
        {"check_id": "predecessor_has_no_dry_run_authorization", "status": "passed", "dry_run_allowed": False},
        {"check_id": "authoritative_counts_preserved", "status": "passed", "authoritative_count": 158, "authoritative_gap": 342},
        {"check_id": "future_candidate_counts_are_conditional", "status": "passed", "conditional_count": 190, "conditional_gap": 310},
        {"check_id": "private_manifest_requirements_present", "status": "passed", "required_private_manifest_count": 3},
        {"check_id": "dry_run_must_be_candidate_only", "status": "passed", "authoritative_replacement_allowed": False},
        {"check_id": "training_admission_stays_separate", "status": "passed", "training_allowed": False},
    ]
    return {
        "record_type": "stage12627_authoritative_ledger_dry_run_preflight_review_v1",
        "review_scope": "dry_run_preflight_review_only",
        "source_update_plan_sha256": EXPECTED_HASHES["stage12626_update_plan"],
        "review_checks": review_checks,
        "review_check_count": len(review_checks),
        "review_status": "preflight_requirements_complete_but_dry_run_not_authorized",
        "dry_run_authorization_status": "not_authorized_by_stage12626_or_stage12627",
        "authoritative_count_before_review": 158,
        "authoritative_gap_before_review": 342,
        "authoritative_count_after_review": 158,
        "authoritative_gap_after_review": 342,
        "conditional_candidate_count_if_later_dry_run_and_update_authorized": 190,
        "conditional_candidate_gap_if_later_dry_run_and_update_authorized": 310,
        "reviewed_plan_delta_total": 32,
        "reviewed_selected_lineage_delta": 14,
        "reviewed_direct_real_log_delta": 18,
        "stage12418_countable_rows": 0,
        "required_private_manifest_count": 3,
        "candidate_artifacts_written": 0,
        "summary_artifacts_updated": 0,
        "minimum_next_review": "stage12628_authoritative_ledger_dry_run_authorization_review_only",
        "dry_run_preflight_review_only": True,
        "dry_run_performed": False,
        "authoritative_ledger_update_performed": False,
        "new_admission_performed": False,
        "training_allowed_after_review": False,
    }


def build_packet(stage12626: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    review = build_preflight_review(stage12626)
    private = {
        "record_type": "stage12627_private_authoritative_ledger_dry_run_preflight_review_only_v1",
        **no_claim_fields(),
        "source_hashes": EXPECTED_HASHES,
        "dry_run_preflight_review_only": True,
        "vm_branch_remains_paused": True,
        "dry_run_preflight_review": review,
        "decision": "DRY_RUN_PREFLIGHT_REVIEW_RECORDED_NO_DRY_RUN_AUTHORIZATION",
    }
    contract = {
        "record_type": "stage12627_public_authoritative_ledger_dry_run_preflight_review_only_contract_v1",
        **no_claim_fields(),
        "stage12626_summary_sha256": EXPECTED_HASHES["stage12626_summary"],
        "stage12626_update_plan_sha256": EXPECTED_HASHES["stage12626_update_plan"],
        "stage12376_summary_sha256": EXPECTED_HASHES["stage12376"],
        "stage12417_summary_sha256": EXPECTED_HASHES["stage12417"],
        "dry_run_preflight_review_sha256": stable_hash(review),
        "private_dry_run_preflight_review_sha256": stable_hash(private),
        "dry_run_preflight_review_only": True,
        "vm_branch_remains_paused": True,
        "claim_boundary": {
            "review": "dry_run_preflight_review_only",
            "dry_run": "not_authorized_or_performed",
            "authoritative_ledger_update": "not_performed",
            "new_admission": "not_authorized",
            "training": "not_authorized",
            "vm": "paused_not_used_for_dry_run_review",
            "replay": "not_executed",
            "level3": "not_materialized",
        },
    }
    summary = {
        "record_type": "stage12627_public_authoritative_ledger_dry_run_preflight_review_only_summary_v1",
        **no_claim_fields(),
        "stage": STAGE,
        "decision": "DRY_RUN_PREFLIGHT_REVIEW_RECORDED_NO_DRY_RUN_AUTHORIZATION",
        "stage12626_summary_sha256": EXPECTED_HASHES["stage12626_summary"],
        "stage12626_update_plan_sha256": EXPECTED_HASHES["stage12626_update_plan"],
        "stage12376_summary_sha256": EXPECTED_HASHES["stage12376"],
        "stage12417_summary_sha256": EXPECTED_HASHES["stage12417"],
        "dry_run_preflight_review_sha256": stable_hash(review),
        "private_dry_run_preflight_review_sha256": stable_hash(private),
        "dry_run_preflight_review_only": True,
        "vm_branch_remains_paused": True,
        "review_status": "preflight_requirements_complete_but_dry_run_not_authorized",
        "dry_run_authorization_status": "not_authorized_by_stage12626_or_stage12627",
        "authoritative_admitted_train_support_tasks_after_review": 158,
        "authoritative_gap_to_500_after_review": 342,
        "conditional_candidate_count_if_later_authorized": 190,
        "conditional_candidate_gap_if_later_authorized": 310,
        "reviewed_plan_delta_total": 32,
        "reviewed_selected_lineage_delta": 14,
        "reviewed_direct_real_log_delta": 18,
        "stage12418_derived_projection_countable_rows": 0,
        "required_private_manifest_count": 3,
        "candidate_artifacts_written": 0,
        "summary_artifacts_updated": 0,
        "frontier_100m_training_dataset_ready": False,
        "downstream_blockers": [
            "dry_run_authorization_absent",
            "authoritative_ledger_update_dry_run_not_materialized",
            "candidate_ledger_artifacts_not_written",
            "authoritative_ledger_not_updated_in_stage12627",
            "new_train_support_rows_not_admitted",
            "authoritative_gap_still_342",
            "training_admission_forbidden",
        ],
    }
    for label, record in (("summary", summary), ("contract", contract)):
        check_false(record, "stage12627_" + label)
        assert_public_sanitized(record, "stage12627_" + label)
    check_false(private, "stage12627_private")
    return summary, contract, private


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    stage12626 = load_stage12626()
    summary, contract, private = build_packet(stage12626)
    pointer = {
        "record_type": "stage12627_public_private_authoritative_ledger_dry_run_preflight_review_pointer_v1",
        **no_claim_fields(),
        "stage12626_summary_sha256": EXPECTED_HASHES["stage12626_summary"],
        "contract_sha256": stable_hash(contract),
        "private_dry_run_preflight_review_sha256": stable_hash(private),
        "dry_run_preflight_review_sha256": stable_hash(private["dry_run_preflight_review"]),
        "dry_run_preflight_review_only": True,
        "vm_branch_remains_paused": True,
    }
    check_false(pointer, "stage12627_pointer")
    assert_public_sanitized(pointer, "stage12627_pointer")
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "private/authoritative_ledger_dry_run_preflight_review_only.json", private)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
