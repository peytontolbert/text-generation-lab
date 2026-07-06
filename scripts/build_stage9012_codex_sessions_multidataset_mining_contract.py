#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9012
NAME = "stage9012_codex_sessions_multidataset_mining_contract"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CODEX_SESSIONS_MULTIDATASET_MINING_CONTRACT_STAGE9012.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT = OUT_DIR / "codex_sessions_multidataset_mining_contract.json"

SESSION_SOURCE_ROOTS = [
    "~/codex/sessions",
    "~/.codex/sessions",
    "/arxiv/code/sessions",
]

NORMALIZED_EVENT_TYPES = [
    "session_meta",
    "user_message",
    "assistant_message",
    "assistant_final",
    "commentary_update",
    "tool_call_exec_command",
    "tool_call_apply_patch",
    "tool_call_other",
    "tool_output",
    "file_read_observed",
    "patch_applied",
    "verification_command",
    "verification_result",
    "user_regression_report",
    "repair_attempt",
    "final_verified_summary",
]

DATASET_FAMILIES = [
    {
        "family": "next_action_policy",
        "target": "SEARCH | READ_FILE | EDIT_FILE | RUN_TEST | VERIFY | REPAIR | ROLLBACK | ABSTAIN | ASK | SUMMARIZE",
        "primary_filters": ["software_task_present", "state_has_recent_context", "next_tool_or_final_action_observed"],
    },
    {
        "family": "edit_localization",
        "target": "file_path | symbol | region | retrieve_more",
        "primary_filters": ["file_reads_observed", "later_edit_or_verified_focus_exists", "exclude_browsing_only_spans"],
    },
    {
        "family": "patch_operator",
        "target": "ADD_IMPORT | MODIFY_FUNCTION | INSERT_GUARD | UPDATE_CONFIG | ADD_TEST | ROLLBACK | DOC_UPDATE",
        "primary_filters": ["apply_patch_observed", "localized_context_available", "operator_inferable_from_diff"],
    },
    {
        "family": "verifier_selection",
        "target": "targeted_test | full_test | build | typecheck | lint | smoke | no_verifier_yet",
        "primary_filters": ["tool_command_observed", "change_state_known", "verification_command_classifiable"],
    },
    {
        "family": "verifier_repair",
        "target": "repair_localization | repair_operator | rollback | retrieve_more | abstain",
        "primary_filters": ["verification_failed_or_user_regression", "subsequent_repair_observed", "repair_outcome_labelable"],
    },
    {
        "family": "outcome_reward",
        "target": "helpful | harmful | neutral | regression | dead_end | verified_success",
        "primary_filters": ["action_outcome_available", "verification_or_user_feedback_available", "exclude_unresolved_ambiguous"],
    },
    {
        "family": "abstain_retrieve_more",
        "target": "RETRIEVE_MORE | ASK_FOR_INFO | DO_NOT_EDIT | RUN_VERIFIER_FIRST",
        "primary_filters": ["insufficient_context_or_high_risk_state", "no_safe_edit_evidence", "decision_boundary_clear"],
    },
    {
        "family": "small_validated_patch_generation",
        "target": "bounded_patch_hunk",
        "primary_filters": ["short_coherent_patch", "verification_passed", "no_later_regression_in_slice", "source_context_compact"],
    },
    {
        "family": "trace_summarization",
        "target": "compact_state_summary",
        "primary_filters": ["tool_heavy_trace", "state_transition_preserved", "summary_is_grounded_in_events"],
    },
]

GLOBAL_ACCEPTANCE_FILTERS = [
    "concrete_software_task_present",
    "repo_or_file_context_present",
    "tool_action_sequence_parseable",
    "edits_linked_to_file_paths_when_used",
    "verification_or_feedback_available_for_outcome_labels",
    "session_boundary_preserved",
    "no_secret_or_credential_content",
    "no_locked_eval_contamination",
]

GLOBAL_REJECTION_FILTERS = [
    "planning_only_without_tools",
    "browsing_only_without_outcome",
    "three_or_more_failed_edits_without_resolution",
    "user_reports_made_worse_without_later_repair",
    "unattributed_assistant_claim_of_success",
    "missing_tool_output_for_claimed_verification",
    "large_unbounded_patch_target",
    "private_secret_or_credential_exposure",
]

