#!/usr/bin/env python3
"""Build private causal evidence return candidate materialization worklist.

Stage12517 consumes Stage12516 public-safe templates and blockers, then groups
unresolved slot templates into bounded private reviewer/extractor tasks. It
publishes only a worklist, a runner preflight contract, and a future candidate
return schema. It never fabricates validated returns and never writes
Stage12515, Stage12503, training, admission, Level-3, or patch-trace outputs.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12517_private_causal_evidence_return_candidate_worklist"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12516 = "stage12516_private_causal_evidence_return_preflight"
STAGE12516_OUT = ROOT / "runs/local/artifacts" / STAGE12516
TEMPLATES = STAGE12516_OUT / "private_causal_evidence_return_templates.jsonl"
BLOCKERS = STAGE12516_OUT / "private_causal_evidence_return_preflight_blockers.jsonl"
VALIDATED_STATUS = STAGE12516_OUT / "validated_private_causal_evidence_return_status.jsonl"
NON_PROOF_STATUSES = {"blocked_unavailable", "validated_absent", "not_applicable"}

TEMPLATE_RECORD_TYPE = "stage12516_private_causal_evidence_return_template_v1"
BLOCKER_RECORD_TYPE = "stage12516_private_causal_evidence_return_preflight_blocker_v1"
TARGET_RETURN_RECORD_TYPE = "stage12516_private_causal_evidence_return_candidate_v1"
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
SLOT_FIELDS = [*IDENTITY_FIELDS, "acquisition_work_order_id_hash", "evidence_slot", "proof_class"]
REQUIRED_CANDIDATE_FIELDS = [
    "record_type",
    "acquisition_work_order_id_hash",
    *IDENTITY_FIELDS,
    "evidence_slot",
    "proof_class",
    "private_reviewer_id_hash",
    "reviewer_conflict_check_hash",
    "reviewer_independence_attestation",
    "independent_slot_status",
    "independent_evidence_digest_hash",
    "slot_status_reason_code",
    "causal_review_digest_hash",
    "raw_private_values_revealed",
    "raw_source_output_included",
    "raw_paths_included",
    "raw_commands_included",
    "raw_diffs_included",
    "raw_verifier_output_included",
    "local_model_authority",
    "policy_label_emitted",
    "proof_or_admission_requested",
    "acceptance_criteria_passed",
    "observed_action_available_to_labeler",
    "observed_action_used_as_label",
    "candidate_action_set_blinded",
    "label_leak_attestation",
    "model_facing_gold_fields_excluded",
    "pass_to_pass_repair_credit_requested",
    "repair_credit_requires_before_fail_after_pass_same_verifier",
    "blocker_codes",
    "training_allowed",
    "admission_allowed",
    "stage12503_return_file_written",
    "stage12503_return_records_written",
]
REQUIRED_FALSE_FIELDS = [
    "raw_private_values_revealed",
    "raw_source_output_included",
    "raw_paths_included",
    "raw_commands_included",
    "raw_diffs_included",
    "raw_verifier_output_included",
    "local_model_authority",
    "policy_label_emitted",
    "proof_or_admission_requested",
    "observed_action_available_to_labeler",
    "observed_action_used_as_label",
    "pass_to_pass_repair_credit_requested",
    "training_allowed",
    "admission_allowed",
    "stage12503_return_file_written",
]
REQUIRED_TRUE_FIELDS = [
    "candidate_action_set_blinded",
    "label_leak_attestation",
    "model_facing_gold_fields_excluded",
    "repair_credit_requires_before_fail_after_pass_same_verifier",
]

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
    "stage12515_candidate_return_file_written": False,
    "stage12503_return_file_written": False,
    "candidate_return_file_written": False,
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
    "stage12515_candidate_return_records_written": 0,
    "stage12503_return_records_written": 0,
    "candidate_return_records_written": 0,
    "validated_private_causal_evidence_return_count": 0,
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
        raise RawLeakError(f"stage12517 raw leak guard rejected {len(issues)} public field(s)")


def _safe_str(row: dict[str, Any], field: str) -> str:
    value = row.get(field)
    return value if isinstance(value, str) else ""


def _status_allowed_by_slot(templates: list[dict[str, Any]]) -> dict[str, list[str]]:
    allowed: dict[str, set[str]] = defaultdict(set)
    for row in templates:
        slot = _safe_str(row, "evidence_slot")
        for status in row.get("allowed_independent_slot_statuses") or []:
            if isinstance(status, str):
                allowed[slot].add(status)
    return {slot: sorted(statuses) for slot, statuses in sorted(allowed.items())}


def _slot_ref(
    template: dict[str, Any],
    blocker: dict[str, Any] | None,
    non_proof_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = {
        field: template.get(field)
        for field in SLOT_FIELDS
    }
    row.update(
        {
            "return_template_id_hash": template.get("return_template_id_hash"),
            "blocker_id_hash": blocker.get("blocker_id_hash") if blocker else None,
            "stage12516_blocker_codes": sorted(blocker.get("blocker_codes") or []) if blocker else [],
            "stage12516_non_proof_status": non_proof_status.get("independent_slot_status") if non_proof_status else None,
            "stage12516_non_proof_status_id_hash": non_proof_status.get("validated_return_status_id_hash") if non_proof_status else None,
            "allowed_independent_slot_statuses": sorted(template.get("allowed_independent_slot_statuses") or []),
            "target_return_record_type": TARGET_RETURN_RECORD_TYPE,
            "required_candidate_fields": REQUIRED_CANDIDATE_FIELDS,
            "required_boolean_false_fields": REQUIRED_FALSE_FIELDS,
            "required_boolean_true_fields": REQUIRED_TRUE_FIELDS,
            "public_safe_status_only": True,
        }
    )
    enforce_no_raw_leaks(row)
    return row


def materialization_task(
    group_key: tuple[str, str, str, str, str],
    templates: list[dict[str, Any]],
    blockers_by_work_order: dict[str, dict[str, Any]],
    non_proof_status_by_work_order: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    revalidation_id, source_stage, language_family, task_family, source_kind = group_key
    ordered = sorted(templates, key=lambda row: FULL_SEVEN_SLOTS.index(_safe_str(row, "evidence_slot")))
    slot_refs = [
        _slot_ref(
            row,
            blockers_by_work_order.get(str(row.get("acquisition_work_order_id_hash"))),
            (non_proof_status_by_work_order or {}).get(str(row.get("acquisition_work_order_id_hash"))),
        )
        for row in ordered
    ]
    present_slots = [_safe_str(row, "evidence_slot") for row in ordered]
    missing_slots = [slot for slot in FULL_SEVEN_SLOTS if slot not in set(present_slots)]
    task = {
        "record_type": WORKLIST_RECORD_TYPE,
        "candidate_materialization_task_id_hash": stable_hash(
            {
                "revalidation": revalidation_id,
                "source": source_stage,
                "language": language_family,
                "task": task_family,
                "slots": present_slots,
            }
        ),
        "source_stage": source_stage,
        "source_kind": source_kind,
        "language_family": language_family,
        "task_family": task_family,
        "revalidation_id_hash": revalidation_id,
        "request_id_hash": ordered[0].get("request_id_hash") if ordered else None,
        "work_item_id_hash": ordered[0].get("work_item_id_hash") if ordered else None,
        "packet_id_hash": ordered[0].get("packet_id_hash") if ordered else None,
        "root_or_window_hash": ordered[0].get("root_or_window_hash") if ordered else None,
        "source_template_stage": STAGE12516,
        "target_future_return_record_type": TARGET_RETURN_RECORD_TYPE,
        "bounded_task_kind": "private_reviewer_or_extractor_candidate_return_materialization",
        "max_slot_count": 7,
        "slot_count": len(slot_refs),
        "slot_refs": slot_refs,
        "full_seven_slot_completeness_required": True,
        "full_seven_slot_set": FULL_SEVEN_SLOTS,
        "missing_from_full_seven_slot_set": missing_slots,
        "runner_preflight_decision": "ready_for_private_runner_assignment" if slot_refs else "blocked_empty_task",
        "future_candidate_output_ref": "private_causal_evidence_return_candidates_jsonl_for_stage12516_only",
        "candidate_output_written_by_stage12517": False,
        "candidate_return_records_written": 0,
        "runner_must_not_emit_validated_returns": True,
        "runner_must_not_write_stage12515_candidate_returns_in_preflight": True,
        "runner_must_not_write_stage12503_returns": True,
        "anti_imitation_guard": "observed_action_unavailable_to_labeler_and_not_used_as_label_required",
        "label_leak_guard": "candidate_action_set_blinded_and_model_facing_gold_fields_excluded_required",
        "pass_to_pass_guard": "pass_to_pass_is_support_status_only_not_repair_credit",
        "raw_leak_guard": "hash_enum_digest_status_only_no_raw_paths_commands_diffs_source_or_verifier_output",
        "public_safe_status_only": True,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    enforce_no_raw_leaks(task)
    return task


def candidate_return_schema(templates: list[dict[str, Any]]) -> dict[str, Any]:
    schema = {
        "record_type": "stage12517_private_causal_evidence_return_candidate_schema_v1",
        "stage": STAGE,
        "source_stage": STAGE12516,
        "target_future_return_record_type": TARGET_RETURN_RECORD_TYPE,
        "required_fields": REQUIRED_CANDIDATE_FIELDS,
        "required_digest_fields": ["independent_evidence_digest_hash", "causal_review_digest_hash"],
        "required_boolean_false_fields": REQUIRED_FALSE_FIELDS,
        "required_boolean_true_fields": REQUIRED_TRUE_FIELDS,
        "allowed_independent_slot_statuses_by_evidence_slot": _status_allowed_by_slot(templates),
        "required_full_seven_slot_completeness": FULL_SEVEN_SLOTS,
        "candidate_return_boundary": "future_private_runner_may_emit_candidates_for_stage12516_validation_only",
        "not_validated_return_boundary": "schema_is_not_a_validated_return_and_confers_no_proof_or_admission",
        "anti_imitation_guard": "observed_action_available_to_labeler_false_observed_action_used_as_label_false_candidate_action_set_blinded_true",
        "label_leak_guard": "label_leak_attestation_true_and_model_facing_gold_fields_excluded_true",
        "pass_to_pass_guard": "pass_to_pass_repair_credit_requested_false",
        "raw_leak_guard": "no_raw_paths_commands_diffs_source_verifier_output_or_private_values",
        "public_safe_status_only": True,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    enforce_no_raw_leaks(schema)
    return schema


def build(root: Path = ROOT) -> dict[str, Any]:
    out = root / "runs/local/artifacts" / STAGE
    stage12516_out = root / "runs/local/artifacts" / STAGE12516
    templates = [
        row
        for row in read_jsonl(stage12516_out / "private_causal_evidence_return_templates.jsonl")
        if row.get("record_type") == TEMPLATE_RECORD_TYPE
    ]
    blockers = [
        row
        for row in read_jsonl(stage12516_out / "private_causal_evidence_return_preflight_blockers.jsonl")
        if row.get("record_type") == BLOCKER_RECORD_TYPE
    ]
    validated_status = read_jsonl(stage12516_out / "validated_private_causal_evidence_return_status.jsonl")
    blockers_by_work_order = {
        str(row.get("acquisition_work_order_id_hash")): row
        for row in blockers
        if row.get("acquisition_work_order_id_hash")
    }
    non_proof_status_by_work_order = {
        str(row.get("acquisition_work_order_id_hash")): row
        for row in validated_status
        if row.get("independent_slot_status") in NON_PROOF_STATUSES and row.get("acquisition_work_order_id_hash")
    }
    unresolved_work_order_ids = set(blockers_by_work_order) | set(non_proof_status_by_work_order)
    unresolved_templates = [
        row
        for row in templates
        if str(row.get("acquisition_work_order_id_hash")) in unresolved_work_order_ids
        and _safe_str(row, "evidence_slot") in FULL_SEVEN_SLOTS
    ]

    grouped: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in unresolved_templates:
        grouped[
            (
                _safe_str(row, "revalidation_id_hash"),
                _safe_str(row, "source_stage"),
                _safe_str(row, "language_family"),
                _safe_str(row, "task_family"),
                _safe_str(row, "source_kind"),
            )
        ].append(row)
    worklist = [
        materialization_task(group_key, rows, blockers_by_work_order, non_proof_status_by_work_order)
        for group_key, rows in sorted(grouped.items())
    ]
    schema = candidate_return_schema(templates)
    slot_counts = Counter(_safe_str(row, "evidence_slot") for row in unresolved_templates)
    task_slot_counts = Counter(str(row["slot_count"]) for row in worklist)
    full_seven_task_count = sum(1 for row in worklist if row["slot_count"] == 7 and not row["missing_from_full_seven_slot_set"])
    blocker_code_counts: Counter[str] = Counter()
    non_proof_status_counts = Counter(str(row.get("independent_slot_status")) for row in validated_status if row.get("independent_slot_status") in NON_PROOF_STATUSES)
    for row in blockers:
        blocker_code_counts.update(row.get("blocker_codes") or [])

    contract = {
        "record_type": "stage12517_private_causal_evidence_return_candidate_worklist_contract_v1",
        "stage": STAGE,
        "source_stage": STAGE12516,
        "input_templates_ref": "stage12516_private_causal_evidence_return_templates_jsonl",
        "input_blockers_ref": "stage12516_private_causal_evidence_return_preflight_blockers_jsonl",
        "input_non_proof_validated_status_ref": "stage12516_validated_private_causal_evidence_return_status_jsonl",
        "non_proof_statuses_remain_unresolved": sorted(NON_PROOF_STATUSES),
        "output_scope": "bounded_private_runner_worklist_and_candidate_schema_only",
        "target_future_return_record_type": TARGET_RETURN_RECORD_TYPE,
        "full_seven_slot_completeness_required": True,
        "full_seven_slot_set": FULL_SEVEN_SLOTS,
        "no_candidate_return_materialization_in_stage": True,
        "anti_imitation_guard": "observed_action_not_available_and_not_used_as_label",
        "label_leak_guard": "gold_fields_excluded_from_model_facing_materials",
        "pass_to_pass_guard": "pass_to_pass_status_never_repair_credit",
        "raw_leak_guard": "hash_enum_digest_status_only",
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
            "private_causal_evidence_return_candidate_materialization_worklist.jsonl",
            "private_causal_evidence_return_candidate_schema.json",
            "private_causal_evidence_return_candidate_worklist_contract.json",
            "runner_preflight.json",
        ],
    }
    runner_preflight = {
        "record_type": "stage12517_private_causal_evidence_return_candidate_runner_preflight_v1",
        "stage": STAGE,
        "private_runner_assignment_ready": bool(worklist),
        "bounded_task_count": len(worklist),
        "max_slots_per_task": 7,
        "runner_output_target": "future_private_causal_evidence_return_candidates_jsonl_for_stage12516_validation",
        "candidate_output_written_by_stage12517": False,
        "validated_returns_written_by_stage12517": False,
        "stage12515_candidate_returns_written_by_stage12517": False,
        "stage12503_returns_written_by_stage12517": False,
        "anti_imitation_required": True,
        "label_leak_guard_required": True,
        "pass_to_pass_not_repair_required": True,
        "full_seven_slot_completeness_required": True,
        "raw_leak_guard_required": True,
        "public_safe_status_only": True,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    summary = {
        "stage": STAGE,
        "record_type": "stage12517_private_causal_evidence_return_candidate_worklist_summary_v1",
        "decision": "private_causal_evidence_return_candidate_materialization_worklist_ready_no_returns_written",
        "claim_boundary": (
            "Stage12517 builds bounded private reviewer/extractor worklist tasks and a future "
            "candidate-return schema only. It does not fabricate validated returns, write "
            "candidate returns, write Stage12503 returns, train, admit, or emit proof rows."
        ),
        "source_stage": STAGE12516,
        "input_template_count": len(templates),
        "input_blocker_count": len(blockers),
        "input_validated_status_count": len(validated_status),
        "input_non_proof_validated_status_count": sum(non_proof_status_counts.values()),
        "non_proof_status_counts": dict(sorted(non_proof_status_counts.items())),
        "unresolved_template_count": len(unresolved_templates),
        "candidate_materialization_task_count": len(worklist),
        "full_seven_slot_task_count": full_seven_task_count,
        "incomplete_seven_slot_task_count": len(worklist) - full_seven_task_count,
        "evidence_slot_counts": dict(sorted(slot_counts.items())),
        "task_slot_count_distribution": dict(sorted(task_slot_counts.items())),
        "blocker_code_counts": dict(sorted(blocker_code_counts.items())),
        "future_candidate_schema_required_field_count": len(REQUIRED_CANDIDATE_FIELDS),
        "runner_preflight_ready": bool(worklist),
        "candidate_output_written_by_stage12517": False,
        "guardrail_scan_passed": True,
        "raw_leak_count": 0,
        "anti_imitation_gate": "observed_action_available_to_labeler_false_and_observed_action_used_as_label_false_required",
        "label_leak_gate": "label_leak_attestation_true_and_model_facing_gold_fields_excluded_true_required",
        "pass_to_pass_gate": "pass_to_pass_support_only_no_repair_credit",
        "full_seven_slot_completeness_gate": "all_seven_private_causal_evidence_slots_required_before_downstream_completion",
        "non_proof_status_gate": "blocked_unavailable_validated_absent_and_not_applicable_remain_unresolved_not_training_ready",
        "public_artifact_policy": "hash_enum_digest_status_only_no_raw_paths_commands_diffs_source_or_verifier_output",
        "next_stage": "private_runner_may_materialize_status_only_candidates_for_stage12516_validation",
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }

    outputs = {
        "worklist": worklist,
        "schema": schema,
        "contract": contract,
        "runner_preflight": runner_preflight,
        "summary": summary,
        "guardrail_scan": guardrail_scan,
    }
    enforce_no_raw_leaks(outputs)

    write_jsonl(out / "private_causal_evidence_return_candidate_materialization_worklist.jsonl", worklist)
    write_json(out / "private_causal_evidence_return_candidate_schema.json", schema)
    write_json(out / "private_causal_evidence_return_candidate_worklist_contract.json", contract)
    write_json(out / "runner_preflight.json", runner_preflight)
    write_json(out / "guardrail_scan.json", guardrail_scan)
    write_json(out / "summary.json", summary)
    write_json(root / "runs/summaries" / f"{STAGE}.json", summary)
    return summary


def main() -> None:
    build(ROOT)


if __name__ == "__main__":
    main()
