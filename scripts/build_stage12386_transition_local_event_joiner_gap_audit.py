#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12386_transition_local_event_joiner_gap_audit"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"


SOURCE_POOLS = [
    {
        "source_name": "stage12206_level3_repo_capped_control",
        "path": ROOT
        / "runs/local/artifacts/stage12206_level3_passfail_training_rollup/level3_passfail_train_support_repo_capped.jsonl",
        "expected_role": "level3_control",
    },
    {
        "source_name": "stage12314_repo_state_join_seed",
        "path": ROOT
        / "runs/local/artifacts/stage12314_session_candidate_repo_and_state_joiner/session_candidate_repo_state_join_records.jsonl",
        "expected_role": "join_seed",
    },
    {
        "source_name": "stage12316_transition_local_join",
        "path": ROOT
        / "runs/local/artifacts/stage12316_transition_local_event_joiner/transition_local_event_join_records.jsonl",
        "expected_role": "transition_local_audit",
    },
    {
        "source_name": "stage12320_event_local_observation_support",
        "path": ROOT
        / "runs/local/artifacts/stage12320_event_local_semantic_review_admission/event_local_observation_train_support_admitted_rows.jsonl",
        "expected_role": "verifier_observation_support",
    },
    {
        "source_name": "stage12323_v4_event_local_observation_support",
        "path": ROOT
        / "runs/local/artifacts/stage12323_v4_event_local_review_admission/v4_event_local_train_support_admitted_rows.jsonl",
        "expected_role": "verifier_observation_support",
    },
    {
        "source_name": "stage12295_transition_function_support",
        "path": ROOT
        / "runs/local/artifacts/stage12295_transition_function_ledger/transition_function_train_support_rows.jsonl",
        "expected_role": "action_observation_taxonomy",
    },
    {
        "source_name": "stage12385_selected_test_support",
        "path": ROOT
        / "runs/local/artifacts/stage12385_combined_train_support_ledger_v15_dedup/combined_selected_test_rows_v15_dedup.jsonl",
        "expected_role": "selected_test_support",
    },
]

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