SPLIT_POLICY = [
    "split_by_session_id_not_row",
    "split_by_repository_when_repository_id_available",
    "hold_out_user_regression_sessions_for_strict_eval",
    "keep_near_duplicate_session_slices_in_same_split",
    "never_train_on_hidden_or_locked_eval_slices",
]

FORBIDDEN_OPERATIONS = [
    "READ_SESSIONS_NOW",
    "MINE_SESSIONS_NOW",
    "COPY_SESSION_CONTENT_NOW",
    "WRITE_TO_ARXIV",
    "EMIT_TRAINING_ROWS",
    "TRAIN_MODEL",
    "RUN_MODEL",
    "RUN_RUNTIME",
    "AUTHORIZE_DECODER_CE",
    "AUTHORIZE_DENOISE_CE",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_contract(registry: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "session_source_roots_recorded": len(SESSION_SOURCE_ROOTS) >= 3,
        "normalized_event_types_recorded": len(NORMALIZED_EVENT_TYPES) >= 15,
        "dataset_families_recorded": len(DATASET_FAMILIES) >= 9,
        "global_acceptance_filters_recorded": len(GLOBAL_ACCEPTANCE_FILTERS) >= 8,
        "global_rejection_filters_recorded": len(GLOBAL_REJECTION_FILTERS) >= 8,
        "split_policy_recorded": len(SPLIT_POLICY) >= 5,
        "forbidden_operations_recorded": len(FORBIDDEN_OPERATIONS) >= 10,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "CODEX_SESSIONS_MULTIDATASET_MINING_CONTRACT_NO_MINING",
        "session_source_roots": SESSION_SOURCE_ROOTS,
        "normalized_event_types": NORMALIZED_EVENT_TYPES,
        "dataset_families": DATASET_FAMILIES,
        "global_acceptance_filters": GLOBAL_ACCEPTANCE_FILTERS,
        "global_rejection_filters": GLOBAL_REJECTION_FILTERS,
        "split_policy": SPLIT_POLICY,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "checks": checks,
        "metrics": {
            "session_source_roots": len(SESSION_SOURCE_ROOTS),
            "normalized_event_types": len(NORMALIZED_EVENT_TYPES),
            "dataset_families": len(DATASET_FAMILIES),
            "global_acceptance_filters": len(GLOBAL_ACCEPTANCE_FILTERS),
            "global_rejection_filters": len(GLOBAL_REJECTION_FILTERS),
            "split_policy_rules": len(SPLIT_POLICY),
            "session_read_authorized_now": False,
            "session_mining_authorized_now": False,
            "session_content_copied_now": False,
            "training_rows_emitted_now": False,
            "arxiv_write_authorized": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "model_execution_attempted": False,
            "runtime_authorized_flag": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Wider Codex sessions are recorded as a future multi-dataset mine. This stage defines event normalization, dataset families, filters, and split policy, but reads no sessions and emits no rows.",
    }


def validate_contract(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    families = {item.get("family") for item in card.get("dataset_families", [])}
    for required in ["next_action_policy", "edit_localization", "patch_operator", "verifier_selection", "verifier_repair", "outcome_reward", "small_validated_patch_generation"]:
        if required not in families:
            failures.append(f"missing_family:{required}")
    for key in [
        "session_read_authorized_now",
        "session_mining_authorized_now",
        "session_content_copied_now",
        "training_rows_emitted_now",
        "arxiv_write_authorized",
        "training_authorized",
        "data_mining_authorized",
        "model_execution_attempted",
        "runtime_authorized_flag",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_contract(registry)
    failures = validate_contract(card)
    CONTRACT.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": 0, "failures": failures, **card["metrics"]},
        "artifacts": {"contract": str(CONTRACT.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "Design a no-content session inventory preflight that counts candidate session files without copying or parsing message bodies. Keep mining and training closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9012 Codex Sessions Multidataset Mining Contract",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage captures the wider Codex sessions as a future multi-dataset mine. It defines event normalization, dataset families, quality filters, and split policy without reading sessions, copying content, mining rows, writing `/arxiv`, or training.",
        "",
        f"Dataset families: `{summary['metrics']['dataset_families']}`",
        f"Normalized event types: `{summary['metrics']['normalized_event_types']}`",
        f"Session mining authorized now: `{summary['metrics']['session_mining_authorized_now']}`",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))),
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
