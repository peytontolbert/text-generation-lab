#!/usr/bin/env python3
"""Build Stage12625 authoritative ledger reconciliation review only.

Stage12624 classified the 32-task advisory count delta. This stage reviews the
available row and guardrail evidence for that delta and records whether a later
ledger-update plan can be prepared. It does not update the authoritative ledger,
admit rows, run training, resume VM/replay, materialize Level-3, or authorize
broad successor work.
"""
from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12625_authoritative_ledger_reconciliation_review_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
S12624 = ROOT / "runs/local/artifacts/stage12624_count_source_reconciliation_preflight_only"
S12624_SUMMARY = ROOT / "runs/summaries/stage12624_count_source_reconciliation_preflight_only.json"
SOURCE_SUMMARIES = {
    "stage12376": ROOT / "runs/summaries/stage12376_combined_train_support_ledger_v11.json",
    "stage12385": ROOT / "runs/summaries/stage12385_combined_train_support_ledger_v15_dedup.json",
    "stage12416": ROOT / "runs/summaries/stage12416_direct_verifier_log_train_support_canonicalizer.json",
    "stage12417": ROOT / "runs/summaries/stage12417_combined_train_support_ledger_v16.json",
    "stage12419": ROOT / "runs/summaries/stage12419_current_dataset_control_board_v17.json",
}
ROW_ARTIFACTS = {
    "stage12376_rows": ROOT / "runs/local/artifacts/stage12376_combined_train_support_ledger_v11/combined_selected_test_rows_v11.jsonl",
    "stage12385_rows": ROOT / "runs/local/artifacts/stage12385_combined_train_support_ledger_v15_dedup/combined_selected_test_rows_v15_dedup.jsonl",
    "stage12416_rows": ROOT / "runs/local/artifacts/stage12416_direct_verifier_log_train_support_canonicalizer/direct_verifier_log_train_support_rows.jsonl",
    "stage12416_guardrail": ROOT / "runs/local/artifacts/stage12416_direct_verifier_log_train_support_canonicalizer/guardrail_scan.json",
    "stage12417_rows": ROOT / "runs/local/artifacts/stage12417_combined_train_support_ledger_v16/combined_train_support_rows_v16.jsonl",
    "stage12417_guardrail": ROOT / "runs/local/artifacts/stage12417_combined_train_support_ledger_v16/guardrail_scan.json",
}
EXPECTED_HASHES = {
    "stage12624_summary": "0ae8b5ca29e787aee81c9ba3d9a74f1f8cba71922a83f0b6c2f3a99154f294c2",
    "stage12624_contract": "3c9748528c11b1111f4d88f75fe67810d2ff605d320b5e0ae665be3cf6713244",
    "stage12624_pointer": "1474e73cd4e31da35dabc2f723718b691973b7a0ed9dff96ad01b8531aa5cce4",
    "stage12624_private": "c7e1175f74a0467b49dac88c7e3f9c32d576bf52ae8b40f74bac2faebd6e1a27",
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
    "stage12625_allowed", "stage12626_allowed", "vm_branch_active", "vm_runner_implementation_allowed",
    "vm_runner_implementation_ready", "vm_runner_execution_allowed", "vm_runner_evidence_present",
    "vm_runner_trustworthy", "storage_root_created", "storage_write_performed", "execution_performed",
    "replay_trustworthy", "raw_replay_evidence_present", "trusted_replay_raw_evidence_present",
    "causal_transition_atoms_present", "causal_transition_atoms_allowed", "level3_preflight_allowed",
    "level_3_materialized", "level_3_materialization_allowed", "training_admission_preflight_allowed",
    "training_admission_allowed", "training_admitted", "training_allowed", "training_run_allowed",
    "gpu_allocation_requested", "cuda2_training_allowed", "strict_eval_admitted", "sealed_eval_admitted",
    "strict_eval_eligible", "sealed_eval_eligible", "admission_allowed", "ranking_allowed", "positive_stop",
    "authoritative_ledger_updated", "authoritative_ledger_update_allowed", "control_board_promoted_to_authoritative",
    "control_board_promotion_allowed",
)
PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "agentkernel_vm_replay", "/dev/", "selector", "raw_stream",
    "stdout.raw", "stderr.raw", "before_commit_oid", "after_commit_oid", "production_path",
    "production_patch_sha256", "manual_executor_slot_contracts", "slot_1.patch", "slot_2.patch",
    "repository_root", "patch_path", "slot_1/", "slot_2/", "combined_selected_test_rows",
    "combined_train_support_rows", "direct_verifier_log_train_support_manifest", "direct_verifier_log_train_support_rows",
    "guardrail_scan.json",
)
RISKY_SELECTED_FIELDS = ("level3_admitted", "patch_trace_admitted", "repair_claim_admitted", "source_heldout_admissible", "strict_eval_eligible")
RISKY_DIRECT_FIELDS = (*RISKY_SELECTED_FIELDS, "level4_admitted", "fail_to_pass_claim_admitted")


