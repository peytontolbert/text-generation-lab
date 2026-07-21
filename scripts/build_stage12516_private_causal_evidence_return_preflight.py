#!/usr/bin/env python3
"""Build private causal evidence return preflight artifacts.

Stage12516 consumes Stage12515 private causal evidence acquisition work orders
and publishes public-safe return schemas/templates for private reviewers. If an
optional candidate return file is present beside the Stage12515 work orders, it
validates only hash/status/enumeration shape. It never executes reviewers,
writes Stage12503 returns, admits proofs, emits training rows, or exposes raw
paths, commands, diffs, source, or verifier output.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12516_private_causal_evidence_return_preflight"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12515 = "stage12515_private_causal_evidence_acquisition_work_orders"
STAGE12515_OUT = ROOT / "runs/local/artifacts" / STAGE12515
WORK_ORDERS = STAGE12515_OUT / "private_causal_evidence_acquisition_work_orders.jsonl"
CANDIDATE_RETURNS = STAGE12515_OUT / "private_causal_evidence_return_candidates.jsonl"

RETURN_RECORD_TYPE = "stage12516_private_causal_evidence_return_candidate_v1"
VALIDATED_RECORD_TYPE = "stage12516_validated_private_causal_evidence_return_status_v1"
TEMPLATE_RECORD_TYPE = "stage12516_private_causal_evidence_return_template_v1"

RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:git clone|git apply|pytest\s|python -c|bash -|sh -|curl\s|"
    r"stdout|stderr|traceback|terminal output|command output|verifier output|commit:)\b|"
    r"\b[0-9a-f]{40}\b",
    re.IGNORECASE | re.MULTILINE,
)
SAFE_HASH_RE = re.compile(r"^[0-9a-f]{12,64}$")

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
    "stage12503_return_records_written": 0,
    "candidate_return_records_written": 0,
    "proof_admission_rows_emitted": 0,
}

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
    "evidence_slot",
    "proof_class",
]
REQUIRED_RETURN_FIELDS = [
    "record_type",
    "acquisition_work_order_id_hash",
    *IDENTITY_FIELDS,
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
FORBIDDEN_RETURN_FIELDS = {
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
    "source",
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


class RawLeakError(ValueError):
    pass


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode("utf-8")).hexdigest()[:n]


def is_safe_hash(value: Any) -> bool:
    if not isinstance(value, str) or not SAFE_HASH_RE.fullmatch(value):
        return False
    return len(set(value.lower())) > 1


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
            if key in FORBIDDEN_RETURN_FIELDS:
                issues.append(stable_hash({"forbidden_key": key}))
            issues.extend(scan_raw_leaks(child))
    elif isinstance(value, list):
        for child in value:
            issues.extend(scan_raw_leaks(child))
    return issues


def enforce_no_raw_leaks(value: Any) -> None:
    issues = scan_raw_leaks(value)
    if issues:
        raise RawLeakError(f"stage12516 raw leak guard rejected {len(issues)} public field(s)")


def template_for(work_order: dict[str, Any]) -> dict[str, Any]:
    allowed_statuses = sorted(work_order.get("acceptable_return_statuses") or [])
    row = {
        "record_type": TEMPLATE_RECORD_TYPE,
        "return_template_id_hash": stable_hash(
            {"work_order": work_order.get("acquisition_work_order_id_hash"), "slot": work_order.get("evidence_slot")}
        ),
        "target_return_record_type": RETURN_RECORD_TYPE,
        "source_stage": STAGE12515,
        "acquisition_work_order_id_hash": work_order.get("acquisition_work_order_id_hash"),
        **{field: work_order.get(field) for field in IDENTITY_FIELDS},
        "required_public_safe_return_fields": REQUIRED_RETURN_FIELDS,
        "allowed_independent_slot_statuses": allowed_statuses,
        "required_digest_fields": ["independent_evidence_digest_hash", "causal_review_digest_hash"],
        "required_boolean_false_fields": [
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
        ],
        "required_boolean_true_fields": [
            "candidate_action_set_blinded",
            "label_leak_attestation",
            "model_facing_gold_fields_excluded",
            "repair_credit_requires_before_fail_after_pass_same_verifier",
        ],
        "reviewer_instruction": "return_only_independent_status_enum_and_digest_hashes_no_raw_values",
        "anti_imitation_requirement": "observed_action_must_not_be_available_to_labeler_or_used_as_label",
        "pass_to_pass_rule": "pass_to_pass_status_is_support_only_and_never_repair_credit_without_before_fail_after_pass_same_verifier",
        "proof_boundary": "template_only_no_proof_admission_or_stage12503_return_writing",
        "public_artifact_policy": "hash_enum_status_only_no_raw_paths_commands_diffs_source_or_verifier_output",
        "public_safe_status_only": True,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    enforce_no_raw_leaks(row)
    return row


def validate_return(row: dict[str, Any], work_order: dict[str, Any] | None) -> list[str]:
    reasons: list[str] = []
    if not row.get("acquisition_work_order_id_hash"):
        reasons.append("missing_acquisition_work_order_id_hash")
    if work_order is None:
        reasons.append("unknown_acquisition_work_order_id_hash")
        return sorted(set(reasons))
    for field in REQUIRED_RETURN_FIELDS:
        if field not in row:
            reasons.append(f"missing_{field}")
    if row.get("record_type") != RETURN_RECORD_TYPE:
        reasons.append("schema_version_unsupported")
    for field in IDENTITY_FIELDS:
        if row.get(field) != work_order.get(field):
            reasons.append(f"{field}_mismatch")
    if set(row.keys()) & FORBIDDEN_RETURN_FIELDS:
        reasons.append("forbidden_raw_or_proof_field_present")
    status = row.get("independent_slot_status")
    allowed_statuses = set(work_order.get("acceptable_return_statuses") or [])
    if status not in allowed_statuses:
        reasons.append("unsupported_independent_slot_status")
    if not is_safe_hash(row.get("independent_evidence_digest_hash")):
        reasons.append("independent_evidence_digest_hash_missing_or_unsafe")
    if not is_safe_hash(row.get("causal_review_digest_hash")):
        reasons.append("causal_review_digest_hash_missing_or_unsafe")
    if not is_safe_hash(row.get("private_reviewer_id_hash")):
        reasons.append("private_reviewer_id_hash_missing_or_unsafe")
    if not is_safe_hash(row.get("reviewer_conflict_check_hash")):
        reasons.append("reviewer_conflict_check_hash_missing_or_unsafe")
    if row.get("reviewer_independence_attestation") is not True:
        reasons.append("reviewer_independence_attestation_missing")
    if not isinstance(row.get("slot_status_reason_code"), str) or not row.get("slot_status_reason_code"):
        reasons.append("slot_status_reason_code_missing")
    for field in [
        "raw_private_values_revealed",
        "raw_source_output_included",
        "raw_paths_included",
        "raw_commands_included",
        "raw_diffs_included",
        "raw_verifier_output_included",
        "local_model_authority",
        "policy_label_emitted",
        "proof_or_admission_requested",
        "training_allowed",
        "admission_allowed",
        "stage12503_return_file_written",
        "observed_action_available_to_labeler",
        "observed_action_used_as_label",
        "pass_to_pass_repair_credit_requested",
    ]:
        if row.get(field) is not False:
            reasons.append(f"{field}_not_false")
    for field in [
        "candidate_action_set_blinded",
        "label_leak_attestation",
        "model_facing_gold_fields_excluded",
        "repair_credit_requires_before_fail_after_pass_same_verifier",
    ]:
        if row.get(field) is not True:
            reasons.append(f"{field}_not_true")
    if row.get("stage12503_return_records_written") != 0:
        reasons.append("stage12503_return_records_written_nonzero")
    if row.get("acceptance_criteria_passed") is not True:
        reasons.append("acceptance_criteria_failed")
    if row.get("blocker_codes") not in ([], None):
        reasons.append("return_blocker_codes_not_empty")
    if scan_raw_leaks(row):
        reasons.append("raw_leakage_detected")
    return sorted(set(reasons))


def accepted_record(row: dict[str, Any], work_order: dict[str, Any]) -> dict[str, Any]:
    accepted = {
        "record_type": VALIDATED_RECORD_TYPE,
        "validated_return_status_id_hash": stable_hash(
            {"work_order": work_order.get("acquisition_work_order_id_hash"), "return": row}
        ),
        "source_stage": STAGE12515,
        "acquisition_work_order_id_hash": work_order.get("acquisition_work_order_id_hash"),
        **{field: work_order.get(field) for field in IDENTITY_FIELDS},
        "independent_slot_status": row.get("independent_slot_status"),
        "independent_evidence_digest_hash": row.get("independent_evidence_digest_hash"),
        "causal_review_digest_hash": row.get("causal_review_digest_hash"),
        "slot_status_reason_code": row.get("slot_status_reason_code"),
        "private_causal_evidence_return_validated": True,
        "proof_boundary": "validated_return_status_only_not_proof_admission_or_stage12503_return",
        "proof_admission_blocked_until_downstream_authoritative_ingest": True,
        "public_safe_status_only": True,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
        "validated_private_causal_evidence_returns": 1,
    }
    enforce_no_raw_leaks(accepted)
    return accepted


def rejected_record(row: dict[str, Any], reasons: list[str]) -> dict[str, Any]:
    rejected = {
        "record_type": "stage12516_rejected_private_causal_evidence_return_v1",
        "rejected_return_id_hash": stable_hash({"return": row.get("acquisition_work_order_id_hash"), "reasons": reasons}),
        "acquisition_work_order_id_hash": row.get("acquisition_work_order_id_hash"),
        **{field: row.get(field) for field in IDENTITY_FIELDS},
        "rejection_codes": reasons,
        "public_safe_status_only": True,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    enforce_no_raw_leaks(rejected)
    return rejected


def blocker_record(work_order: dict[str, Any], return_seen: bool) -> dict[str, Any]:
    blockers = [
        "private_causal_evidence_return_absent"
        if not return_seen
        else "private_causal_evidence_return_not_validated",
        "independent_slot_status_and_digest_required_before_proof_or_admission",
        "do_not_write_stage12503_return_from_stage12516_preflight",
    ]
    blocked = {
        "record_type": "stage12516_private_causal_evidence_return_preflight_blocker_v1",
        "blocker_id_hash": stable_hash(
            {"work_order": work_order.get("acquisition_work_order_id_hash"), "return_seen": return_seen}
        ),
        "acquisition_work_order_id_hash": work_order.get("acquisition_work_order_id_hash"),
        **{field: work_order.get(field) for field in IDENTITY_FIELDS},
        "preflight_decision": "blocked",
        "blocker_codes": blockers,
        "public_safe_status_only": True,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    enforce_no_raw_leaks(blocked)
    return blocked


def build(root: Path = ROOT) -> dict[str, Any]:
    out = root / "runs/local/artifacts" / STAGE
    stage12515_out = root / "runs/local/artifacts" / STAGE12515
    work_orders = read_jsonl(stage12515_out / "private_causal_evidence_acquisition_work_orders.jsonl")
    returns_path = stage12515_out / "private_causal_evidence_return_candidates.jsonl"
    candidate_returns = read_jsonl(returns_path)

    templates = [template_for(row) for row in work_orders]
    work_order_by_id = {str(row.get("acquisition_work_order_id_hash")): row for row in work_orders}
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    rejected_work_order_ids: set[str] = set()
    return_id_counts = Counter(str(row.get("acquisition_work_order_id_hash")) for row in candidate_returns)
    for row in candidate_returns:
        work_order_id = str(row.get("acquisition_work_order_id_hash"))
        work_order = work_order_by_id.get(work_order_id)
        reasons = validate_return(row, work_order)
        if return_id_counts[work_order_id] > 1:
            reasons.append("duplicate_return_for_acquisition_work_order")
            reasons = sorted(set(reasons))
        if reasons:
            rejected.append(rejected_record(row, reasons))
            if work_order_id in work_order_by_id:
                rejected_work_order_ids.add(work_order_id)
            continue
        accepted.append(accepted_record(row, work_order_by_id[work_order_id]))

    accepted_work_order_ids = {str(row["acquisition_work_order_id_hash"]) for row in accepted}
    required_slots_by_revalidation: dict[str, set[str]] = {}
    accepted_slots_by_revalidation: dict[str, set[str]] = {}
    for row in work_orders:
        rid = str(row.get("revalidation_id_hash"))
        required_slots_by_revalidation.setdefault(rid, set()).add(str(row.get("evidence_slot")))
    for row in accepted:
        rid = str(row.get("revalidation_id_hash"))
        accepted_slots_by_revalidation.setdefault(rid, set()).add(str(row.get("evidence_slot")))
    complete_revalidation_ids = {
        rid
        for rid, required_slots in required_slots_by_revalidation.items()
        if required_slots and accepted_slots_by_revalidation.get(rid, set()) == required_slots
    }
    incomplete_revalidation_ids = set(required_slots_by_revalidation) - complete_revalidation_ids
    blockers = [
        blocker_record(row, str(row.get("acquisition_work_order_id_hash")) in rejected_work_order_ids)
        for row in work_orders
        if str(row.get("acquisition_work_order_id_hash")) not in accepted_work_order_ids
    ]

    slot_counts = Counter(str(row.get("evidence_slot")) for row in work_orders)
    accepted_status_counts = Counter(str(row.get("independent_slot_status")) for row in accepted)
    non_proof_statuses = {"blocked_unavailable", "validated_absent", "not_applicable"}
    semantically_insufficient_accepted = [
        row for row in accepted if str(row.get("independent_slot_status")) in non_proof_statuses
    ]
    semantic_sufficiency_candidate_count = sum(
        1 for row in accepted if row.get("independent_slot_status") == "validated_present"
    )
    rejection_counts: Counter[str] = Counter()
    blocker_counts: Counter[str] = Counter()
    for row in rejected:
        rejection_counts.update(row["rejection_codes"])
    for row in blockers:
        blocker_counts.update(row["blocker_codes"])

    contract = {
        "record_type": "stage12516_private_causal_evidence_return_preflight_contract_v1",
        "stage": STAGE,
        "source_stage": STAGE12515,
        "candidate_return_input_ref": "stage12515_private_causal_evidence_return_candidates_jsonl_optional",
        "target_return_record_type": RETURN_RECORD_TYPE,
        "output_scope": "templates_validation_status_and_blockers_only",
        "required_return_fields": REQUIRED_RETURN_FIELDS,
        "required_digest_fields": ["independent_evidence_digest_hash", "causal_review_digest_hash"],
        "required_anti_imitation_fields": [
            "observed_action_available_to_labeler",
            "observed_action_used_as_label",
            "candidate_action_set_blinded",
        ],
        "required_label_leak_fields": [
            "label_leak_attestation",
            "model_facing_gold_fields_excluded",
        ],
        "required_pass_to_pass_repair_credit_fields": [
            "pass_to_pass_repair_credit_requested",
            "repair_credit_requires_before_fail_after_pass_same_verifier",
        ],
        "full_record_gate": "all_required_slots_for_a_revalidation_record_must_validate_before_any_downstream_revalidation_can_consider_it_complete",
        "public_artifact_policy": "hash_enum_status_only_no_raw_paths_commands_diffs_source_or_verifier_output",
        "proof_boundary": "no_proof_admission_or_stage12503_return_writing",
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }

    outputs = {
        "templates": templates,
        "accepted": accepted,
        "rejected": rejected,
        "blockers": blockers,
        "contract": contract,
    }
    leak_issues = scan_raw_leaks(outputs)
    if leak_issues:
        raise RawLeakError(f"stage12516 raw leak guard rejected {len(leak_issues)} public field(s)")

    decision = (
        "private_causal_evidence_return_candidates_validated_preflight_only_no_training_or_admission"
        if accepted
        else "private_causal_evidence_return_templates_ready_no_valid_returns_no_training_or_admission"
    )
    summary = {
        "stage": STAGE,
        "record_type": "stage12516_private_causal_evidence_return_preflight_summary_v1",
        "decision": decision,
        "claim_boundary": (
            "Stage12516 emits return templates and validates optional private causal evidence "
            "return records. It blocks proof/admission unless independent slot statuses and "
            "digest hashes are supplied, and it never writes Stage12503 returns."
        ),
        "source_stage": STAGE12515,
        "input_work_order_count": len(work_orders),
        "return_template_count": len(templates),
        "candidate_return_file_present": returns_path.exists(),
        "candidate_return_record_count": len(candidate_returns),
        "validated_private_causal_evidence_return_count": len(accepted),
        "rejected_private_causal_evidence_return_count": len(rejected),
        "blocked_work_order_count": len(blockers),
        "semantically_insufficient_validated_return_count": len(semantically_insufficient_accepted),
        "semantic_sufficiency_candidate_return_count": semantic_sufficiency_candidate_count,
        "complete_revalidation_record_count": len(complete_revalidation_ids),
        "incomplete_revalidation_record_count": len(incomplete_revalidation_ids),
        "all_slots_joined_for_any_revalidation_record": bool(complete_revalidation_ids),
        "proof_ready_revalidation_record_count": 0,
        "evidence_slot_counts": dict(sorted(slot_counts.items())),
        "accepted_status_counts": dict(sorted(accepted_status_counts.items())),
        "accepted_non_proof_status_counts": dict(
            sorted((status, count) for status, count in accepted_status_counts.items() if status in non_proof_statuses)
        ),
        "semantic_sufficiency_gate": "validated_return_status_is_not_causal_proof_blocked_unavailable_validated_absent_and_not_applicable_remain_non_proof",
        "rejection_code_counts": dict(sorted(rejection_counts.items())),
        "blocker_code_counts": dict(sorted(blocker_counts.items())),
        "guardrail_scan_passed": True,
        "raw_leak_count": 0,
        "anti_imitation_gate": "observed_action_available_to_labeler_false_and_observed_action_used_as_label_false_required",
        "pass_to_pass_gate": "pass_to_pass_support_only_no_repair_credit_in_stage12516",
        "label_leak_gate": "model_facing_gold_fields_excluded_required",
        "public_artifact_policy": "hash_enum_status_only_no_raw_paths_commands_diffs_source_or_verifier_output",
        "next_stage": "private_reviewer_returns_or_downstream_authoritative_status_ingest_after_all_required_slot_digests_present",
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }

    write_jsonl(out / "private_causal_evidence_return_templates.jsonl", templates)
    write_jsonl(out / "validated_private_causal_evidence_return_status.jsonl", accepted)
    write_jsonl(out / "rejected_private_causal_evidence_returns.jsonl", rejected)
    write_jsonl(out / "private_causal_evidence_return_preflight_blockers.jsonl", blockers)
    write_json(out / "private_causal_evidence_return_preflight_contract.json", contract)
    write_json(
        out / "guardrail_scan.json",
        {
            "stage": STAGE,
            "scan_passed": True,
            "raw_leak_count": 0,
            "raw_leak_issue_hashes": [],
            "scanned_outputs": [
                "private_causal_evidence_return_templates.jsonl",
                "validated_private_causal_evidence_return_status.jsonl",
                "rejected_private_causal_evidence_returns.jsonl",
                "private_causal_evidence_return_preflight_blockers.jsonl",
                "private_causal_evidence_return_preflight_contract.json",
            ],
        },
    )
    write_json(out / "summary.json", summary)
    write_json(root / "runs/summaries" / f"{STAGE}.json", summary)
    return summary


def main() -> None:
    build(ROOT)


if __name__ == "__main__":
    main()
