#!/usr/bin/env python3
"""Gate Stage12516 private causal evidence statuses for semantic sufficiency.

Stage12519 consumes only public-safe Stage12516 validated return statuses plus
Stage12515/12517 identity context. It groups by revalidation_id_hash and checks
whether every required private causal evidence slot is both present and
semantically sufficient. Status and digest hashes are never treated as proof.

The stage emits blockers and a missing-evidence worklist only. It writes no
training, admission, Level-3, patch-trace, Stage12503, raw path, raw command,
raw diff, source, or verifier-output artifacts.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12519_private_causal_evidence_semantic_sufficiency_gate"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12515 = "stage12515_private_causal_evidence_acquisition_work_orders"
STAGE12516 = "stage12516_private_causal_evidence_return_preflight"
STAGE12517 = "stage12517_private_causal_evidence_return_candidate_worklist"

STAGE12515_OUT = ROOT / "runs/local/artifacts" / STAGE12515
STAGE12516_OUT = ROOT / "runs/local/artifacts" / STAGE12516
STAGE12517_OUT = ROOT / "runs/local/artifacts" / STAGE12517

WORK_ORDERS = STAGE12515_OUT / "private_causal_evidence_acquisition_work_orders.jsonl"
VALIDATED_STATUS = STAGE12516_OUT / "validated_private_causal_evidence_return_status.jsonl"
WORKLIST = STAGE12517_OUT / "private_causal_evidence_return_candidate_materialization_worklist.jsonl"

VALIDATED_RECORD_TYPE = "stage12516_validated_private_causal_evidence_return_status_v1"
WORK_ORDER_RECORD_TYPE = "stage12515_private_causal_evidence_acquisition_work_order_v1"
WORKLIST_RECORD_TYPE = "stage12517_private_causal_evidence_return_candidate_materialization_task_v1"

FULL_SEVEN_SLOTS = [
    "same_source_causal_lineage_with_independent_evidence_digest",
    "structured_state_before_codes",
    "state_delta_or_state_after_codes",
    "patch_apply_or_no_patch_status",
    "stop_continue_policy_label",
    "independent_policy_label_and_candidate_action_set",
    "external_patch_effect_or_no_patch_reason",
]
IDENTITY_FIELDS = [
    "revalidation_id_hash",
    "request_id_hash",
    "work_item_id_hash",
    "packet_id_hash",
    "root_or_window_hash",
    "source_stage",
    "source_kind",
    "language_family",
    "task_family",
]
STATUS_IDENTITY_FIELDS = [*IDENTITY_FIELDS, "acquisition_work_order_id_hash", "evidence_slot", "proof_class"]

NON_PROOF_STATUSES = {"blocked_unavailable", "validated_absent", "not_applicable"}
SUFFICIENT_STATUS = "validated_present"
NO_PATCH_SLOTS = {"patch_apply_or_no_patch_status", "external_patch_effect_or_no_patch_reason"}
NO_STOP_SLOTS = {"stop_continue_policy_label"}
EXPLICIT_NO_PATCH_REASON_CODES = {
    "explicit_no_patch_reason_validated",
    "no_patch_semantics_validated",
    "not_applicable_no_patch_semantics_validated",
}
EXPLICIT_NO_STOP_REASON_CODES = {
    "explicit_no_stop_reason_validated",
    "no_stop_semantics_validated",
    "not_applicable_no_stop_semantics_validated",
}

RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:git clone|git apply|pytest\s|python -c|bash -|sh -|curl\s|"
    r"stdout|stderr|traceback|terminal output|command output|verifier output|commit:)\b|"
    r"\b[0-9a-f]{40}\b",
    re.IGNORECASE | re.MULTILINE,
)
FORBIDDEN_PUBLIC_KEYS = {
    "raw",
    "raw_output",
    "raw_outputs",
    "raw_diff",
    "diff",
    "patch",
    "command",
    "commands",
    "cmd",
    "path",
    "paths",
    "file_path",
    "source_text",
    "source_content",
    "verifier_output",
    "stdout",
    "stderr",
    "terminal_output",
    "policy_label",
    "policy_label_hash",
    "training_row",
    "training_rows",
    "admitted_row",
    "level3_atom",
    "patch_trace",
    "proof_row",
}
FALSE_GUARDS = {
    "training_allowed": False,
    "admission_allowed": False,
    "packaging_allowed": False,
    "execution_performed_by_stage": False,
    "hydration_performed_by_stage": False,
    "replay_performed_by_stage": False,
    "network_performed_by_stage": False,
    "policy_label_materialized": False,
    "level3_atom_materialized": False,
    "patch_trace_materialized": False,
    "stage12503_return_file_written": False,
    "proof_admission_allowed": False,
    "raw_source_output_included": False,
    "raw_private_values_revealed": False,
}
ZERO_GUARDS = {
    "training_rows_emitted": 0,
    "admitted_rows": 0,
    "level3_admitted": 0,
    "level3_atom_count": 0,
    "patch_trace_admitted": 0,
    "patch_trace_rows": 0,
    "policy_labels_emitted": 0,
    "proof_rows_emitted": 0,
    "proof_grade_repair_rows": 0,
    "external_repair_credit_count": 0,
    "sealed_eval_rows": 0,
    "stage12503_return_records_written": 0,
}


class RawLeakError(ValueError):
    pass


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode("utf-8")).hexdigest()[:n]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                value = json.loads(line)
                if isinstance(value, dict):
                    rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def scan_raw_leaks(value: Any) -> list[str]:
    issues: list[str] = []
    if isinstance(value, str):
        if RAW_LEAK_RE.search(value):
            issues.append(stable_hash(value))
    elif isinstance(value, dict):
        for key, child in value.items():
            if key in FORBIDDEN_PUBLIC_KEYS:
                issues.append(stable_hash({"forbidden_key": key}))
            issues.extend(scan_raw_leaks(child))
    elif isinstance(value, list):
        for child in value:
            issues.extend(scan_raw_leaks(child))
    return issues


def enforce_no_raw_leaks(value: Any) -> None:
    issues = scan_raw_leaks(value)
    if issues:
        raise RawLeakError(f"stage12519 raw leak guard rejected {len(issues)} public field(s)")


def _safe_str(row: dict[str, Any], field: str) -> str:
    value = row.get(field)
    return value if isinstance(value, str) else ""


def _identity_key(row: dict[str, Any]) -> tuple[str, ...]:
    return tuple(_safe_str(row, field) for field in IDENTITY_FIELDS)


def _identity_context_for(
    revalidation_id: str,
    rows: list[dict[str, Any]],
    work_orders_by_revalidation: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    source = rows[0] if rows else (work_orders_by_revalidation.get(revalidation_id) or [{}])[0]
    return {field: source.get(field) for field in IDENTITY_FIELDS}


def _slot_semantic_result(status: dict[str, Any] | None) -> tuple[bool, str, str | None]:
    if status is None:
        return False, "missing_stage12516_validated_status", None
    slot = _safe_str(status, "evidence_slot")
    independent_status = _safe_str(status, "independent_slot_status")
    reason = _safe_str(status, "slot_status_reason_code")
    if independent_status == SUFFICIENT_STATUS:
        return True, "validated_present_semantically_sufficient", None
    if independent_status == "blocked_unavailable":
        return False, "blocked_unavailable_is_non_proof", "status_non_proof_blocked_unavailable"
    if slot in NO_PATCH_SLOTS and independent_status in {"validated_absent", "not_applicable"}:
        if reason in EXPLICIT_NO_PATCH_REASON_CODES:
            return True, "explicit_no_patch_semantics_sufficient_without_repair_credit", None
        return False, "no_patch_status_lacks_explicit_semantic_reason", "explicit_no_patch_semantics_missing"
    if slot in NO_STOP_SLOTS and independent_status in {"validated_absent", "not_applicable"}:
        if reason in EXPLICIT_NO_STOP_REASON_CODES:
            return True, "explicit_no_stop_semantics_sufficient_without_observed_action_imitation", None
        return False, "no_stop_status_lacks_explicit_semantic_reason", "explicit_no_stop_semantics_missing"
    if independent_status in NON_PROOF_STATUSES:
        return False, f"{independent_status}_is_non_proof_for_slot", f"status_non_proof_{independent_status}"
    return False, "unsupported_or_missing_independent_slot_status", "unsupported_or_missing_status"


def _guard_failures(status: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if status.get("record_type") != VALIDATED_RECORD_TYPE:
        failures.append("stage12516_validated_record_type_required")
    if status.get("private_causal_evidence_return_validated") is not True:
        failures.append("stage12516_status_not_validated")
    if status.get("proof_admission_allowed") is not False:
        failures.append("proof_admission_allowed_not_false")
    if status.get("training_allowed") is not False:
        failures.append("training_allowed_not_false")
    if status.get("admission_allowed") is not False:
        failures.append("admission_allowed_not_false")
    if status.get("stage12503_return_records_written") != 0:
        failures.append("stage12503_return_records_written_nonzero")
    for field in [
        "raw_private_values_revealed",
        "raw_source_output_included",
        "raw_paths_included",
        "raw_commands_included",
        "raw_diffs_included",
        "raw_verifier_output_included",
        "observed_action_available_to_labeler",
        "observed_action_used_as_label",
        "pass_to_pass_repair_credit_requested",
    ]:
        if field in status and status.get(field) is not False:
            failures.append(f"{field}_not_false")
    for field in [
        "candidate_action_set_blinded",
        "label_leak_attestation",
        "model_facing_gold_fields_excluded",
        "repair_credit_requires_before_fail_after_pass_same_verifier",
    ]:
        if field in status and status.get(field) is not True:
            failures.append(f"{field}_not_true")
    if set(status.keys()) & FORBIDDEN_PUBLIC_KEYS:
        failures.append("forbidden_raw_label_or_proof_field_present")
    if scan_raw_leaks(status):
        failures.append("raw_leakage_detected")
    return sorted(set(failures))


def _slot_matrix_row(
    revalidation_id: str,
    slot: str,
    status: dict[str, Any] | None,
    work_order: dict[str, Any] | None,
    stage12517_slot_ref_seen: bool,
) -> dict[str, Any]:
    sufficient, reason, blocker_code = _slot_semantic_result(status)
    guard_failures = _guard_failures(status) if status is not None else []
    if guard_failures:
        sufficient = False
    blocker_codes = [] if sufficient else [blocker_code or reason]
    blocker_codes.extend(guard_failures)
    row = {
        "record_type": "stage12519_private_causal_evidence_slot_semantic_matrix_row_v1",
        "semantic_matrix_row_id_hash": stable_hash({"revalidation": revalidation_id, "slot": slot}),
        "revalidation_id_hash": revalidation_id,
        "acquisition_work_order_id_hash": (
            status.get("acquisition_work_order_id_hash")
            if status is not None
            else (work_order.get("acquisition_work_order_id_hash") if work_order else None)
        ),
        "evidence_slot": slot,
        "proof_class": status.get("proof_class") if status is not None else (work_order.get("proof_class") if work_order else None),
        "stage12516_validated_status_seen": status is not None,
        "stage12515_work_order_seen": work_order is not None,
        "stage12517_identity_context_seen": stage12517_slot_ref_seen,
        "independent_slot_status": status.get("independent_slot_status") if status is not None else None,
        "semantic_sufficient": sufficient,
        "semantic_sufficiency_reason": reason,
        "status_hash_as_proof_allowed": False,
        "digest_hash_as_proof_allowed": False,
        "observed_action_imitation_allowed": False,
        "pass_to_pass_repair_credit_allowed": False,
        "blocker_codes": sorted(set(blocker_codes)),
        "public_safe_status_only": True,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    enforce_no_raw_leaks(row)
    return row


def blocker_record(revalidation_id: str, identity: dict[str, Any], matrix_rows: list[dict[str, Any]]) -> dict[str, Any]:
    blocker_codes = Counter(code for row in matrix_rows for code in row["blocker_codes"])
    row = {
        "record_type": "stage12519_private_causal_evidence_semantic_sufficiency_blocker_v1",
        "semantic_sufficiency_blocker_id_hash": stable_hash({"revalidation": revalidation_id, "blockers": sorted(blocker_codes)}),
        **identity,
        "revalidation_id_hash": revalidation_id,
        "decision": "blocked_private_causal_evidence_semantically_insufficient",
        "semantic_sufficient_slot_count": sum(1 for item in matrix_rows if item["semantic_sufficient"]),
        "required_slot_count": len(FULL_SEVEN_SLOTS),
        "missing_or_insufficient_slots": [item["evidence_slot"] for item in matrix_rows if not item["semantic_sufficient"]],
        "blocker_code_counts": dict(sorted(blocker_codes.items())),
        "status_hash_as_proof_gate": "status_and_digest_hashes_are_never_proof",
        "observed_action_imitation_gate": "observed_action_available_to_labeler_false_and_observed_action_used_as_label_false_required",
        "pass_to_pass_gate": "pass_to_pass_support_only_no_repair_credit",
        "full_seven_slot_gate": "all_seven_slots_required_and_semantic_sufficiency_required",
        "public_safe_status_only": True,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    enforce_no_raw_leaks(row)
    return row


def worklist_record(revalidation_id: str, identity: dict[str, Any], matrix_rows: list[dict[str, Any]]) -> dict[str, Any]:
    missing = [row for row in matrix_rows if not row["semantic_sufficient"]]
    row = {
        "record_type": "stage12519_missing_private_causal_evidence_worklist_v1",
        "missing_evidence_worklist_id_hash": stable_hash({"revalidation": revalidation_id, "slots": [row["evidence_slot"] for row in missing]}),
        **identity,
        "revalidation_id_hash": revalidation_id,
        "bounded_task_kind": "private_causal_evidence_semantic_sufficiency_repair_worklist",
        "target_prior_stage": STAGE12516,
        "slot_count": len(missing),
        "slot_refs": [
            {
                "acquisition_work_order_id_hash": row["acquisition_work_order_id_hash"],
                "evidence_slot": row["evidence_slot"],
                "proof_class": row["proof_class"],
                "current_independent_slot_status": row["independent_slot_status"],
                "blocker_codes": row["blocker_codes"],
                "needed_evidence": "independent_semantic_evidence_or_explicit_no_patch_no_stop_semantics_status_only",
            }
            for row in missing
        ],
        "candidate_output_written_by_stage12519": False,
        "validated_returns_written_by_stage12519": False,
        "stage12503_returns_written_by_stage12519": False,
        "public_safe_status_only": True,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    enforce_no_raw_leaks(row)
    return row


def build(root: Path = ROOT) -> dict[str, Any]:
    out = root / "runs/local/artifacts" / STAGE
    stage12515_out = root / "runs/local/artifacts" / STAGE12515
    stage12516_out = root / "runs/local/artifacts" / STAGE12516
    stage12517_out = root / "runs/local/artifacts" / STAGE12517

    work_orders = [
        row
        for row in read_jsonl(stage12515_out / "private_causal_evidence_acquisition_work_orders.jsonl")
        if row.get("record_type") in {WORK_ORDER_RECORD_TYPE, None}
    ]
    statuses = [
        row
        for row in read_jsonl(stage12516_out / "validated_private_causal_evidence_return_status.jsonl")
        if row.get("record_type") == VALIDATED_RECORD_TYPE
    ]
    worklist = [
        row
        for row in read_jsonl(stage12517_out / "private_causal_evidence_return_candidate_materialization_worklist.jsonl")
        if row.get("record_type") in {WORKLIST_RECORD_TYPE, None}
    ]
    enforce_no_raw_leaks({"work_orders": work_orders, "validated_statuses": statuses, "stage12517_worklist": worklist})

    work_orders_by_revalidation: dict[str, list[dict[str, Any]]] = defaultdict(list)
    work_order_by_revalidation_slot: dict[tuple[str, str], dict[str, Any]] = {}
    for row in work_orders:
        rid = _safe_str(row, "revalidation_id_hash")
        slot = _safe_str(row, "evidence_slot")
        if rid:
            work_orders_by_revalidation[rid].append(row)
            if slot:
                work_order_by_revalidation_slot[(rid, slot)] = row

    statuses_by_revalidation: dict[str, list[dict[str, Any]]] = defaultdict(list)
    status_by_revalidation_slot: dict[tuple[str, str], dict[str, Any]] = {}
    duplicate_slot_counts: Counter[str] = Counter()
    for row in statuses:
        rid = _safe_str(row, "revalidation_id_hash")
        slot = _safe_str(row, "evidence_slot")
        if not rid or not slot:
            continue
        statuses_by_revalidation[rid].append(row)
        key = (rid, slot)
        if key in status_by_revalidation_slot:
            duplicate_slot_counts[slot] += 1
            continue
        status_by_revalidation_slot[key] = row

    stage12517_slot_refs_seen = {
        (_safe_str(ref, "revalidation_id_hash"), _safe_str(ref, "evidence_slot"))
        for task in worklist
        for ref in (task.get("slot_refs") or [])
        if isinstance(ref, dict)
    }
    revalidation_ids = sorted(set(work_orders_by_revalidation) | set(statuses_by_revalidation))

    matrix_rows: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    missing_worklist: list[dict[str, Any]] = []
    proof_ready_ids: set[str] = set()
    complete_seven_ids: set[str] = set()
    identity_mismatch_count = 0

    for rid in revalidation_ids:
        rows = statuses_by_revalidation.get(rid, [])
        identity = _identity_context_for(rid, rows, work_orders_by_revalidation)
        identity_keys = {_identity_key(row) for row in rows}
        if len(identity_keys) > 1:
            identity_mismatch_count += 1
        per_rid: list[dict[str, Any]] = []
        for slot in FULL_SEVEN_SLOTS:
            status = status_by_revalidation_slot.get((rid, slot))
            work_order = work_order_by_revalidation_slot.get((rid, slot))
            per_rid.append(_slot_matrix_row(rid, slot, status, work_order, (rid, slot) in stage12517_slot_refs_seen))
        matrix_rows.extend(per_rid)
        if all(row["stage12516_validated_status_seen"] for row in per_rid):
            complete_seven_ids.add(rid)
        if identity_mismatch_count and len(identity_keys) > 1:
            for row in per_rid:
                if "identity_context_mismatch" not in row["blocker_codes"]:
                    row["blocker_codes"].append("identity_context_mismatch")
                    row["semantic_sufficient"] = False
        if all(row["semantic_sufficient"] for row in per_rid) and len(identity_keys) <= 1:
            proof_ready_ids.add(rid)
        else:
            blockers.append(blocker_record(rid, identity, per_rid))
            missing_worklist.append(worklist_record(rid, identity, per_rid))

    status_counts = Counter(_safe_str(row, "independent_slot_status") for row in statuses)
    slot_counts = Counter(_safe_str(row, "evidence_slot") for row in statuses)
    blocker_code_counts = Counter(code for row in blockers for code, count in row["blocker_code_counts"].items() for _ in range(count))
    contract = {
        "record_type": "stage12519_private_causal_evidence_semantic_sufficiency_contract_v1",
        "stage": STAGE,
        "source_stages": [STAGE12515, STAGE12516, STAGE12517],
        "input_validated_status_ref": "stage12516_validated_private_causal_evidence_return_status_jsonl",
        "input_identity_context_refs": [
            "stage12515_private_causal_evidence_acquisition_work_orders_jsonl",
            "stage12517_private_causal_evidence_return_candidate_materialization_worklist_jsonl",
        ],
        "output_scope": "semantic_sufficiency_blockers_and_missing_evidence_worklist_only",
        "full_seven_slot_set": FULL_SEVEN_SLOTS,
        "non_proof_statuses": sorted(NON_PROOF_STATUSES),
        "semantic_sufficiency_matrix": {
            "default_required_status": SUFFICIENT_STATUS,
            "blocked_unavailable": "never_semantic_proof",
            "validated_absent": "non_proof_unless_explicit_no_patch_or_no_stop_semantics",
            "not_applicable": "non_proof_unless_explicit_no_patch_or_no_stop_semantics",
            "explicit_no_patch_slots": sorted(NO_PATCH_SLOTS),
            "explicit_no_stop_slots": sorted(NO_STOP_SLOTS),
        },
        "status_hash_as_proof_gate": "status_hashes_and_digest_hashes_are_never_sufficient_proof",
        "observed_action_imitation_gate": "observed_action_available_to_labeler_false_and_observed_action_used_as_label_false_required",
        "pass_to_pass_gate": "pass_to_pass_support_only_no_repair_credit",
        "full_seven_slot_gate": "all_seven_slots_required_plus_semantic_sufficiency_required",
        "raw_label_leak_gate": "no_raw_paths_commands_diffs_source_verifier_output_or_policy_labels",
        "public_safe_status_only": True,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    guardrail_scan = {
        "stage": STAGE,
        "scan_passed": True,
        "raw_leak_count": 0,
        "raw_leak_issue_hashes": [],
        "scanned_outputs": [
            "private_causal_evidence_semantic_sufficiency_matrix.jsonl",
            "private_causal_evidence_semantic_sufficiency_blockers.jsonl",
            "missing_private_causal_evidence_worklist.jsonl",
            "private_causal_evidence_semantic_sufficiency_contract.json",
            "summary.json",
        ],
    }
    summary = {
        "stage": STAGE,
        "record_type": "stage12519_private_causal_evidence_semantic_sufficiency_summary_v1",
        "decision": (
            "private_causal_evidence_semantic_sufficiency_passed_status_only_no_admission"
            if proof_ready_ids
            else "blocked_private_causal_evidence_semantically_insufficient"
        ),
        "claim_boundary": (
            "Stage12519 gates Stage12516 validated statuses for semantic sufficiency. "
            "It treats status and digest hashes as non-proof, emits blockers and a "
            "missing-evidence worklist, and writes no training, admission, Level-3, "
            "patch-trace, Stage12503, raw, source, command, diff, or verifier_output."
        ),
        "source_stages": [STAGE12515, STAGE12516, STAGE12517],
        "input_validated_status_count": len(statuses),
        "input_stage12515_work_order_count": len(work_orders),
        "input_stage12517_task_count": len(worklist),
        "grouped_revalidation_record_count": len(revalidation_ids),
        "complete_seven_slot_revalidation_record_count": len(complete_seven_ids),
        "proof_ready_revalidation_record_count": len(proof_ready_ids),
        "semantic_sufficiency_blocker_count": len(blockers),
        "missing_evidence_worklist_count": len(missing_worklist),
        "status_counts": dict(sorted(status_counts.items())),
        "evidence_slot_counts": dict(sorted(slot_counts.items())),
        "non_proof_status_counts": dict(sorted((status, status_counts[status]) for status in NON_PROOF_STATUSES if status_counts[status])),
        "duplicate_slot_status_counts": dict(sorted(duplicate_slot_counts.items())),
        "identity_context_mismatch_count": identity_mismatch_count,
        "blocker_code_counts": dict(sorted(blocker_code_counts.items())),
        "status_hash_as_proof_gate": "status_and_digest_hashes_are_never_proof_or_admission",
        "observed_action_imitation_gate": "observed_action_available_to_labeler_false_and_observed_action_used_as_label_false_required",
        "pass_to_pass_gate": "pass_to_pass_support_only_no_repair_credit",
        "full_seven_slot_completeness_gate": "all_seven_slots_required_plus_semantic_sufficiency_required",
        "semantic_sufficiency_gate": "blocked_unavailable_validated_absent_and_not_applicable_non_proof_unless_explicit_no_patch_no_stop_semantics",
        "raw_label_leak_gate": "no_raw_paths_commands_diffs_source_verifier_output_or_policy_labels",
        "guardrail_scan_passed": True,
        "raw_leak_count": 0,
        "next_stage": "acquire_missing_private_causal_evidence_or_explicit_no_patch_no_stop_semantics_before_any_admission",
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    outputs = {
        "matrix_rows": matrix_rows,
        "blockers": blockers,
        "missing_worklist": missing_worklist,
        "contract": contract,
        "guardrail_scan": guardrail_scan,
        "summary": summary,
    }
    enforce_no_raw_leaks(outputs)

    write_jsonl(out / "private_causal_evidence_semantic_sufficiency_matrix.jsonl", matrix_rows)
    write_jsonl(out / "private_causal_evidence_semantic_sufficiency_blockers.jsonl", blockers)
    write_jsonl(out / "missing_private_causal_evidence_worklist.jsonl", missing_worklist)
    write_json(out / "private_causal_evidence_semantic_sufficiency_contract.json", contract)
    write_json(out / "guardrail_scan.json", guardrail_scan)
    write_json(out / "summary.json", summary)
    write_json(root / "runs/summaries" / f"{STAGE}.json", summary)
    return summary


def main() -> None:
    build(ROOT)


if __name__ == "__main__":
    main()