REQUIRED_LEVEL3_BASELINE_FIELDS = [
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


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def nonempty(value: Any) -> bool:
    if value is None:
        return False
    if value == "":
        return False
    if value == []:
        return False
    if value == {}:
        return False
    return True


def dig(row: dict[str, Any], *path: str) -> Any:
    value: Any = row
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def field_value(row: dict[str, Any], field: str) -> Any:
    if field == "observation_status_class":
        return (
            dig(row, "observation", "verifier_status_class")
            or dig(row, "target_only", "verifier_status_class")
            or dig(row, "model_input_view", "verifier_status_class")
            or row.get("verifier_status")
            or row.get("verifier_status_class")
        )
    if field == "patch_apply_status":
        return (
            dig(row, "observation", "patch_apply_status")
            or dig(row, "target_only", "patch_apply_status")
            or dig(row, "model_input_view", "patch_apply_status")
            or row.get("patch_apply_status")
        )
    if field == "state_before_summary_codes":
        return (
            row.get("state_before_summary_codes")
            or dig(row, "model_input_view", "state_before_summary_codes")
            or row.get("state_before")
        )
    if field == "candidate_action_set":
        return row.get("candidate_action_set") or dig(row, "model_input_view", "candidate_action_set")
    if field == "chosen_action":
        return row.get("chosen_action") or row.get("observed_action")
    if field == "state_delta_codes":
        return row.get("state_delta_codes") or dig(row, "target_only", "state_delta_codes") or row.get("state_update")
    if field == "stop_continue_label":
        return row.get("stop_continue_label") or row.get("stop_decision") or row.get("stop_continue")
    if field == "semantic_rule_id":
        return row.get("semantic_rule_id") or dig(row, "target_only", "semantic_rule_id")
    if field == "transition_function_key":
        return row.get("transition_function_key") or dig(row, "target_only", "transition_function_key")
    if field == "verifier_identity":
        return (
            row.get("verifier_identity")
            or dig(row, "observation", "verifier_identity")
            or dig(row, "observation", "verifier_observation_sequence")
            or dig(row, "command_result", "command_hash")
            or dig(row, "command_result", "command_ref")
        )
    if field == "verifier_transition":
        return row.get("verifier_transition") or dig(row, "target_only", "verifier_transition")
    return row.get(field)


def missing_fields(row: dict[str, Any], fields: list[str]) -> list[str]:
    return [field for field in fields if not nonempty(field_value(row, field))]


def has_real_patch_trace(row: dict[str, Any]) -> bool:
    if nonempty(row.get("patch_diff")) or nonempty(row.get("patch_trace")):
        return True
    source_extra = row.get("source_extra") if isinstance(row.get("source_extra"), dict) else {}
    return nonempty(source_extra.get("patch_diff")) or nonempty(source_extra.get("patch_trace"))


def row_id(row: dict[str, Any]) -> str:
    for key in (
        "row_id",
        "rollup_record_id",
        "transition_local_join_id",
        "join_record_id",
        "transition_function_row_id",
        "source_row_id",
        "candidate_id",
        "root_id",
    ):
        value = row.get(key)
        if value:
            return str(value)
    return "unknown_row"


def classify_record(row: dict[str, Any], source_name: str) -> tuple[str, list[str], list[str]]:
    missing_transition = missing_fields(row, REQUIRED_TRANSITION_LOCAL_FIELDS)
    missing_level3 = missing_fields(row, REQUIRED_LEVEL3_BASELINE_FIELDS)
    blockers = list(row.get("blocked_reasons") or [])
    admission = row.get("admission") if isinstance(row.get("admission"), dict) else {}

    level3_complete = not missing_level3 and (
        "level_3" in str(row.get("admission_level", ""))
        or source_name.startswith("stage12206")
    )
    transition_complete = not missing_transition and not any(
        reason in blockers
        for reason in (
            "chosen_action_policy_label_not_admitted_from_observed_order",
            "state_delta_needs_semantic_review_before_training",
            "repo_family_still_not_semantically_recovered",
        )
    )

    if level3_complete and has_real_patch_trace(row):
        return "patch_trace_complete", missing_transition, missing_level3
    if level3_complete:
        return "level3_control_complete", missing_transition, missing_level3
    if transition_complete:
        return "transition_local_complete", missing_transition, missing_level3
    if nonempty(field_value(row, "semantic_rule_id")) or nonempty(field_value(row, "transition_function_key")):
        return "transition_local_incomplete", missing_transition, missing_level3
    if (
        nonempty(field_value(row, "observation_status_class"))
        or nonempty(field_value(row, "patch_apply_status"))
        or admission.get("training_scope") == "target_hidden_observation_status_only"
    ):
        return "verifier_observation_support", missing_transition, missing_level3
    return "candidate_only", missing_transition, missing_level3


def audit_source(source: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    path = source["path"]
    rows = read_jsonl(path)
    record_audits: list[dict[str, Any]] = []
    classification_counts: Counter[str] = Counter()
    missing_transition_counts: Counter[str] = Counter()
    missing_level3_counts: Counter[str] = Counter()
    blocker_counts: Counter[str] = Counter()
    languages: Counter[str] = Counter()

    for row in rows:
        classification, missing_transition, missing_level3 = classify_record(row, source["source_name"])
        classification_counts[classification] += 1
        missing_transition_counts.update(missing_transition)
        missing_level3_counts.update(missing_level3)
        blocker_counts.update(row.get("blocked_reasons") or [])
        language = row.get("language_family") or row.get("language") or "unknown"
        languages[str(language)] += 1
        record_audits.append(
            {
                "stage": STAGE,
                "source_name": source["source_name"],
                "expected_role": source["expected_role"],
                "source_path": str(path.relative_to(ROOT)),
                "source_row_id": row_id(row),
                "classification": classification,
                "missing_transition_local_fields": missing_transition,
                "missing_level3_baseline_fields": missing_level3,
                "blocked_reasons": row.get("blocked_reasons") or [],
                "language_family": language,
                "training_admission_allowed_here": False,
            }
        )

    source_summary = {
        "source_name": source["source_name"],
        "expected_role": source["expected_role"],
        "path": str(path.relative_to(ROOT)),
        "source_status": "present" if path.exists() else "missing",
        "rows": len(rows),
        "classification_counts": dict(classification_counts),
        "missing_transition_local_field_counts": dict(missing_transition_counts),
        "missing_level3_baseline_field_counts": dict(missing_level3_counts),
        "blocked_reason_counts": dict(blocker_counts),
        "language_counts": dict(languages),
        "recommendation": recommendation(source["source_name"], classification_counts),
    }
    return source_summary, record_audits


def recommendation(source_name: str, counts: Counter[str]) -> str:
    if counts["patch_trace_complete"]:
        return "review_patch_trace_rows_before_any_training_claim"
    if counts["level3_control_complete"] and source_name.startswith("stage12206"):
        return "use_as_level3_control_exemplar_not_new_claim"
    if counts["transition_local_complete"]:
        return "manual_review_required_before_admission"
    if counts["transition_local_incomplete"]:
        return "use_as_materialization_seed_not_training_rows"
    if counts["verifier_observation_support"]:
        return "use_as_auxiliary_observation_support_only"
    return "candidate_or_join_audit_only"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    all_records: list[dict[str, Any]] = []
    source_summaries: list[dict[str, Any]] = []
    total_classes: Counter[str] = Counter()
    aggregate_missing_transition: Counter[str] = Counter()
    aggregate_missing_level3: Counter[str] = Counter()
    aggregate_languages: Counter[str] = Counter()
    records_by_class: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)

    for source in SOURCE_POOLS:
        summary, audits = audit_source(source)
        source_summaries.append(summary)
        all_records.extend(audits)
        total_classes.update(summary["classification_counts"])
        aggregate_missing_transition.update(summary["missing_transition_local_field_counts"])
        aggregate_missing_level3.update(summary["missing_level3_baseline_field_counts"])
        aggregate_languages.update(summary["language_counts"])
        for audit in audits:
            records_by_class[audit["classification"]].append(audit)

    write_jsonl(OUT / "transition_local_gap_audit_records.jsonl", all_records)
    # Compatibility name used by an earlier parallel worker draft. Keep it in sync
    # so the artifact directory cannot contain contradictory Stage12386 counts.
    write_jsonl(OUT / "transition_local_event_joiner_gap_audit_records.jsonl", all_records)
    for classification, rows in records_by_class.items():
        write_jsonl(OUT / f"{classification}.jsonl", rows)

    true_new_transition_rows = total_classes["transition_local_complete"] + total_classes["patch_trace_complete"]
    summary = {
        "stage": STAGE,
        "decision": "transition_local_gap_audit_complete_training_still_blocked",
        "claim_boundary": "This stage audits existing pools only. It emits no training package and admits no new Level-3 or patch-trace rows.",
        "training_allowed": False,
        "new_training_rows_emitted": 0,
        "sources_audited": len(SOURCE_POOLS),
        "records_audited": len(all_records),
        "classification_counts": dict(total_classes),
        "true_new_transition_rows_available_without_manual_review": true_new_transition_rows,
        "missing_transition_local_field_counts": dict(aggregate_missing_transition),
        "missing_level3_baseline_field_counts": dict(aggregate_missing_level3),
        "language_counts": dict(aggregate_languages),
        "source_summaries": source_summaries,
        "next_stage": {
            "stage": "stage12387_transition_local_materializer_upgrade",
            "purpose": "Upgrade the stage12316/stage12260 raw-index path against the Stage12206 control contract: recover repo_family, safe command_result, state_update, stop_decision, and policy-valid candidate labels.",
            "training_allowed": False,
            "must_not_train_on": [
                "candidate_only",
                "transition_local_incomplete",
                "verifier_observation_support_as_level3",
            ],
        },
    }

    (OUT / "transition_local_gap_audit_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (OUT / "transition_local_event_joiner_gap_audit_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (OUT / "TRANSITION_LOCAL_EVENT_JOINER_GAP_AUDIT_STAGE12386.md").write_text(
        "# Stage12386 Transition-Local Event Joiner Gap Audit\n\n"
        "This is a fail-closed audit stage. It separates Level-3 control rows, verifier-observation support rows, "
        "transition-local incomplete rows, and candidate-only rows.\n\n"
        f"Records audited: {len(all_records)}\n\n"
        f"Classification counts: `{json.dumps(dict(total_classes), sort_keys=True)}`\n\n"
        "No training package was emitted. Existing candidate/support rows must not be promoted to causal maintainer "
        "episodes until command result, state update, stop decision, repo family, verifier identity, and policy-valid "
        "candidate labels are present.\n",
        encoding="utf-8",
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
