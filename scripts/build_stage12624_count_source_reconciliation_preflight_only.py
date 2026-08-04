#!/usr/bin/env python3
"""Build Stage12624 count-source reconciliation preflight only.

Stage12623 authorized only a narrow count-source reconciliation preflight. This
stage classifies why the Stage12419 control board reports 190 countable tasks
while the current authoritative Stage12376 ledger remains 158. It does not admit
rows, update the authoritative ledger, run replay/VM work, materialize Level-3,
or authorize training.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12624_count_source_reconciliation_preflight_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
S12623 = ROOT / "runs/local/artifacts/stage12623_dataset_gap_plan_only"
S12623_SUMMARY = ROOT / "runs/summaries/stage12623_dataset_gap_plan_only.json"
SOURCE_SUMMARIES = {
    "stage12376": ROOT / "runs/summaries/stage12376_combined_train_support_ledger_v11.json",
    "stage12385": ROOT / "runs/summaries/stage12385_combined_train_support_ledger_v15_dedup.json",
    "stage12416": ROOT / "runs/summaries/stage12416_direct_verifier_log_train_support_canonicalizer.json",
    "stage12417": ROOT / "runs/summaries/stage12417_combined_train_support_ledger_v16.json",
    "stage12419": ROOT / "runs/summaries/stage12419_current_dataset_control_board_v17.json",
}
EXPECTED_HASHES = {
    "stage12623_summary": "02f26841e4c3c824a9f7e405cd9b1d49902a9d727940b27043861a2d5f06abd0",
    "stage12623_contract": "a4cf94a1e9ae107357f2d0c8178a9c32e09e71f0ecb7e91c9e5d9bf4a974fe96",
    "stage12623_pointer": "b6b3f70093abf9bcf43185307ce6d20dc445afb34792c3fcaece9ed7b9648d62",
    "stage12623_private": "24aa9cdbc28161ca9e3b612e40c17e74ab9bf048015e4722f9d7e784523feddd",
    "stage12376": "a7aa3bcae28c5741f1955d2b954744143266bb61d2e824d78343e932cc3b695e",
    "stage12385": "9a95e41cda6609ce7aee84d1a9aea409f06824b03d1f48a81fc74cbaafc55615",
    "stage12416": "35a01e25be81736b84a49da918e34448ddcc93e31cb57d207b765c74334228f6",
    "stage12417": "c9a872e36c12888b7f3fd45218cb69aa7d75b238378368289483ba54c483721a",
    "stage12419": "61b8a0541c06cec23ac06d75e5da9679c073d7615b97ee2257748049e4d5d954",
}

FALSE_FIELDS = (
    "implementation_ready", "dataset_admission_allowed", "dataset_rows_admitted", "new_rows_admitted",
    "frontier_100m_training_dataset_ready", "source_packet_implementation_allowed", "source_packet_executable",
    "stage12620_allowed", "stage12621_allowed", "stage12622_allowed", "stage12623_allowed", "stage12624_allowed",
    "stage12625_allowed", "vm_branch_active", "vm_runner_implementation_allowed", "vm_runner_implementation_ready",
    "vm_runner_execution_allowed", "vm_runner_evidence_present", "vm_runner_trustworthy", "storage_root_created",
    "storage_write_performed", "execution_performed", "replay_trustworthy", "raw_replay_evidence_present",
    "trusted_replay_raw_evidence_present", "causal_transition_atoms_present", "causal_transition_atoms_allowed",
    "level3_preflight_allowed", "level_3_materialized", "level_3_materialization_allowed",
    "training_admission_preflight_allowed", "training_admission_allowed", "training_admitted", "training_allowed",
    "training_run_allowed", "gpu_allocation_requested", "cuda2_training_allowed", "strict_eval_admitted",
    "sealed_eval_admitted", "strict_eval_eligible", "sealed_eval_eligible", "admission_allowed",
    "ranking_allowed", "positive_stop", "authoritative_ledger_updated", "control_board_promoted_to_authoritative",
)
PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "agentkernel_vm_replay", "/dev/", "selector", "raw_stream",
    "stdout.raw", "stderr.raw", "before_commit_oid", "after_commit_oid", "production_path",
    "production_patch_sha256", "manual_executor_slot_contracts", "slot_1.patch", "slot_2.patch",
    "repository_root", "patch_path", "slot_1/", "slot_2/", "combined_selected_test_rows",
    "combined_train_support_rows", "direct_verifier_log_train_support_manifest",
)


class CountSourceReconciliationError(RuntimeError):
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
        raise CountSourceReconciliationError("json_object_required:" + path.name)
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
            raise CountSourceReconciliationError(f"{label}_gate_drift:{field}")


def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise CountSourceReconciliationError(f"{label}_public_leak:{needle}")


def load_inputs() -> dict[str, Any]:
    summary = read_json(S12623 / "summary.json")
    external = read_json(S12623_SUMMARY)
    contract = read_json(S12623 / "contract.json")
    pointer = read_json(S12623 / "digest_pointer.json")
    private = read_json(S12623 / "private/dataset_gap_plan_only.json")
    if summary != external:
        raise CountSourceReconciliationError("stage12623_external_summary_mismatch")
    for label, value in (
        ("stage12623_summary", summary),
        ("stage12623_contract", contract),
        ("stage12623_pointer", pointer),
        ("stage12623_private", private),
    ):
        if stable_hash(value) != EXPECTED_HASHES[label]:
            raise CountSourceReconciliationError("stage12623_pin_drift:" + label)
    if summary.get("stage12624_count_source_reconciliation_preflight_only_allowed") is not True:
        raise CountSourceReconciliationError("stage12623_scoped_gate_missing")
    if summary.get("stage12624_allowed") is not False:
        raise CountSourceReconciliationError("stage12623_broad_successor_gate_drift")
    if summary.get("authoritative_planning_baseline_tasks") != 158:
        raise CountSourceReconciliationError("stage12623_authoritative_baseline_drift")
    if summary.get("authoritative_training_gap_to_500") != 342:
        raise CountSourceReconciliationError("stage12623_authoritative_gap_drift")
    if summary.get("control_board_advisory_countable_supply_tasks") != 190:
        raise CountSourceReconciliationError("stage12623_control_board_count_drift")
    sources = {name: read_json(path) for name, path in SOURCE_SUMMARIES.items()}
    for label, value in sources.items():
        if stable_hash(value) != EXPECTED_HASHES[label]:
            raise CountSourceReconciliationError("source_pin_drift:" + label)
    return {
        "stage12623_summary": summary,
        "stage12623_contract": contract,
        "stage12623_pointer": pointer,
        "stage12623_private": private,
        "sources": sources,
    }


def build_reconciliation_preflight(inputs: Mapping[str, Any]) -> dict[str, Any]:
    sources = inputs["sources"]
    s12376 = sources["stage12376"]
    s12385 = sources["stage12385"]
    s12416 = sources["stage12416"]
    s12417 = sources["stage12417"]
    s12419 = sources["stage12419"]
    authoritative_count = s12376.get("current_admitted_train_support_tasks")
    authoritative_gap = s12376.get("remaining_gap_to_500")
    stage12385_count = s12385.get("current_admitted_train_support_tasks")
    stage12416_delta = s12416.get("emitted_train_support_rows")
    control_count = (s12419.get("countable_train_support") or {}).get("stage12417_current_admitted_train_support_tasks")
    control_gap = (s12419.get("countable_train_support") or {}).get("remaining_gap_to_500")
    stage12417_count = s12417.get("current_admitted_train_support_tasks")
    if (authoritative_count, authoritative_gap) != (158, 342):
        raise CountSourceReconciliationError("authoritative_count_source_drift")
    if stage12385_count != 172:
        raise CountSourceReconciliationError("stage12385_count_drift")
    if stage12416_delta != 18:
        raise CountSourceReconciliationError("stage12416_delta_drift")
    if (stage12417_count, control_count, control_gap) != (190, 190, 310):
        raise CountSourceReconciliationError("control_board_count_source_drift")
    selected_lineage_delta = stage12385_count - authoritative_count
    direct_log_delta = stage12416_delta
    total_delta = control_count - authoritative_count
    if (selected_lineage_delta, direct_log_delta, total_delta) != (14, 18, 32):
        raise CountSourceReconciliationError("delta_arithmetic_drift")
    components = [
        {
            "component_id": "stage12385_minus_stage12376_selected_test_lineage_delta",
            "source_stage": "stage12385_combined_train_support_ledger_v15_dedup",
            "baseline_stage": "stage12376_combined_train_support_ledger_v11",
            "candidate_task_delta": selected_lineage_delta,
            "candidate_status": "reconciliation_review_required_not_admitted",
            "evidence_to_verify": [
                "supersession_lineage_from_stage12376_to_stage12385",
                "selected_test_duplicate_rows_removed_equals_10",
                "generic_non_candidate_targets_zero",
                "raw_command_rows_zero",
                "anti_collapse_failures_empty",
            ],
            "dedupe_keys": ["row_id", "root_id", "task_family", "target_semantic_id"],
            "exclusion_rules": ["do_not_promote_over_stage12376_without_authoritative_ledger_update", "do_not_recount_superseded_rows"],
            "admission_action": "none_preflight_only",
        },
        {
            "component_id": "stage12416_direct_real_log_delta",
            "source_stage": "stage12416_direct_verifier_log_train_support_canonicalizer",
            "baseline_stage": "stage12385_combined_train_support_ledger_v15_dedup",
            "candidate_task_delta": direct_log_delta,
            "candidate_status": "reconciliation_review_required_not_admitted",
            "evidence_to_verify": [
                "guardrail_scan_passed",
                "duplicate_projection_count_against_stage12385_zero",
                "raw_leak_count_zero",
                "overclaim_count_zero",
                "level3_patch_repair_fail_to_pass_claims_zero",
            ],
            "dedupe_keys": ["source_record_id", "projection_id", "task_family", "target_semantic"],
            "exclusion_rules": ["do_not_count_stage12418_derived_projection_rows", "do_not_claim_repair_or_level3"],
            "admission_action": "none_preflight_only",
        },
    ]
    return {
        "record_type": "stage12624_count_source_reconciliation_preflight_v1",
        "authoritative_baseline_stage": "stage12376_combined_train_support_ledger_v11",
        "authoritative_admitted_train_support_tasks": authoritative_count,
        "authoritative_gap_to_500": authoritative_gap,
        "control_board_stage": "stage12419_current_dataset_control_board_v17",
        "control_board_advisory_countable_supply_tasks": control_count,
        "control_board_advisory_gap_to_500": control_gap,
        "raw_delta_to_reconcile": total_delta,
        "delta_components": components,
        "delta_component_count": len(components),
        "stage12385_selected_lineage_delta": selected_lineage_delta,
        "stage12416_direct_real_log_delta": direct_log_delta,
        "stage12417_control_ledger_count": stage12417_count,
        "stage12418_derived_projection_countable_rows": (s12419.get("derived_projection_lane") or {}).get("stage12418_countable_as_new_train_support_rows"),
        "stage12418_derived_projection_rows_excluded": (s12419.get("derived_projection_lane") or {}).get("stage12418_sanitized_projection_rows"),
        "reconciliation_status": "not_reconciled_no_authoritative_ledger_update",
        "minimum_next_gate": "stage12625_authoritative_ledger_reconciliation_review_only",
        "preflight_only": True,
        "new_admission_performed": False,
        "training_allowed_after_preflight": False,
    }


def build_packet(inputs: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    preflight = build_reconciliation_preflight(inputs)
    private = {
        "record_type": "stage12624_private_count_source_reconciliation_preflight_only_v1",
        **no_claim_fields(),
        "source_hashes": EXPECTED_HASHES,
        "count_source_reconciliation_preflight_only": True,
        "vm_branch_remains_paused": True,
        "stage12625_authoritative_ledger_reconciliation_review_only_allowed": True,
        "reconciliation_preflight": preflight,
        "decision": "COUNT_SOURCE_RECONCILIATION_PREFLIGHT_RECORDED_NO_ADMISSION",
    }
    contract = {
        "record_type": "stage12624_public_count_source_reconciliation_preflight_only_contract_v1",
        **no_claim_fields(),
        "stage12623_summary_sha256": EXPECTED_HASHES["stage12623_summary"],
        "stage12376_summary_sha256": EXPECTED_HASHES["stage12376"],
        "stage12419_summary_sha256": EXPECTED_HASHES["stage12419"],
        "reconciliation_preflight_sha256": stable_hash(preflight),
        "private_reconciliation_preflight_sha256": stable_hash(private),
        "count_source_reconciliation_preflight_only": True,
        "vm_branch_remains_paused": True,
        "stage12625_authoritative_ledger_reconciliation_review_only_allowed": True,
        "claim_boundary": {
            "plan": "count_source_reconciliation_preflight_only",
            "authoritative_ledger_update": "not_authorized",
            "new_admission": "not_authorized",
            "training": "not_authorized",
            "vm": "paused_not_used_for_count_reconciliation",
            "replay": "not_executed",
            "level3": "not_materialized",
        },
    }
    summary = {
        "record_type": "stage12624_public_count_source_reconciliation_preflight_only_summary_v1",
        **no_claim_fields(),
        "stage": STAGE,
        "decision": "COUNT_SOURCE_RECONCILIATION_PREFLIGHT_RECORDED_NO_ADMISSION",
        "stage12623_summary_sha256": EXPECTED_HASHES["stage12623_summary"],
        "stage12376_summary_sha256": EXPECTED_HASHES["stage12376"],
        "stage12419_summary_sha256": EXPECTED_HASHES["stage12419"],
        "reconciliation_preflight_sha256": stable_hash(preflight),
        "private_reconciliation_preflight_sha256": stable_hash(private),
        "count_source_reconciliation_preflight_only": True,
        "vm_branch_remains_paused": True,
        "stage12625_authoritative_ledger_reconciliation_review_only_allowed": True,
        "authoritative_admitted_train_support_tasks": 158,
        "authoritative_gap_to_500": 342,
        "control_board_advisory_countable_supply_tasks": 190,
        "control_board_advisory_gap_to_500": 310,
        "raw_delta_to_reconcile": 32,
        "delta_component_count": 2,
        "stage12385_selected_lineage_delta": 14,
        "stage12416_direct_real_log_delta": 18,
        "stage12418_derived_projection_countable_rows": 0,
        "stage12418_derived_projection_rows_excluded": 292,
        "reconciliation_status": "not_reconciled_no_authoritative_ledger_update",
        "frontier_100m_training_dataset_ready": False,
        "downstream_blockers": [
            "stage12385_lineage_delta_not_authoritatively_reconciled",
            "stage12416_direct_log_delta_not_authoritatively_reconciled",
            "stage12418_derived_projection_rows_excluded_from_train_support_count",
            "authoritative_ledger_still_158",
            "authoritative_gap_still_342",
            "new_train_support_rows_not_admitted",
            "training_admission_forbidden",
        ],
    }
    for label, record in (("summary", summary), ("contract", contract)):
        check_false(record, "stage12624_" + label)
        assert_public_sanitized(record, "stage12624_" + label)
    check_false(private, "stage12624_private")
    return summary, contract, private


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    inputs = load_inputs()
    summary, contract, private = build_packet(inputs)
    pointer = {
        "record_type": "stage12624_public_private_count_source_reconciliation_preflight_pointer_v1",
        **no_claim_fields(),
        "stage12623_summary_sha256": EXPECTED_HASHES["stage12623_summary"],
        "contract_sha256": stable_hash(contract),
        "private_reconciliation_preflight_sha256": stable_hash(private),
        "reconciliation_preflight_sha256": stable_hash(private["reconciliation_preflight"]),
        "count_source_reconciliation_preflight_only": True,
        "vm_branch_remains_paused": True,
        "stage12625_authoritative_ledger_reconciliation_review_only_allowed": True,
    }
    check_false(pointer, "stage12624_pointer")
    assert_public_sanitized(pointer, "stage12624_pointer")
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "private/count_source_reconciliation_preflight_only.json", private)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