class LedgerReconciliationReviewError(RuntimeError):
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
        raise LedgerReconciliationReviewError("json_object_required:" + path.name)
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not all(isinstance(row, dict) for row in rows):
        raise LedgerReconciliationReviewError("jsonl_object_rows_required:" + path.name)
    return rows


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
            raise LedgerReconciliationReviewError(f"{label}_gate_drift:{field}")


def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise LedgerReconciliationReviewError(f"{label}_public_leak:{needle}")


def duplicate_stats(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts = Counter(str(row.get("row_id")) for row in rows)
    duplicate_ids = {row_id: count for row_id, count in counts.items() if count > 1}
    return {"duplicate_id_count": len(duplicate_ids), "duplicate_extra_rows": sum(count - 1 for count in duplicate_ids.values())}


def risky_selected_count(rows: Iterable[Mapping[str, Any]]) -> int:
    return sum(1 for row in rows if any((row.get("admission") or {}).get(field) for field in RISKY_SELECTED_FIELDS))


def raw_selected_count(rows: Iterable[Mapping[str, Any]]) -> int:
    return sum(1 for row in rows if (row.get("source_refs") or {}).get("raw_source_emitted") or (row.get("source_refs") or {}).get("raw_verifier_log_emitted"))


def risky_direct_count(rows: Iterable[Mapping[str, Any]]) -> int:
    return sum(1 for row in rows if any(row.get(field) for field in RISKY_DIRECT_FIELDS))


def load_inputs() -> dict[str, Any]:
    summary = read_json(S12624 / "summary.json")
    external = read_json(S12624_SUMMARY)
    contract = read_json(S12624 / "contract.json")
    pointer = read_json(S12624 / "digest_pointer.json")
    private = read_json(S12624 / "private/count_source_reconciliation_preflight_only.json")
    if summary != external:
        raise LedgerReconciliationReviewError("stage12624_external_summary_mismatch")
    for label, value in (
        ("stage12624_summary", summary),
        ("stage12624_contract", contract),
        ("stage12624_pointer", pointer),
        ("stage12624_private", private),
    ):
        if stable_hash(value) != EXPECTED_HASHES[label]:
            raise LedgerReconciliationReviewError("stage12624_pin_drift:" + label)
    if summary.get("stage12625_authoritative_ledger_reconciliation_review_only_allowed") is not True:
        raise LedgerReconciliationReviewError("stage12624_scoped_gate_missing")
    if summary.get("stage12625_allowed") is not False:
        raise LedgerReconciliationReviewError("stage12624_broad_successor_gate_drift")
    if summary.get("authoritative_admitted_train_support_tasks") != 158:
        raise LedgerReconciliationReviewError("stage12624_authoritative_baseline_drift")
    if summary.get("authoritative_gap_to_500") != 342:
        raise LedgerReconciliationReviewError("stage12624_authoritative_gap_drift")
    if summary.get("raw_delta_to_reconcile") != 32:
        raise LedgerReconciliationReviewError("stage12624_delta_drift")
    sources = {name: read_json(path) for name, path in SOURCE_SUMMARIES.items()}
    for label, value in sources.items():
        if stable_hash(value) != EXPECTED_HASHES[label]:
            raise LedgerReconciliationReviewError("source_pin_drift:" + label)
    row_hashes = {name: sha256_bytes(path.read_bytes()) for name, path in ROW_ARTIFACTS.items()}
    for label, value in row_hashes.items():
        if value != EXPECTED_HASHES[label]:
            raise LedgerReconciliationReviewError("row_artifact_pin_drift:" + label)
    rows = {name: read_jsonl(path) for name, path in ROW_ARTIFACTS.items() if path.suffix == ".jsonl"}
    guardrails = {name: read_json(path) for name, path in ROW_ARTIFACTS.items() if path.suffix == ".json"}
    return {
        "stage12624_summary": summary,
        "stage12624_contract": contract,
        "stage12624_pointer": pointer,
        "stage12624_private": private,
        "sources": sources,
        "rows": rows,
        "guardrails": guardrails,
        "row_hashes": row_hashes,
    }


def build_review(inputs: Mapping[str, Any]) -> dict[str, Any]:
    sources = inputs["sources"]
    rows = inputs["rows"]
    guardrails = inputs["guardrails"]
    s12376_rows = rows["stage12376_rows"]
    s12385_rows = rows["stage12385_rows"]
    s12416_rows = rows["stage12416_rows"]
    s12417_rows = rows["stage12417_rows"]
    ids12376 = {row["row_id"] for row in s12376_rows}
    ids12385 = {row["row_id"] for row in s12385_rows}
    ids12416 = {row["row_id"] for row in s12416_rows}
    ids12417 = {row["row_id"] for row in s12417_rows}
    selected_added = [row for row in s12385_rows if row["row_id"] not in ids12376]
    selected_removed = [row for row in s12376_rows if row["row_id"] not in ids12385]
    s12376_dupes = duplicate_stats(s12376_rows)
    s12385_dupes = duplicate_stats(s12385_rows)
    s12416_dupes = duplicate_stats(s12416_rows)
    s12417_dupes = duplicate_stats(s12417_rows)
    selected_net_delta = len(s12385_rows) - len(s12376_rows)
    if (len(s12376_rows), len(s12385_rows), selected_net_delta) != (67, 81, 14):
        raise LedgerReconciliationReviewError("selected_row_count_delta_drift")
    if (len(selected_added), len(selected_removed), s12376_dupes["duplicate_extra_rows"], s12385_dupes["duplicate_extra_rows"]) != (30, 6, 10, 0):
        raise LedgerReconciliationReviewError("selected_supersession_arithmetic_drift")
    if selected_net_delta != len(selected_added) - len(selected_removed) - s12376_dupes["duplicate_extra_rows"]:
        raise LedgerReconciliationReviewError("selected_net_delta_formula_drift")
    if (len(s12416_rows), len(s12417_rows), len(ids12417 - ids12385)) != (18, 99, 18):
        raise LedgerReconciliationReviewError("direct_log_merge_delta_drift")
    if not ids12416.issubset(ids12417):
        raise LedgerReconciliationReviewError("stage12416_rows_missing_from_stage12417")
    if any(duplicate_stats(value)["duplicate_extra_rows"] for value in (s12385_rows, s12416_rows, s12417_rows)):
        raise LedgerReconciliationReviewError("post_reconciliation_duplicate_rows_present")
    s12416_guard = guardrails["stage12416_guardrail"]
    s12417_guard = guardrails["stage12417_guardrail"]
    if s12416_guard.get("scan_passed") is not True or s12417_guard.get("scan_passed") is not True:
        raise LedgerReconciliationReviewError("guardrail_scan_failed")
    if s12416_guard.get("raw_leak_count") != 0 or s12417_guard.get("raw_leak_count") != 0:
        raise LedgerReconciliationReviewError("raw_leak_guardrail_drift")
    if s12416_guard.get("overclaim_count") != 0 or s12417_guard.get("overclaim_count") != 0:
        raise LedgerReconciliationReviewError("overclaim_guardrail_drift")
    if risky_selected_count(selected_added) or raw_selected_count(selected_added) or risky_direct_count(s12416_rows):
        raise LedgerReconciliationReviewError("delta_component_risk_drift")
    s12385 = sources["stage12385"]
    s12416 = sources["stage12416"]
    s12417 = sources["stage12417"]
    if s12385.get("selected_test_duplicate_rows_removed") != 10:
        raise LedgerReconciliationReviewError("stage12385_duplicate_removal_drift")
    if s12385.get("selected_test_raw_command_rows_should_be_zero") != 0:
        raise LedgerReconciliationReviewError("stage12385_raw_command_drift")
    if s12385.get("selected_test_generic_non_candidate_targets_should_be_zero") != 0:
        raise LedgerReconciliationReviewError("stage12385_generic_target_drift")
    if s12416.get("duplicate_projection_count_against_stage12385") != 0:
        raise LedgerReconciliationReviewError("stage12416_duplicate_projection_drift")
    if s12416.get("guardrail_scan_passed") is not True or s12417.get("guardrail_scan_passed") is not True:
        raise LedgerReconciliationReviewError("summary_guardrail_drift")
    components = [
        {
            "component_id": "stage12385_minus_stage12376_selected_test_lineage_delta",
            "review_status": "passed_for_later_authoritative_ledger_update_plan_not_admitted",
            "net_task_delta": 14,
            "selected_rows_before": 67,
            "selected_rows_after": 81,
            "row_ids_added": 30,
            "row_ids_removed_or_superseded": 6,
            "prior_duplicate_extra_rows_removed": 10,
            "post_review_duplicate_extra_rows": 0,
            "risk_counts": {"risky_claim_rows": 0, "raw_source_or_log_rows": 0},
            "required_later_action": "prepare_authoritative_ledger_update_plan_with_supersession_manifest",
        },
        {
            "component_id": "stage12416_direct_real_log_delta",
            "review_status": "passed_for_later_authoritative_ledger_update_plan_not_admitted",
            "net_task_delta": 18,
            "direct_log_projection_rows": 18,
            "rows_present_in_stage12417": 18,
            "post_review_duplicate_extra_rows": 0,
            "guardrail_scan_passed": True,
            "risk_counts": {"risky_claim_rows": 0, "raw_leak_rows": 0, "overclaim_rows": 0},
            "required_later_action": "prepare_authoritative_ledger_update_plan_with_stage12416_dedupe_manifest",
        },
    ]
    return {
        "record_type": "stage12625_authoritative_ledger_reconciliation_review_v1",
        "authoritative_baseline_stage": "stage12376_combined_train_support_ledger_v11",
        "authoritative_admitted_train_support_tasks_before_review": 158,
        "authoritative_gap_to_500_before_review": 342,
        "control_board_advisory_countable_supply_tasks": 190,
        "control_board_advisory_gap_to_500": 310,
        "reviewed_delta_total": 32,
        "review_components": components,
        "review_component_count": len(components),
        "review_passed_delta_total": 32,
        "review_blocked_delta_total": 0,
        "authoritative_ledger_update_performed": False,
        "authoritative_admitted_train_support_tasks_after_review": 158,
        "authoritative_gap_to_500_after_review": 342,
        "candidate_count_after_future_update_if_authorized": 190,
        "candidate_gap_after_future_update_if_authorized": 310,
        "reconciliation_review_status": "passed_for_later_update_plan_no_authoritative_ledger_update",
        "minimum_next_gate": "stage12626_authoritative_ledger_update_plan_only",
        "review_only": True,
        "new_admission_performed": False,
        "training_allowed_after_review": False,
    }


def build_packet(inputs: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    review = build_review(inputs)
    private = {
        "record_type": "stage12625_private_authoritative_ledger_reconciliation_review_only_v1",
        **no_claim_fields(),
        "source_hashes": EXPECTED_HASHES,
        "row_artifact_hashes": inputs["row_hashes"],
        "authoritative_ledger_reconciliation_review_only": True,
        "vm_branch_remains_paused": True,
        "stage12626_authoritative_ledger_update_plan_only_allowed": True,
        "reconciliation_review": review,
        "decision": "AUTHORITATIVE_LEDGER_RECONCILIATION_REVIEW_PASSED_UPDATE_PLAN_REQUIRED_NO_ADMISSION",
    }
    contract = {
        "record_type": "stage12625_public_authoritative_ledger_reconciliation_review_only_contract_v1",
        **no_claim_fields(),
        "stage12624_summary_sha256": EXPECTED_HASHES["stage12624_summary"],
        "stage12376_summary_sha256": EXPECTED_HASHES["stage12376"],
        "stage12419_summary_sha256": EXPECTED_HASHES["stage12419"],
        "reconciliation_review_sha256": stable_hash(review),
        "private_reconciliation_review_sha256": stable_hash(private),
        "authoritative_ledger_reconciliation_review_only": True,
        "vm_branch_remains_paused": True,
        "stage12626_authoritative_ledger_update_plan_only_allowed": True,
        "claim_boundary": {
            "review": "authoritative_ledger_reconciliation_review_only",
            "authoritative_ledger_update": "not_performed",
            "new_admission": "not_authorized",
            "training": "not_authorized",
            "vm": "paused_not_used_for_ledger_review",
            "replay": "not_executed",
            "level3": "not_materialized",
        },
    }
    summary = {
        "record_type": "stage12625_public_authoritative_ledger_reconciliation_review_only_summary_v1",
        **no_claim_fields(),
        "stage": STAGE,
        "decision": "AUTHORITATIVE_LEDGER_RECONCILIATION_REVIEW_PASSED_UPDATE_PLAN_REQUIRED_NO_ADMISSION",
        "stage12624_summary_sha256": EXPECTED_HASHES["stage12624_summary"],
        "stage12376_summary_sha256": EXPECTED_HASHES["stage12376"],
        "stage12419_summary_sha256": EXPECTED_HASHES["stage12419"],
        "reconciliation_review_sha256": stable_hash(review),
        "private_reconciliation_review_sha256": stable_hash(private),
        "authoritative_ledger_reconciliation_review_only": True,
        "vm_branch_remains_paused": True,
        "stage12626_authoritative_ledger_update_plan_only_allowed": True,
        "authoritative_admitted_train_support_tasks_before_review": 158,
        "authoritative_gap_to_500_before_review": 342,
        "reviewed_delta_total": 32,
        "review_passed_delta_total": 32,
        "review_blocked_delta_total": 0,
        "stage12385_selected_lineage_net_delta": 14,
        "stage12385_selected_lineage_added_rows": 30,
        "stage12385_selected_lineage_superseded_rows": 6,
        "stage12376_prior_duplicate_extra_rows_removed_by_lineage": 10,
        "stage12416_direct_real_log_delta": 18,
        "stage12418_derived_projection_countable_rows": 0,
        "authoritative_admitted_train_support_tasks_after_review": 158,
        "authoritative_gap_to_500_after_review": 342,
        "candidate_count_after_future_update_if_authorized": 190,
        "candidate_gap_after_future_update_if_authorized": 310,
        "reconciliation_review_status": "passed_for_later_update_plan_no_authoritative_ledger_update",
        "frontier_100m_training_dataset_ready": False,
        "downstream_blockers": [
            "authoritative_ledger_update_plan_not_materialized",
            "authoritative_ledger_not_updated_in_stage12625",
            "new_train_support_rows_not_admitted",
            "authoritative_gap_still_342",
            "frontier_training_admission_absent",
            "training_admission_forbidden",
        ],
    }
    for label, record in (("summary", summary), ("contract", contract)):
        check_false(record, "stage12625_" + label)
        assert_public_sanitized(record, "stage12625_" + label)
    check_false(private, "stage12625_private")
    return summary, contract, private


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    inputs = load_inputs()
    summary, contract, private = build_packet(inputs)
    pointer = {
        "record_type": "stage12625_public_private_authoritative_ledger_reconciliation_review_pointer_v1",
        **no_claim_fields(),
        "stage12624_summary_sha256": EXPECTED_HASHES["stage12624_summary"],
        "contract_sha256": stable_hash(contract),
        "private_reconciliation_review_sha256": stable_hash(private),
        "reconciliation_review_sha256": stable_hash(private["reconciliation_review"]),
        "authoritative_ledger_reconciliation_review_only": True,
        "vm_branch_remains_paused": True,
        "stage12626_authoritative_ledger_update_plan_only_allowed": True,
    }
    check_false(pointer, "stage12625_pointer")
    assert_public_sanitized(pointer, "stage12625_pointer")
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "private/authoritative_ledger_reconciliation_review_only.json", private)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
