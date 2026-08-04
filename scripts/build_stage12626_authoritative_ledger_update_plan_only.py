#!/usr/bin/env python3
"""Build Stage12626 authoritative ledger update plan only.

Stage12625 reviewed the advisory 32-task delta and found it ready for a later
ledger-update plan. This stage records the exact update mechanics and dry-run
requirements. It does not write a new authoritative ledger, admit rows, run
training, resume VM/replay, materialize Level-3, or authorize broad successor
work.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12626_authoritative_ledger_update_plan_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
S12625 = ROOT / "runs/local/artifacts/stage12625_authoritative_ledger_reconciliation_review_only"
S12625_SUMMARY = ROOT / "runs/summaries/stage12625_authoritative_ledger_reconciliation_review_only.json"
EXPECTED_HASHES = {
    "stage12625_summary": "8ec649bac5d1846d6ac501f855ba814596afa0788ce21299556b49fcaa100ecb",
    "stage12625_contract": "e2bc2b7ad8cacab8073fa7aeea0f7b8d26c0017484ff233d222a39b3203fbe79",
    "stage12625_pointer": "f236daec0b7652edce1c0a8ebdaef9dc610ee428bdb57a8a8f5d45529637d84a",
    "stage12625_private": "f5c16ecff55f99ee247ef7da9592e5689614603cfc15b24486149d4803ac4620",
    "stage12376": "a7aa3bcae28c5741f1955d2b954744143266bb61d2e824d78343e932cc3b695e",
    "stage12385": "9a95e41cda6609ce7aee84d1a9aea409f06824b03d1f48a81fc74cbaafc55615",
    "stage12416": "35a01e25be81736b84a49da918e34448ddcc93e31cb57d207b765c74334228f6",
    "stage12417": "c9a872e36c12888b7f3fd45218cb69aa7d75b238378368289483ba54c483721a",
    "stage12419": "61b8a0541c06cec23ac06d75e5da9679c073d7615b97ee2257748049e4d5d954",
    "stage12376_rows": "df1bb6559b02bb834d736ff87cbbf30dc4e2e31b408243553c5c115895e35a25",
    "stage12385_rows": "a4116ba793d817b2b4d8cd9ce0c99c88b0a6a4e2496287f9ab5f9479a0bed92c",
    "stage12416_rows": "5d9e0daa04bbb829a55d8047a325bfd0655f15430e488caa9a1904cc53c5c9ae",
    "stage12416_guardrail": "7f069101a9fa734c90fa23c93a562dc8de9eb4fc8cc78eb6f90676c504b5ce8c",
    "stage12417_rows": "065923de4ef183501b5f528d82065814826bd257a9b1814d54850680fe6cbce5",
    "stage12417_guardrail": "7f069101a9fa734c90fa23c93a562dc8de9eb4fc8cc78eb6f90676c504b5ce8c",
}

FALSE_FIELDS = (
    "implementation_ready", "dataset_admission_allowed", "dataset_rows_admitted", "new_rows_admitted",
    "frontier_100m_training_dataset_ready", "source_packet_implementation_allowed", "source_packet_executable",
    "stage12620_allowed", "stage12621_allowed", "stage12622_allowed", "stage12623_allowed", "stage12624_allowed",
    "stage12625_allowed", "stage12626_allowed", "stage12627_allowed", "stage12627_authoritative_ledger_update_dry_run_only_allowed", "vm_branch_active",
    "vm_runner_implementation_allowed", "vm_runner_implementation_ready", "vm_runner_execution_allowed",
    "vm_runner_evidence_present", "vm_runner_trustworthy", "storage_root_created", "storage_write_performed",
    "execution_performed", "replay_trustworthy", "raw_replay_evidence_present", "trusted_replay_raw_evidence_present",
    "causal_transition_atoms_present", "causal_transition_atoms_allowed", "level3_preflight_allowed",
    "level_3_materialized", "level_3_materialization_allowed", "training_admission_preflight_allowed",
    "training_admission_allowed", "training_admitted", "training_allowed", "training_run_allowed",
    "gpu_allocation_requested", "cuda2_training_allowed", "strict_eval_admitted", "sealed_eval_admitted",
    "strict_eval_eligible", "sealed_eval_eligible", "admission_allowed", "ranking_allowed", "positive_stop",
    "authoritative_ledger_updated", "authoritative_ledger_update_allowed", "authoritative_ledger_dry_run_performed",
    "control_board_promoted_to_authoritative", "control_board_promotion_allowed", "row_artifacts_written",
    "summary_artifact_written", "ledger_update_materialized",
)
PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "agentkernel_vm_replay", "/dev/", "selector", "raw_stream",
    "stdout.raw", "stderr.raw", "before_commit_oid", "after_commit_oid", "production_path",
    "production_patch_sha256", "manual_executor_slot_contracts", "slot_1.patch", "slot_2.patch",
    "repository_root", "patch_path", "slot_1/", "slot_2/", "combined_selected_test_rows",
    "combined_train_support_rows", "direct_verifier_log_train_support_manifest", "direct_verifier_log_train_support_rows",
    "guardrail_scan.json", "combined_train_support_ledger", "jsonl",
)


class LedgerUpdatePlanError(RuntimeError):
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
        raise LedgerUpdatePlanError("json_object_required:" + path.name)
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
            raise LedgerUpdatePlanError(f"{label}_gate_drift:{field}")


def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise LedgerUpdatePlanError(f"{label}_public_leak:{needle}")


def load_stage12625() -> dict[str, Any]:
    summary = read_json(S12625 / "summary.json")
    external = read_json(S12625_SUMMARY)
    contract = read_json(S12625 / "contract.json")
    pointer = read_json(S12625 / "digest_pointer.json")
    private = read_json(S12625 / "private/authoritative_ledger_reconciliation_review_only.json")
    if summary != external:
        raise LedgerUpdatePlanError("stage12625_external_summary_mismatch")
    for label, value in (
        ("stage12625_summary", summary),
        ("stage12625_contract", contract),
        ("stage12625_pointer", pointer),
        ("stage12625_private", private),
    ):
        if stable_hash(value) != EXPECTED_HASHES[label]:
            raise LedgerUpdatePlanError("stage12625_pin_drift:" + label)
    if summary.get("stage12626_authoritative_ledger_update_plan_only_allowed") is not True:
        raise LedgerUpdatePlanError("stage12625_scoped_gate_missing")
    if summary.get("stage12626_allowed") is not False:
        raise LedgerUpdatePlanError("stage12625_broad_successor_gate_drift")
    if summary.get("authoritative_admitted_train_support_tasks_after_review") != 158:
        raise LedgerUpdatePlanError("stage12625_authoritative_count_drift")
    if summary.get("authoritative_gap_to_500_after_review") != 342:
        raise LedgerUpdatePlanError("stage12625_authoritative_gap_drift")
    if summary.get("review_passed_delta_total") != 32 or summary.get("review_blocked_delta_total") != 0:
        raise LedgerUpdatePlanError("stage12625_review_delta_drift")
    review = private.get("reconciliation_review") or {}
    if review.get("reconciliation_review_status") != "passed_for_later_update_plan_no_authoritative_ledger_update":
        raise LedgerUpdatePlanError("stage12625_review_status_drift")
    if private.get("row_artifact_hashes") != {key: EXPECTED_HASHES[key] for key in (
        "stage12376_rows", "stage12385_rows", "stage12416_rows", "stage12416_guardrail", "stage12417_rows", "stage12417_guardrail"
    )}:
        raise LedgerUpdatePlanError("stage12625_row_hashes_drift")
    return {"summary": summary, "contract": contract, "pointer": pointer, "private": private}


def build_update_plan(stage12625: Mapping[str, Any]) -> dict[str, Any]:
    review = stage12625["private"]["reconciliation_review"]
    if review.get("authoritative_ledger_update_performed") is not False:
        raise LedgerUpdatePlanError("stage12625_already_updated_drift")
    if review.get("reviewed_delta_total") != 32:
        raise LedgerUpdatePlanError("stage12625_review_total_drift")
    selected_component, direct_component = review["review_components"]
    if selected_component.get("net_task_delta") != 14 or direct_component.get("net_task_delta") != 18:
        raise LedgerUpdatePlanError("stage12625_component_delta_drift")
    plan_steps = [
        {
            "step_id": "pin_authoritative_baseline",
            "required_inputs": ["stage12376_summary", "stage12376_rows"],
            "required_checks": ["baseline_count_158", "baseline_gap_342", "prior_duplicate_extra_rows_10_recorded"],
            "writes_allowed_in_stage12626": False,
        },
        {
            "step_id": "apply_selected_lineage_supersession_plan",
            "required_inputs": ["stage12385_summary", "stage12385_rows"],
            "planned_delta": 14,
            "required_checks": ["30_added_row_ids", "6_superseded_row_ids", "10_prior_duplicate_extras_removed", "post_dedupe_duplicate_extra_rows_0"],
            "writes_allowed_in_stage12626": False,
        },
        {
            "step_id": "append_direct_real_log_projection_plan",
            "required_inputs": ["stage12416_summary", "stage12416_rows", "stage12416_guardrail"],
            "planned_delta": 18,
            "required_checks": ["18_rows_present", "duplicate_projection_count_0", "raw_leak_count_0", "overclaim_count_0", "no_repair_patch_level3_or_eval_claims"],
            "writes_allowed_in_stage12626": False,
        },
        {
            "step_id": "dry_run_merged_ledger_plan",
            "required_inputs": ["stage12417_summary", "stage12417_rows", "stage12417_guardrail"],
            "planned_count_if_future_update_authorized": 190,
            "planned_gap_if_future_update_authorized": 310,
            "required_checks": ["99_unique_projection_rows", "190_total_with_91_event_local_base", "guardrail_scan_passed", "stage12418_derived_projection_rows_excluded"],
            "writes_allowed_in_stage12626": False,
        },
        {
            "step_id": "publish_future_update_manifest_plan",
            "required_outputs_for_later_stage": ["merged_row_manifest", "supersession_manifest", "dedupe_manifest", "guardrail_manifest", "public_summary_diff"],
            "required_checks": ["public_no_private_paths", "all_training_and_eval_gates_false", "no_control_board_auto_promotion"],
            "writes_allowed_in_stage12626": False,
        },
    ]
    invariants = {
        "authoritative_count_before_stage12626": 158,
        "authoritative_gap_before_stage12626": 342,
        "authoritative_count_after_stage12626": 158,
        "authoritative_gap_after_stage12626": 342,
        "planned_candidate_count_after_later_update": 190,
        "planned_candidate_gap_after_later_update": 310,
        "planned_delta_total": 32,
        "stage12418_countable_rows": 0,
        "row_artifacts_to_write_now": 0,
        "summary_artifacts_to_update_now": 0,
    }
    private_manifest_requirements = {
        "supersession_manifest": {
            "required": True,
            "source_transition": "stage12376_to_stage12385",
            "rows_before": 67,
            "rows_after": 81,
            "row_ids_added": 30,
            "row_ids_removed_or_superseded": 6,
            "prior_duplicate_extra_rows_removed": 10,
            "net_delta": 14,
            "required_row_actions": ["keep", "add", "supersede", "drop_duplicate"],
            "per_changed_row_fields": ["stable_lineage_key", "action", "reason", "source_component", "dedupe_key_family"],
            "publicly_emitted": False,
        },
        "direct_log_merge_manifest": {
            "required": True,
            "source_transition": "stage12385_plus_stage12416_to_stage12417",
            "direct_log_projection_rows": 18,
            "all_rows_must_be_present_in_stage12417": True,
            "required_row_actions": ["append_projection", "dedupe_check"],
            "forbidden_claims": ["repair", "level3", "fail_to_pass", "strict_eval", "sealed_eval"],
            "publicly_emitted": False,
        },
        "duplicate_policy_manifest": {
            "required": True,
            "stage12385_policy": "row_id_dedupe_removed_10_prior_duplicate_extras",
            "stage12417_policy": "multi_key_dedupe_by_row_id_source_key_audit_hash_root_projection_target",
            "post_update_duplicate_extra_rows_required": 0,
            "publicly_emitted": False,
        },
    }
    future_stage_requirements = {
        "minimum_next_review": "stage12627_authoritative_ledger_update_dry_run_preflight_review",
        "dry_run_must_emit_candidate_files_only": True,
        "dry_run_must_not_replace_authoritative_summary": True,
        "dry_run_must_recompute_all_counts_from_pinned_rows": True,
        "dry_run_must_include_public_summary_diff": True,
        "dry_run_must_keep_training_admission_separate": True,
        "dry_run_must_materialize_private_manifest_requirements": True,
    }
    return {
        "record_type": "stage12626_authoritative_ledger_update_plan_v1",
        "plan_scope": "authoritative_ledger_update_plan_only",
        "source_review_sha256": stage12625["summary"]["reconciliation_review_sha256"],
        "private_source_review_sha256": stage12625["summary"]["private_reconciliation_review_sha256"],
        "update_plan_steps": plan_steps,
        "update_plan_step_count": len(plan_steps),
        "planned_update_components": [
            {
                "component_id": "selected_lineage_supersession",
                "planned_delta": 14,
                "row_ids_added": 30,
                "row_ids_removed_or_superseded": 6,
                "prior_duplicate_extra_rows_removed": 10,
                "materialization_status": "not_materialized_plan_only",
            },
            {
                "component_id": "direct_real_log_projection_merge",
                "planned_delta": 18,
                "projection_rows": 18,
                "guardrail_status": "passed_in_pinned_sources",
                "materialization_status": "not_materialized_plan_only",
            },
        ],
        "invariants": invariants,
        "private_manifest_requirements": private_manifest_requirements,
        "future_stage_requirements": future_stage_requirements,
        "authoritative_ledger_update_plan_only": True,
        "authoritative_ledger_update_performed": False,
        "new_admission_performed": False,
        "training_allowed_after_plan": False,
    }


def build_packet(stage12625: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    plan = build_update_plan(stage12625)
    private = {
        "record_type": "stage12626_private_authoritative_ledger_update_plan_only_v1",
        **no_claim_fields(),
        "source_hashes": EXPECTED_HASHES,
        "authoritative_ledger_update_plan_only": True,
        "vm_branch_remains_paused": True,
        "stage12627_authoritative_ledger_update_dry_run_only_allowed": False,
        "update_plan": plan,
        "decision": "AUTHORITATIVE_LEDGER_UPDATE_PLAN_RECORDED_NO_LEDGER_UPDATE_OR_ADMISSION",
    }
    contract = {
        "record_type": "stage12626_public_authoritative_ledger_update_plan_only_contract_v1",
        **no_claim_fields(),
        "stage12625_summary_sha256": EXPECTED_HASHES["stage12625_summary"],
        "stage12376_summary_sha256": EXPECTED_HASHES["stage12376"],
        "stage12417_summary_sha256": EXPECTED_HASHES["stage12417"],
        "update_plan_sha256": stable_hash(plan),
        "private_update_plan_sha256": stable_hash(private),
        "authoritative_ledger_update_plan_only": True,
        "vm_branch_remains_paused": True,
        "stage12627_authoritative_ledger_update_dry_run_only_allowed": False,
        "claim_boundary": {
            "plan": "authoritative_ledger_update_plan_only",
            "authoritative_ledger_update": "not_performed",
            "dry_run": "not_performed",
            "new_admission": "not_authorized",
            "training": "not_authorized",
            "vm": "paused_not_used_for_update_plan",
            "replay": "not_executed",
            "level3": "not_materialized",
        },
    }
    summary = {
        "record_type": "stage12626_public_authoritative_ledger_update_plan_only_summary_v1",
        **no_claim_fields(),
        "stage": STAGE,
        "decision": "AUTHORITATIVE_LEDGER_UPDATE_PLAN_RECORDED_NO_LEDGER_UPDATE_OR_ADMISSION",
        "stage12625_summary_sha256": EXPECTED_HASHES["stage12625_summary"],
        "stage12376_summary_sha256": EXPECTED_HASHES["stage12376"],
        "stage12417_summary_sha256": EXPECTED_HASHES["stage12417"],
        "update_plan_sha256": stable_hash(plan),
        "private_update_plan_sha256": stable_hash(private),
        "authoritative_ledger_update_plan_only": True,
        "vm_branch_remains_paused": True,
        "stage12627_authoritative_ledger_update_dry_run_only_allowed": False,
        "authoritative_admitted_train_support_tasks_before_plan": 158,
        "authoritative_gap_to_500_before_plan": 342,
        "authoritative_admitted_train_support_tasks_after_plan": 158,
        "authoritative_gap_to_500_after_plan": 342,
        "planned_delta_total": 32,
        "planned_selected_lineage_delta": 14,
        "planned_direct_real_log_delta": 18,
        "planned_candidate_count_after_later_update": 190,
        "planned_candidate_gap_after_later_update": 310,
        "stage12418_derived_projection_countable_rows": 0,
        "update_plan_step_count": len(plan["update_plan_steps"]),
        "row_artifacts_to_write_now": 0,
        "summary_artifacts_to_update_now": 0,
        "frontier_100m_training_dataset_ready": False,
        "downstream_blockers": [
            "authoritative_ledger_update_dry_run_not_materialized",
            "authoritative_ledger_not_updated_in_stage12626",
            "new_train_support_rows_not_admitted",
            "authoritative_gap_still_342",
            "frontier_training_admission_absent",
            "training_admission_forbidden",
        ],
    }
    for label, record in (("summary", summary), ("contract", contract)):
        check_false(record, "stage12626_" + label)
        assert_public_sanitized(record, "stage12626_" + label)
    check_false(private, "stage12626_private")
    return summary, contract, private


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    stage12625 = load_stage12625()
    summary, contract, private = build_packet(stage12625)
    pointer = {
        "record_type": "stage12626_public_private_authoritative_ledger_update_plan_pointer_v1",
        **no_claim_fields(),
        "stage12625_summary_sha256": EXPECTED_HASHES["stage12625_summary"],
        "contract_sha256": stable_hash(contract),
        "private_update_plan_sha256": stable_hash(private),
        "update_plan_sha256": stable_hash(private["update_plan"]),
        "authoritative_ledger_update_plan_only": True,
        "vm_branch_remains_paused": True,
        "stage12627_authoritative_ledger_update_dry_run_only_allowed": False,
    }
    check_false(pointer, "stage12626_pointer")
    assert_public_sanitized(pointer, "stage12626_pointer")
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "private/authoritative_ledger_update_plan_only.json", private)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
