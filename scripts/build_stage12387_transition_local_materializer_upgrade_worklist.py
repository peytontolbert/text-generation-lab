#!/usr/bin/env python3
"""Build a fail-closed Stage12387 transition-local upgrade worklist.

This stage emits recovery work only. It does not admit or write training rows.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12387_transition_local_materializer_upgrade_worklist"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12386_AUDIT = (
    ROOT
    / "runs/local/artifacts/stage12386_transition_local_event_joiner_gap_audit/transition_local_gap_audit_records.jsonl"
)
STAGE12316_JOIN = (
    ROOT
    / "runs/local/artifacts/stage12316_transition_local_event_joiner/transition_local_event_join_records.jsonl"
)
STAGE12206_CONTROL = (
    ROOT
    / "runs/local/artifacts/stage12206_level3_passfail_training_rollup/level3_passfail_train_support_repo_capped.jsonl"
)
STAGE12206_SUMMARY = ROOT / "runs/summaries/stage12206_level3_passfail_training_rollup.json"

REQUIRED_TRANSITION_LOCAL_FIELDS = [
    "state_before_summary_codes",
    "candidate_action_set",
    "chosen_action",
    "observation_status_class",
    "patch_apply_status",
    "verifier_identity",
    "verifier_transition",
    "state_delta_codes",
    "stop_continue_label",
    "semantic_rule_id",
    "transition_function_key",
]

REQUIRED_LEVEL3_CONTROL_FIELDS = [
    "root_id",
    "repo_family",
    "language",
    "candidate_action_set",
    "observed_action",
    "command_result",
    "state_update",
    "stop_decision",
    "verifier_transition",
]

BLOCKER_CLASS_MAP = {
    "chosen_action_policy_label_not_admitted_from_observed_order": "policy_label_not_admitted",
    "state_delta_needs_semantic_review_before_training": "state_delta_semantic_review_required",
    "repo_family_still_not_semantically_recovered": "repo_identity_recovery_required",
    "repo_family_not_semantically_recovered": "repo_identity_recovery_required",
    "semantic_rule_id_not_deterministically_assignable": "semantic_transition_key_missing",
    "transition_function_key_not_deterministically_assignable": "semantic_transition_key_missing",
    "verifier_status_not_training_grade": "verifier_status_not_training_grade",
    "raw_source_session_unavailable_for_internal_semantic_extraction": "raw_session_unavailable",
    "task_window_missing": "raw_window_missing",
    "transition_local_state_ledger_missing": "transition_local_state_ledger_missing",
    "state_delta_proof_missing": "state_delta_semantic_review_required",
    "stop_continue_proof_missing": "stop_continue_proof_missing",
    "patch_applicability_or_no_patch_reason_missing": "patch_apply_status_missing",
    "verifier_status_class_missing": "verifier_status_missing",
    "ordered_patch_and_verifier_refs_missing": "patch_verifier_order_missing",
}


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def stable_id(prefix: str, *parts: Any) -> str:
    payload = json.dumps(parts, sort_keys=True, separators=(",", ":"), default=str)
    return f"{prefix}_{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:20]}"


def dig(row: dict[str, Any] | None, *path: str) -> Any:
    value: Any = row or {}
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def nonempty(value: Any) -> bool:
    return value not in (None, "", [], {})


def field_value(row: dict[str, Any] | None, field: str) -> Any:
    row = row or {}
    if field == "observation_status_class":
        return (
            dig(row, "observation", "verifier_status_class")
            or dig(row, "target_only", "verifier_status_class")
            or dig(row, "model_input_view", "verifier_status_class")
            or row.get("verifier_status")
            or row.get("verifier_status_class")
        )
    if field == "patch_apply_status":
        return dig(row, "observation", "patch_apply_status") or dig(row, "target_only", "patch_apply_status") or row.get(field)
    if field == "state_before_summary_codes":
        return row.get(field) or dig(row, "model_input_view", field)
    if field == "candidate_action_set":
        return row.get(field) or dig(row, "model_input_view", field)
    if field == "chosen_action":
        return row.get("chosen_action") or row.get("observed_action")
    if field == "state_delta_codes":
        return row.get(field) or dig(row, "target_only", field) or row.get("state_update")
    if field == "stop_continue_label":
        return row.get(field) or dig(row, "target_only", field) or row.get("stop_decision")
    if field == "semantic_rule_id":
        return row.get(field) or dig(row, "target_only", field)
    if field == "transition_function_key":
        return row.get(field) or dig(row, "target_only", field)
    if field == "verifier_identity":
        return (
            row.get(field)
            or dig(row, "observation", "verifier_identity")
            or dig(row, "observation", "verifier_observation_sequence")
            or dig(row, "command_result", "command_hash")
            or dig(row, "command_result", "command_ref")
        )
    if field == "verifier_transition":
        return row.get(field) or dig(row, "target_only", field)
    return row.get(field)


def build_stage12316_index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for row in rows:
        for key in ("transition_local_join_id", "source_join_record_id", "candidate_id", "task_window_id"):
            value = row.get(key)
            if value:
                index[str(value)] = row
    return index


def load_control_contract(rows: list[dict[str, Any]], summary: dict[str, Any]) -> dict[str, Any]:
    sample = rows[0] if rows else {}
    visibility = sample.get("stage12206_training_visibility") if isinstance(sample.get("stage12206_training_visibility"), dict) else {}
    schema_presence = {field: field in sample for field in REQUIRED_LEVEL3_CONTROL_FIELDS}
    return {
        "source_path": str(STAGE12206_CONTROL.relative_to(ROOT)),
        "summary_path": str(STAGE12206_SUMMARY.relative_to(ROOT)),
        "required_level3_control_fields": REQUIRED_LEVEL3_CONTROL_FIELDS,
        "sample_schema_presence": schema_presence,
        "allowed_prompt_fields": visibility.get("allowed_prompt_fields") or [],
        "hide_fields_from_model_prompt": visibility.get("hide_fields_from_model_prompt") or [],
        "control_rows_loaded": len(rows),
        "control_summary_decision": summary.get("decision"),
        "control_claim_boundary": summary.get("claim_boundary"),
    }


def exact_missing(audit: dict[str, Any], enriched: dict[str, Any] | None) -> tuple[list[str], list[str]]:
    missing_transition = list(audit.get("missing_transition_local_fields") or [])
    missing_level3 = list(audit.get("missing_level3_baseline_fields") or [])
    if enriched:
        missing_transition = [
            field
            for field in REQUIRED_TRANSITION_LOCAL_FIELDS
            if field in missing_transition and not nonempty(field_value(enriched, field))
        ]
        missing_level3 = [
            field
            for field in REQUIRED_LEVEL3_CONTROL_FIELDS
            if field in missing_level3 and not nonempty(field_value(enriched, field))
        ]
    return missing_transition, missing_level3


def classify_blockers(
    audit: dict[str, Any],
    enriched: dict[str, Any] | None,
    missing_transition: list[str],
    missing_level3: list[str],
) -> list[str]:
    classes = {BLOCKER_CLASS_MAP.get(reason, reason) for reason in audit.get("blocked_reasons") or []}
    if "semantic_rule_id" in missing_transition or "transition_function_key" in missing_transition:
        classes.add("semantic_transition_key_missing")
    if "patch_apply_status" in missing_transition:
        classes.add("patch_apply_status_missing")
    if "observation_status_class" in missing_transition:
        classes.add("verifier_status_missing")
    if "verifier_identity" in missing_transition or "verifier_transition" in missing_transition:
        classes.add("verifier_identity_or_transition_missing")
    if "chosen_action" in missing_transition or "observed_action" in missing_level3:
        classes.add("policy_label_not_admitted")
    if "state_delta_codes" in missing_transition or "state_update" in missing_level3:
        classes.add("state_delta_semantic_review_required")
    if {"root_id", "repo_family", "language"} & set(missing_level3):
        classes.add("repo_identity_recovery_required")
    if {"command_result", "state_update", "stop_decision"} & set(missing_level3):
        classes.add("level3_control_contract_missing")
    if audit.get("expected_role") == "verifier_observation_support":
        classes.add("observation_status_support_only")
    if enriched and dig(enriched, "chosen_action", "status") == "observed_action_sequence_only_not_policy_gold":
        classes.add("observed_action_only_not_policy_gold")
    return sorted(classes)


def required_operations(
    blocker_classes: list[str],
    missing_transition: list[str],
    missing_level3: list[str],
    enriched: dict[str, Any] | None,
) -> list[str]:
    operations: list[str] = []
    classes = set(blocker_classes)
    if "repo_identity_recovery_required" in classes:
        operations.append("recover_root_id_repo_family_language_from_stage12314_join_or_raw_session_metadata")
    if "level3_control_contract_missing" in classes:
        operations.append("rehydrate_command_result_state_update_stop_decision_to_stage12206_control_shape")
    if "policy_label_not_admitted" in classes or "observed_action_only_not_policy_gold" in classes:
        operations.append("manual_policy_label_review_before_any_chosen_action_or_observed_action_target")
    if "state_delta_semantic_review_required" in classes:
        operations.append("semantic_review_state_delta_codes_against_safe_command_and_verifier_observations")
    if "semantic_transition_key_missing" in classes:
        operations.append("rerun_deterministic_semantic_rule_and_transition_function_key_extraction")
    if "patch_apply_status_missing" in classes:
        operations.append("recover_patch_apply_status_or_explicit_no_patch_reason_from_raw_session")
    if "verifier_status_missing" in classes:
        operations.append("recover_verifier_status_class_from_safe_verifier_observation_sequence")
    if "verifier_identity_or_transition_missing" in classes:
        operations.append("derive_or_recover_verifier_identity_and_transition_without_emitting_raw_command_output")
    if "candidate_action_set" in missing_transition:
        operations.append("construct_neutral_candidate_action_set_matching_stage12206_prompt_visibility")
    if "verifier_transition" in missing_transition and enriched:
        operations.append("derive_nontraining_verifier_transition_candidate_from_patch_and_verifier_status_for_review")
    if "observation_status_support_only" in classes:
        operations.append("do_not_promote_observation_support_row_to_causal_transition_without_new_review")
    operations.append("keep_training_admission_false_and_emit_worklist_only")
    return sorted(dict.fromkeys(operations))


def safety_flags(
    blocker_classes: list[str],
    missing_transition: list[str],
    missing_level3: list[str],
    enriched: dict[str, Any] | None,
) -> dict[str, Any]:
    classes = set(blocker_classes)
    semantic_pair_present = nonempty(field_value(enriched, "semantic_rule_id")) and nonempty(field_value(enriched, "transition_function_key"))
    patch_present = nonempty(field_value(enriched, "patch_apply_status"))
    verifier_present = nonempty(field_value(enriched, "observation_status_class"))
    raw_available = bool(dig(enriched, "source_refs", "raw_source_reopened_internally") or dig(enriched, "internal_semantic_extraction", "raw_was_inspected"))
    deterministic_missing = set(missing_transition).issubset({"verifier_transition", "verifier_identity"})
    repo_or_policy_blocked = bool(classes & {"repo_identity_recovery_required", "policy_label_not_admitted", "observed_action_only_not_policy_gold"})
    semantic_review_only = bool(
        classes
        & {
            "semantic_transition_key_missing",
            "state_delta_semantic_review_required",
            "policy_label_not_admitted",
            "observed_action_only_not_policy_gold",
            "observation_status_support_only",
        }
    )
    return {
        "auto_derivation_safe": bool(semantic_pair_present and patch_present and verifier_present and deterministic_missing and not repo_or_policy_blocked),
        "auto_derivation_scope": (
            "nontraining_verifier_identity_or_transition_only"
            if semantic_pair_present and patch_present and verifier_present and deterministic_missing
            else "not_safe"
        ),
        "raw_session_rehydration_safe": bool(raw_available and not ("raw_session_unavailable" in classes)),
        "raw_session_rehydration_scope": "safe_for_nontraining_metadata_recovery_only" if raw_available else "not_available_from_requested_inputs",
        "semantic_review_only": semantic_review_only,
        "training_admission_allowed": False,
        "new_training_row_admitted": False,
    }


def score_row(
    audit: dict[str, Any],
    enriched: dict[str, Any] | None,
    blocker_classes: list[str],
    missing_transition: list[str],
    missing_level3: list[str],
    safety: dict[str, Any],
) -> int:
    score = 0
    semantic_pair_present = nonempty(field_value(enriched, "semantic_rule_id")) and nonempty(field_value(enriched, "transition_function_key"))
    if semantic_pair_present:
        score += 45
    if nonempty(field_value(enriched, "patch_apply_status")):
        score += 20
    if nonempty(field_value(enriched, "observation_status_class")):
        score += 20
    if nonempty(field_value(enriched, "state_delta_codes")):
        score += 10
    if nonempty(field_value(enriched, "stop_continue_label")):
        score += 8
    if nonempty(field_value(enriched, "state_before_summary_codes")):
        score += 8
    if audit.get("source_name") == "stage12316_transition_local_join":
        score += 15
    if safety["raw_session_rehydration_safe"]:
        score += 8
    score -= len(set(blocker_classes)) * 7
    score -= len(missing_transition) * 5
    score -= len(missing_level3) * 2
    if "observed_action_only_not_policy_gold" in blocker_classes or "policy_label_not_admitted" in blocker_classes:
        score -= 18
    if "repo_identity_recovery_required" in blocker_classes:
        score -= 22
    if "observation_status_support_only" in blocker_classes:
        score -= 25
    if "semantic_transition_key_missing" in blocker_classes:
        score -= 30
    if "verifier_status_not_training_grade" in blocker_classes:
        score -= 15
    return score


def build_worklist_row(
    audit: dict[str, Any],
    stage12316_index: dict[str, dict[str, Any]],
    control_contract: dict[str, Any],
) -> dict[str, Any]:
    source_row_id = str(audit.get("source_row_id") or "")
    enriched = stage12316_index.get(source_row_id)
    missing_transition, missing_level3 = exact_missing(audit, enriched)
    blocker_classes = classify_blockers(audit, enriched, missing_transition, missing_level3)
    operations = required_operations(blocker_classes, missing_transition, missing_level3, enriched)
    safety = safety_flags(blocker_classes, missing_transition, missing_level3, enriched)
    score = score_row(audit, enriched, blocker_classes, missing_transition, missing_level3, safety)
    present_signals = {
        "semantic_rule_id_present": nonempty(field_value(enriched, "semantic_rule_id")) or "semantic_rule_id" not in missing_transition,
        "transition_function_key_present": nonempty(field_value(enriched, "transition_function_key")) or "transition_function_key" not in missing_transition,
        "patch_apply_status_present": nonempty(field_value(enriched, "patch_apply_status")) or "patch_apply_status" not in missing_transition,
        "verifier_status_present": nonempty(field_value(enriched, "observation_status_class")) or "observation_status_class" not in missing_transition,
        "state_delta_codes_present": nonempty(field_value(enriched, "state_delta_codes")) or "state_delta_codes" not in missing_transition,
        "stop_continue_label_present": nonempty(field_value(enriched, "stop_continue_label")) or "stop_continue_label" not in missing_transition,
        "stage12316_enriched": bool(enriched),
    }
    return {
        "stage": STAGE,
        "worklist_id": stable_id("stage12387_workitem", audit.get("source_name"), source_row_id, missing_transition, missing_level3),
        "source_name": audit.get("source_name"),
        "source_path": audit.get("source_path"),
        "source_row_id": source_row_id,
        "expected_role": audit.get("expected_role"),
        "classification": audit.get("classification"),
        "language_family": audit.get("language_family"),
        "priority_score": score,
        "missing_transition_local_fields": missing_transition,
        "missing_level3_control_fields": missing_level3,
        "original_blocked_reasons": audit.get("blocked_reasons") or [],
        "blocker_classes": blocker_classes,
        "required_recovery_operations": operations,
        "recovery_safety": safety,
        "present_signals": present_signals,
        "stage12206_control_contract_ref": {
            "required_level3_control_fields": control_contract["required_level3_control_fields"],
            "must_hide_fields_from_model_prompt": control_contract["hide_fields_from_model_prompt"],
        },
        "stage12316_refs": {
            "transition_local_join_id": (enriched or {}).get("transition_local_join_id"),
            "source_join_record_id": (enriched or {}).get("source_join_record_id"),
            "candidate_id": (enriched or {}).get("candidate_id"),
            "task_window_id": (enriched or {}).get("task_window_id"),
            "raw_source_reopened_internally": bool(dig(enriched, "source_refs", "raw_source_reopened_internally")),
            "raw_text_emitted": bool(dig(enriched, "source_refs", "raw_text_emitted")),
            "raw_command_text_emitted": bool(dig(enriched, "source_refs", "raw_command_text_emitted")),
            "raw_tool_output_emitted": bool(dig(enriched, "source_refs", "raw_tool_output_emitted")),
            "raw_patch_body_emitted": bool(dig(enriched, "source_refs", "raw_patch_body_emitted")),
        },
        "admission": {
            "training_allowed": False,
            "level3_admitted": False,
            "patch_trace_admitted": False,
            "strict_eval_eligible": False,
            "reason": "Stage12387 is a fail-closed worklist only; recovery outputs must be reviewed by a later stage.",
        },
    }


def write_markdown(worklist: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    lines = [
        "# Stage12387 Transition-Local Materializer Upgrade Worklist",
        "",
        "Fail-closed worklist only. No training rows are admitted by this stage.",
        "",
        f"Worklist rows: {len(worklist)}",
        f"Decision: `{summary['decision']}`",
        f"Top priority rows shown: {min(25, len(worklist))}",
        "",
        "| rank | score | source | row | missing transition fields | blocker classes | recovery safety |",
        "| ---: | ---: | --- | --- | --- | --- | --- |",
    ]
    for row in worklist[:25]:
        safety_bits = []
        if row["recovery_safety"]["auto_derivation_safe"]:
            safety_bits.append("auto-derivation")
        if row["recovery_safety"]["raw_session_rehydration_safe"]:
            safety_bits.append("raw-session")
        if row["recovery_safety"]["semantic_review_only"]:
            safety_bits.append("semantic-review-only")
        safety = ", ".join(safety_bits) if safety_bits else "not-safe"
        lines.append(
            "| {rank} | {score} | `{source}` | `{row_id}` | `{missing}` | `{blockers}` | {safety} |".format(
                rank=row["worklist_rank"],
                score=row["priority_score"],
                source=row["source_name"],
                row_id=row["source_row_id"],
                missing=", ".join(row["missing_transition_local_fields"]) or "none",
                blockers=", ".join(row["blocker_classes"]) or "none",
                safety=safety,
            )
        )
    lines.extend(
        [
            "",
            "## Required Control Contract",
            "",
            "Rows must be recovered to the Stage12206 Level-3 control shape before any future admission decision. "
            "This stage records missing fields and recovery operations only.",
        ]
    )
    (OUT / "TRANSITION_LOCAL_MATERIALIZER_UPGRADE_WORKLIST_STAGE12387.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    audit_rows = read_jsonl(STAGE12386_AUDIT)
    stage12316_rows = read_jsonl(STAGE12316_JOIN)
    control_rows = read_jsonl(STAGE12206_CONTROL)
    control_summary = read_json(STAGE12206_SUMMARY)
    stage12316_index = build_stage12316_index(stage12316_rows)
    control_contract = load_control_contract(control_rows, control_summary)

    worklist = [
        build_worklist_row(audit, stage12316_index, control_contract)
        for audit in audit_rows
        if audit.get("classification") == "transition_local_incomplete"
    ]
    worklist.sort(
        key=lambda row: (
            -int(row["priority_score"]),
            len(row["missing_transition_local_fields"]) + len(row["missing_level3_control_fields"]),
            str(row["source_name"]),
            str(row["source_row_id"]),
        )
    )
    for rank, row in enumerate(worklist, 1):
        row["worklist_rank"] = rank

    blocker_counts: Counter[str] = Counter()
    operation_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    safety_counts: Counter[str] = Counter()
    missing_transition_counts: Counter[str] = Counter()
    missing_level3_counts: Counter[str] = Counter()
    for row in worklist:
        source_counts[str(row["source_name"])] += 1
        blocker_counts.update(row["blocker_classes"])
        operation_counts.update(row["required_recovery_operations"])
        missing_transition_counts.update(row["missing_transition_local_fields"])
        missing_level3_counts.update(row["missing_level3_control_fields"])
        if row["recovery_safety"]["auto_derivation_safe"]:
            safety_counts["auto_derivation_safe"] += 1
        if row["recovery_safety"]["raw_session_rehydration_safe"]:
            safety_counts["raw_session_rehydration_safe"] += 1
        if row["recovery_safety"]["semantic_review_only"]:
            safety_counts["semantic_review_only"] += 1

    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUT / "transition_local_materializer_upgrade_worklist.jsonl", worklist)
    write_json(OUT / "blocker_class_counts.json", dict(blocker_counts))
    write_json(OUT / "required_recovery_operation_counts.json", dict(operation_counts))

    summary = {
        "stage": STAGE,
        "decision": "fail_closed_transition_local_upgrade_worklist_ready",
        "claim_boundary": "Worklist only. No training package, no Level-3 admission, no patch-trace admission, and no strict eval claim.",
        "training_allowed": False,
        "new_training_rows_emitted": 0,
        "level3_admitted": 0,
        "patch_trace_admitted": 0,
        "strict_eval_eligible_rows": 0,
        "inputs": {
            "stage12386_audit_records": str(STAGE12386_AUDIT.relative_to(ROOT)),
            "stage12316_transition_local_event_join_records": str(STAGE12316_JOIN.relative_to(ROOT)),
            "stage12206_control_schema_source": str(STAGE12206_CONTROL.relative_to(ROOT)),
        },
        "input_counts": {
            "stage12386_audit_records": len(audit_rows),
            "stage12316_transition_local_event_join_records": len(stage12316_rows),
            "stage12206_control_rows_loaded": len(control_rows),
        },
        "worklist_count": len(worklist),
        "worklist_source_counts": dict(source_counts),
        "recovery_safety_counts": dict(safety_counts),
        "blocker_class_counts": dict(blocker_counts),
        "required_recovery_operation_counts": dict(operation_counts),
        "missing_transition_local_field_counts": dict(missing_transition_counts),
        "missing_level3_control_field_counts": dict(missing_level3_counts),
        "priority_policy": {
            "prefer": [
                "semantic_rule_id and transition_function_key present",
                "patch_apply_status present",
                "verifier status present",
                "fewer blocker classes and missing control fields",
            ],
            "deprioritize": [
                "observed-action-only rows without policy label review",
                "repo-unrecovered rows until recovery path is known",
                "observation-status support rows that are not causal transition records",
            ],
        },
        "stage12206_control_contract": control_contract,
        "artifact_paths": {
            "worklist_jsonl": str((OUT / "transition_local_materializer_upgrade_worklist.jsonl").relative_to(ROOT)),
            "markdown": str((OUT / "TRANSITION_LOCAL_MATERIALIZER_UPGRADE_WORKLIST_STAGE12387.md").relative_to(ROOT)),
            "blocker_class_counts": str((OUT / "blocker_class_counts.json").relative_to(ROOT)),
            "required_recovery_operation_counts": str((OUT / "required_recovery_operation_counts.json").relative_to(ROOT)),
        },
    }
    write_json(OUT / "summary.json", summary)
    write_markdown(worklist, summary)
    write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if worklist else 2


if __name__ == "__main__":
    raise SystemExit(main())
