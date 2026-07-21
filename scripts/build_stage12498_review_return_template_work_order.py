#!/usr/bin/env python3
"""Public-safe Stage12495 review-return template work order.

Stage12498 is a recovery stage after Stage12497 blocks on zero validated
policy-label returns. It does not validate, admit, train, hydrate, replay, or
package rows. It only emits a public-safe operator work order and placeholder
schema for producing Stage12495 review returns that Stage12496 can validate.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12498_review_return_template_work_order"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12495 = "stage12495_independent_policy_label_and_action_set_review"
STAGE12496 = "stage12496_policy_label_review_return_validator"
STAGE12497 = "stage12497_renderer_state_delta_source_reopen_gate"

WORK_ITEMS = ROOT / "runs/local/artifacts" / STAGE12495 / "independent_policy_label_review_work_items.jsonl"
STAGE12495_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12495}.json"
STAGE12496_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12496}.json"
STAGE12497_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12497}.json"
STAGE12497_WORK_ITEMS = ROOT / "runs/local/artifacts" / STAGE12497 / "renderer_state_delta_source_reopen_work_items.jsonl"
STAGE12497_BLOCKED = ROOT / "runs/local/artifacts" / STAGE12497 / "blocked_gate_refs.jsonl"

RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:git clone|git apply|pytest\s|python -c|bash -|sh -|curl\s|"
    r"stdout|stderr|traceback|terminal output|command output)\b|"
    r"\b[0-9a-f]{40}\b",
    re.IGNORECASE | re.MULTILINE,
)

FALSE_GUARDS = {
    "training_allowed": False,
    "admission_allowed": False,
    "packaging_allowed": False,
    "execution_performed_by_stage": False,
    "hydration_performed_by_stage": False,
    "replay_performed_by_stage": False,
    "network_performed_by_stage": False,
}

ZERO_GUARDS = {
    "training_rows_emitted": 0,
    "admitted_rows": 0,
    "reviewed_train_support_rows": 0,
    "proof_grade_repair_rows": 0,
    "external_repair_credit_count": 0,
    "sealed_eval_rows": 0,
    "independent_policy_labels_validated": 0,
    "independent_policy_labels_admitted": 0,
}

REQUIRED_RETURN_FIELDS = [
    "record_type",
    "review_item_id_hash",
    "packet_id_hash",
    "source_candidate_id_hash",
    "work_item_id_hash",
    "task_family",
    "language_family",
    "reviewer_id_hash",
    "reviewer_independence_attestation",
    "reviewer_conflict_check_hash",
    "candidate_option_set_hash",
    "candidate_action_set_rewritten_hash",
    "candidate_action_set_rewrite_rationale_hash",
    "independent_policy_label_hash",
    "independent_policy_label_rationale_hash",
    "state_before_semantic_review_hash",
    "state_delta_semantic_review_hash",
    "hard_negative_audit_hash",
    "anti_shortcut_audit_hash",
    "option_permutation_audit_hash",
    "deterministic_blinded_shuffle_hash",
    "observed_action_available_to_labeler",
    "observed_action_used_as_label",
    "local_model_authority",
    "raw_private_values_revealed",
    "event_local_promoted",
    "acceptance_criteria_passed",
    "blocker_codes",
    "training_allowed",
    "admission_allowed",
    "admitted_rows",
    "training_rows_emitted",
    "candidate_action_family_count",
    "hard_negative_count",
]

ACCEPTANCE_CRITERIA = [
    "all_required_stage12496_fields_present",
    "record_type_is_stage12496_policy_label_review_return_v1",
    "ids_and_task_metadata_match_stage12495_work_item",
    "reviewer_independence_attestation_true",
    "reviewer_conflict_check_hash_present",
    "candidate_option_set_hash_matches_work_item",
    "candidate_action_set_rewritten_hash_present_and_distinct_from_original",
    "candidate_action_set_rewrite_rationale_hash_present",
    "independent_policy_label_hash_present",
    "independent_policy_label_rationale_hash_present",
    "state_before_semantic_review_hash_present",
    "state_delta_semantic_review_hash_present",
    "hard_negative_audit_hash_present",
    "anti_shortcut_audit_hash_present",
    "option_permutation_audit_hash_present",
    "deterministic_blinded_shuffle_hash_present",
    "candidate_action_family_count_at_least_6",
    "hard_negative_count_at_least_2",
    "acceptance_criteria_passed_true",
    "blocker_codes_empty",
    "local_model_authority_false",
    "raw_private_values_revealed_false",
    "observed_action_available_to_labeler_false",
    "observed_action_used_as_label_false",
    "event_local_promoted_false",
    "training_allowed_false",
    "admission_allowed_false",
    "training_rows_emitted_zero",
    "admitted_rows_zero",
]

DETERMINISTIC_BLINDED_SHUFFLE_REQUIREMENTS = [
    "derive_shuffle_seed_from_review_item_id_hash_and_reviewer_conflict_check_hash",
    "shuffle_candidate_actions_before_label_selection",
    "store_only_deterministic_blinded_shuffle_hash",
    "do_not_store_or_expose_unblinded_order",
    "do_not_use_observed_action_or_local_model_output_in_permutation",
]

HARD_NEGATIVE_REQUIREMENTS = [
    "include_at_least_two_plausible_wrong_actions",
    "include_patch_too_early_negative_when_relevant",
    "include_finish_too_early_negative_when_relevant",
    "include_insufficient_evidence_or_not_exercised_negative_when_relevant",
    "document_negative_rationale_only_as_hash",
]

EVENT_LOCAL_RULES = [
    "event_local_transition_observation_items_are_support_only",
    "do_not_create_stage12496_return_for_event_local_items",
    "event_local_promoted_must_remain_false",
    "event_local_items_do_not_become_level3_policy_labels",
    "event_local_items_do_not_become_next_action_targets",
]


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode("utf-8")).hexdigest()[:n]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
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


def scan(value: Any) -> list[str]:
    issues: list[str] = []
    if isinstance(value, str):
        if RAW_LEAK_RE.search(value):
            issues.append(stable_hash(value))
    elif isinstance(value, dict):
        for child in value.values():
            issues.extend(scan(child))
    elif isinstance(value, list):
        for child in value:
            issues.extend(scan(child))
    return issues


def template_schema() -> dict[str, Any]:
    schema = {field: f"<{field}>" for field in REQUIRED_RETURN_FIELDS}
    schema.update(
        {
            "record_type": "stage12496_policy_label_review_return_v1",
            "reviewer_independence_attestation": True,
            "observed_action_available_to_labeler": False,
            "observed_action_used_as_label": False,
            "local_model_authority": False,
            "raw_private_values_revealed": False,
            "event_local_promoted": False,
            "acceptance_criteria_passed": True,
            "blocker_codes": [],
            "training_allowed": False,
            "admission_allowed": False,
            "admitted_rows": 0,
            "training_rows_emitted": 0,
            "candidate_action_family_count": "<integer_at_least_6>",
            "hard_negative_count": "<integer_at_least_2>",
        }
    )
    return {
        "record_type": "stage12498_placeholder_return_schema_v1",
        "placeholder_only": True,
        "stage12496_return_record": schema,
        "required_fields": REQUIRED_RETURN_FIELDS,
        "acceptance_criteria": ACCEPTANCE_CRITERIA,
        "deterministic_blinded_shuffle_requirements": DETERMINISTIC_BLINDED_SHUFFLE_REQUIREMENTS,
        "hard_negative_requirements": HARD_NEGATIVE_REQUIREMENTS,
        "event_local_non_promotion_rules": EVENT_LOCAL_RULES,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }


def return_slot(row: dict[str, Any]) -> dict[str, Any]:
    task_family = row.get("task_family")
    return {
        "record_type": "stage12498_review_return_work_order_slot_v1",
        "slot_id_hash": stable_hash({"review_item": row.get("review_item_id_hash")}),
        "review_item_id_hash": row.get("review_item_id_hash"),
        "packet_id_hash": row.get("packet_id_hash"),
        "source_candidate_id_hash": row.get("source_candidate_id_hash"),
        "work_item_id_hash": row.get("work_item_id_hash"),
        "task_family": task_family,
        "language_family": row.get("language_family"),
        "candidate_option_set_hash": row.get("candidate_option_set_hash"),
        "candidate_option_count": row.get("candidate_option_count"),
        "return_eligible_for_stage12496": True,
        "operator_action": "produce_independent_stage12496_review_return",
        "copy_these_hash_fields_exactly": [
            "review_item_id_hash",
            "packet_id_hash",
            "source_candidate_id_hash",
            "work_item_id_hash",
            "task_family",
            "language_family",
            "candidate_option_set_hash",
        ],
        "must_fill_hash_fields": [
            "reviewer_id_hash",
            "reviewer_conflict_check_hash",
            "candidate_action_set_rewritten_hash",
            "candidate_action_set_rewrite_rationale_hash",
            "independent_policy_label_hash",
            "independent_policy_label_rationale_hash",
            "state_before_semantic_review_hash",
            "state_delta_semantic_review_hash",
            "hard_negative_audit_hash",
            "anti_shortcut_audit_hash",
            "option_permutation_audit_hash",
            "deterministic_blinded_shuffle_hash",
        ],
        "acceptance_criteria": ACCEPTANCE_CRITERIA,
        "deterministic_blinded_shuffle_requirements": DETERMINISTIC_BLINDED_SHUFFLE_REQUIREMENTS,
        "hard_negative_requirements": HARD_NEGATIVE_REQUIREMENTS,
        "public_safe_context": {
            "candidate_options_public_safe": row.get("candidate_options_public_safe", []),
            "task_family_acceptance_criteria": row.get("acceptance_criteria", []),
            "source_record_kind": row.get("source_record_kind"),
        },
        "forbidden_authority": {
            "local_model_authority": False,
            "observed_action_available_to_labeler": False,
            "observed_action_used_as_label": False,
            "raw_private_values_revealed": False,
        },
        "local_model_authority": False,
        "observed_action_available_to_labeler": False,
        "observed_action_used_as_label": False,
        "observed_action_access_allowed_count": 0,
        "raw_private_values_revealed": False,
        "fixed_zero_fields": {
            "admitted_rows": 0,
            "training_rows_emitted": 0,
        },
        "claim_boundary": {
            "review_return_work_order": True,
            "validated_policy_label_review": False,
            "reviewed_train_support": False,
            "level3_closed_loop_episode": False,
            "proof_grade_repair": False,
        },
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }


def excluded_event_local(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_type": "stage12498_event_local_non_promotion_ref_v1",
        "event_local_ref_hash": stable_hash({"event_local": row.get("review_item_id_hash")}),
        "review_item_id_hash": row.get("review_item_id_hash"),
        "packet_id_hash": row.get("packet_id_hash"),
        "task_family": row.get("task_family"),
        "language_family": row.get("language_family"),
        "return_eligible_for_stage12496": False,
        "reason_codes": [
            "event_local_support_only_no_policy_target",
            "stage12496_rejects_event_local_policy_label_attempt",
            "event_local_non_promotion_required",
        ],
        "event_local_non_promotion_rules": EVENT_LOCAL_RULES,
        "event_local_promoted": False,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stage12495_summary = read_json(STAGE12495_SUMMARY)
    stage12496_summary = read_json(STAGE12496_SUMMARY)
    stage12497_summary = read_json(STAGE12497_SUMMARY)
    work_items = read_jsonl(WORK_ITEMS)
    stage12497_work_items = read_jsonl(STAGE12497_WORK_ITEMS)
    stage12497_blocked = read_jsonl(STAGE12497_BLOCKED)

    eligible = [row for row in work_items if row.get("task_family") != "event_local_transition_observation"]
    event_local = [row for row in work_items if row.get("task_family") == "event_local_transition_observation"]
    work_order_slots = [return_slot(row) for row in eligible]
    event_local_refs = [excluded_event_local(row) for row in event_local]
    schema = template_schema()

    language_counts = Counter(row.get("language_family") for row in work_order_slots)
    task_counts = Counter(row.get("task_family") for row in work_order_slots)
    issue_hashes = scan(
        {
            "schema": schema,
            "work_order_slots": work_order_slots,
            "event_local_refs": event_local_refs,
        }
    )
    guardrail = {
        "stage": STAGE,
        "scan_passed": not issue_hashes,
        "raw_leak_count": len(issue_hashes),
        "issue_hashes": issue_hashes[:80],
    }
    summary = {
        "stage": STAGE,
        "record_type": "stage12498_review_return_template_work_order_summary_v1",
        "decision": "review_return_work_order_ready_training_blocked"
        if work_order_slots and guardrail["scan_passed"]
        else "blocked_empty_or_guardrail_failed",
        "source_stage_refs": [STAGE12495, STAGE12496, STAGE12497],
        "stage12495_decision": stage12495_summary.get("decision"),
        "stage12496_decision": stage12496_summary.get("decision"),
        "stage12497_decision": stage12497_summary.get("decision"),
        "stage12495_review_item_count": stage12495_summary.get("review_item_count", len(work_items)),
        "stage12496_accepted_return_count": stage12496_summary.get("accepted_return_count", 0),
        "stage12496_missing_return_count": stage12496_summary.get("missing_return_count", len(work_items)),
        "stage12497_work_item_count": stage12497_summary.get("work_item_count", len(stage12497_work_items)),
        "stage12497_blocked_gate_count": stage12497_summary.get("blocked_gate_count", len(stage12497_blocked)),
        "input_work_item_count": len(work_items),
        "return_eligible_work_item_count": len(eligible),
        "review_return_work_order_slot_count": len(work_order_slots),
        "placeholder_schema_count": 1,
        "sample_schema_uses_placeholders_only": True,
        "event_local_input_count": len(event_local),
        "event_local_excluded_count": len(event_local_refs),
        "event_local_promoted_count": 0,
        "local_model_suggestions_authoritative_count": 0,
        "local_model_authority_violation_count": 0,
        "observed_action_access_allowed_count": 0,
        "observed_action_imitation_failure_count": 0,
        "private_raw_value_output_count": 0,
        "raw_path_output_count": 0,
        "raw_command_output_count": 0,
        "raw_source_output_count": 0,
        "deterministic_blinded_shuffle_required_count": len(work_order_slots),
        "hard_negative_required_count": len(work_order_slots),
        "minimum_hard_negative_count_per_return": 2,
        "minimum_candidate_action_family_count_per_return": 6,
        "stage12496_required_field_count": len(REQUIRED_RETURN_FIELDS),
        "acceptance_criteria_count": len(ACCEPTANCE_CRITERIA),
        "language_counts": dict(sorted(language_counts.items())),
        "task_family_counts": dict(sorted(task_counts.items())),
        "raw_leak_count": guardrail["raw_leak_count"],
        "next_stage": "stage12496_policy_label_review_return_validator_after_operator_returns",
        **FALSE_GUARDS,
        **ZERO_GUARDS,
        "summary_hash": stable_hash(
            {
                "eligible": len(eligible),
                "event_local": len(event_local),
                "stage12496_missing": stage12496_summary.get("missing_return_count"),
                "stage12497_blocked": stage12497_summary.get("blocked_gate_count"),
            }
        ),
    }

    write_json(OUT / "review_return_operator_work_order.json", {
        "record_type": "stage12498_review_return_operator_work_order_v1",
        "purpose": "produce_public_safe_independent_review_returns_for_stage12495",
        "target_validator_stage": STAGE12496,
        "required_fields": REQUIRED_RETURN_FIELDS,
        "acceptance_criteria": ACCEPTANCE_CRITERIA,
        "deterministic_blinded_shuffle_requirements": DETERMINISTIC_BLINDED_SHUFFLE_REQUIREMENTS,
        "hard_negative_requirements": HARD_NEGATIVE_REQUIREMENTS,
        "event_local_non_promotion_rules": EVENT_LOCAL_RULES,
        "operator_steps": [
            "select_one_return_eligible_slot",
            "copy_hash_identity_fields_exactly",
            "perform_independent_policy_label_review_without_observed_action_access",
            "rewrite_candidate_action_set_with_required_hard_negatives",
            "record_only_hashes_for_private_review_material",
            "keep_all_training_and_admission_fields_false_or_zero",
            "do_not_create_returns_for_event_local_non_promotion_refs",
        ],
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    })
    write_json(OUT / "sample_review_return_schema.json", schema)
    write_jsonl(OUT / "review_return_work_order_slots.jsonl", work_order_slots)
    write_jsonl(OUT / "event_local_non_promotion_refs.jsonl", event_local_refs)
    write_json(OUT / "guardrail_scan.json", guardrail)
    write_json(OUT / "summary.json", summary)
    write_json(SUMMARY, summary)


if __name__ == "__main__":
    main()
