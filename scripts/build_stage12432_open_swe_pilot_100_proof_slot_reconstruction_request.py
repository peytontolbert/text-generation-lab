#!/usr/bin/env python3
"""Stage12432 Open-SWE pilot-100 proof-slot reconstruction request.

This is a public-safe request/control artifact. It reads only the Stage12431
public summary, does not inspect raw Open-SWE row values, and does not run
checkout, patch application, replay, verifier, or training work.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12432_open_swe_pilot_100_proof_slot_reconstruction_request"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
STAGE12431_SUMMARY = ROOT / "runs/summaries/stage12431_open_swe_private_pilot_100_postrun_summary.json"

EXPECTED_STAGE12431 = "stage12431_open_swe_private_pilot_100_postrun_summary"
EXPECTED_METADATA_CANDIDATE_SUPPLY_ROWS = 207489
EXPECTED_PRIVATE_SAMPLED_ROWS = 100
EXPECTED_PRIVATE_DEDUPE_SURVIVORS = 100
EXPECTED_PROOF_COMPLETE_CANDIDATES = 0

RECONSTRUCTION_TASKS = [
    "checkout_before_anchor",
    "patch_application_proof",
    "same_verifier_before_after",
    "causal_transition",
    "state_after",
    "stop_continue",
]

ZERO_COUNTERS: dict[str, bool | int] = {
    "training_allowed": False,
    "admission_allowed": False,
    "execution_allowed_by_public_artifact": False,
    "reconstruction_executed_by_public_artifact": False,
    "admitted_rows": 0,
    "emitted_rows": 0,
    "emitted_training_rows": 0,
    "countable_rows": 0,
    "countable_new_rows": 0,
    "countable_as_new_train_support_rows": 0,
    "countable_as_new_proof_floor_rows": 0,
    "raw_rows_inspected": 0,
    "raw_rows_copied": 0,
    "raw_content_emitted": False,
    "replay_attempted_count": 0,
    "patch_apply_attempted_count": 0,
    "tests_run_count": 0,
}

RAW_CONTENT_POLICY: dict[str, bool] = {
    "raw_trajectories_emitted": False,
    "raw_commands_emitted": False,
    "raw_outputs_emitted": False,
    "raw_diffs_emitted": False,
    "raw_patches_emitted": False,
    "raw_issue_bodies_emitted": False,
    "raw_paths_emitted": False,
    "raw_urls_emitted": False,
    "source_text_emitted": False,
    "row_values_emitted": False,
    "locator_values_emitted": False,
    "schema_field_names_emitted": False,
    "private_slot_values_emitted": False,
    "training_rows_emitted": False,
}

FORBIDDEN_TEXT_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:Traceback \(most recent call last\)|stdout|stderr|pytest |npm |pip |git clone|git apply|curl )\b",
    re.IGNORECASE | re.MULTILINE,
)


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:n]


def file_hash(path: Path, n: int = 24) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:n]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def safe_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def source_stage12431_summary(summary: dict[str, Any]) -> dict[str, Any]:
    accounting = summary.get("accounting_table", {})
    if not isinstance(accounting, dict):
        accounting = {}
    return {
        "source_stage": summary.get("stage"),
        "source_record_type": summary.get("record_type"),
        "source_decision_hash": stable_hash(summary.get("decision"), 16),
        "source_guardrail_scan_passed": summary.get("guardrail_scan_passed", False),
        "source_training_allowed": summary.get("training_allowed", False),
        "source_admission_allowed": summary.get("admission_allowed", False),
        "source_admitted_rows": safe_int(summary.get("admitted_rows")),
        "source_emitted_rows": safe_int(summary.get("emitted_rows")),
        "source_countable_new_rows": safe_int(summary.get("countable_new_rows")),
        "source_raw_leak_count": safe_int(summary.get("raw_leak_count")),
        "source_overclaim_count": safe_int(summary.get("overclaim_count")),
        "source_metadata_candidate_supply_rows": safe_int(summary.get("metadata_candidate_supply_rows")),
        "source_private_sampled_rows": safe_int(summary.get("private_sampled_rows")),
        "source_private_dedupe_survivors": safe_int(summary.get("private_dedupe_survivors")),
        "source_proof_complete_candidates": safe_int(summary.get("proof_complete_candidates")),
        "source_level3_candidates_after_private_replay": safe_int(
            summary.get("level3_candidates_after_private_replay")
        ),
        "source_patch_trace_candidates": safe_int(summary.get("patch_trace_candidates")),
        "source_accounting_table_hash": stable_hash(accounting, 24),
    }


def private_reconstruction_task(name: str, candidate_count: int) -> dict[str, Any]:
    required_private_artifacts = {
        "checkout_before_anchor": [
            "private_repository_locator",
            "private_before_anchor_identifier",
            "private_checkout_result",
            "private_workspace_cleanliness_attestation",
        ],
        "patch_application_proof": [
            "private_patch_payload",
            "private_application_command",
            "private_application_exit_status",
            "private_changed_state_attestation",
        ],
        "same_verifier_before_after": [
            "private_verifier_identity",
            "private_before_observation",
            "private_after_observation",
            "private_comparable_environment_attestation",
        ],
        "causal_transition": [
            "private_failure_before_evidence",
            "private_success_after_evidence",
            "private_patch_effect_linkage",
            "private_non_patch_confounder_check",
        ],
        "state_after": [
            "private_after_state_identifier",
            "private_after_state_cleanliness_attestation",
            "private_after_state_reproducibility_attestation",
        ],
        "stop_continue": [
            "private_stop_or_continue_label",
            "private_label_basis",
            "private_terminal_or_next_action_attestation",
        ],
    }
    public_summary_fields = {
        "checkout_before_anchor": [
            "checkout_before_anchor_present_count",
            "checkout_before_anchor_missing_count",
        ],
        "patch_application_proof": [
            "patch_application_proof_present_count",
            "patch_application_proof_missing_count",
        ],
        "same_verifier_before_after": [
            "same_verifier_before_after_present_count",
            "same_verifier_before_after_missing_count",
        ],
        "causal_transition": [
            "causal_transition_present_count",
            "causal_transition_missing_count",
        ],
        "state_after": [
            "state_after_present_count",
            "state_after_missing_count",
        ],
        "stop_continue": [
            "stop_continue_present_count",
            "stop_continue_missing_count",
        ],
    }
    return {
        "task": name,
        "request_status": "private_reconstruction_required",
        "public_artifact_executes_task": False,
        "candidate_scope_count": candidate_count,
        "private_artifacts_required": required_private_artifacts[name],
        "public_summary_counts_required": public_summary_fields[name],
        "public_value_policy": "counts_hashes_and_normalized_status_only",
        "failure_policy": "missing_or_incomparable_private_evidence_blocks_candidate",
    }


def build_request(stage12431: dict[str, Any]) -> dict[str, Any]:
    source = source_stage12431_summary(stage12431)
    source_ok = (
        bool(stage12431)
        and source["source_stage"] == EXPECTED_STAGE12431
        and source["source_guardrail_scan_passed"] is True
        and source["source_training_allowed"] is False
        and source["source_admission_allowed"] is False
        and source["source_admitted_rows"] == 0
        and source["source_emitted_rows"] == 0
        and source["source_countable_new_rows"] == 0
        and source["source_raw_leak_count"] == 0
        and source["source_overclaim_count"] == 0
        and source["source_metadata_candidate_supply_rows"] == EXPECTED_METADATA_CANDIDATE_SUPPLY_ROWS
        and source["source_private_sampled_rows"] == EXPECTED_PRIVATE_SAMPLED_ROWS
        and source["source_private_dedupe_survivors"] == EXPECTED_PRIVATE_DEDUPE_SURVIVORS
        and source["source_proof_complete_candidates"] == EXPECTED_PROOF_COMPLETE_CANDIDATES
    )
    source_candidate_count = source["source_private_dedupe_survivors"] if source_ok else 0
    task_map = {
        name: private_reconstruction_task(name, source_candidate_count) for name in RECONSTRUCTION_TASKS
    }
    task_missing_counts = {f"{name}_missing": source_candidate_count for name in RECONSTRUCTION_TASKS}
    task_present_counts = {f"{name}_present": 0 for name in RECONSTRUCTION_TASKS}
    all_slot_missing_count = source_candidate_count
    blocker_counts = {
        "public_artifact_request_only": 1,
        "stage12431_summary_missing_or_invalid": 0 if source_ok else 1,
        "private_reconstruction_not_executed_here": 1,
        "no_raw_rows_read": 1,
        "no_replay_execution_in_public_artifact": 1,
        "no_rows_admitted": 1,
        "training_gate_forced_closed": 1,
        "proof_complete_candidates_zero": 1,
        "candidate_slots_incomplete": source_candidate_count,
        **task_missing_counts,
    }

    return {
        **ZERO_COUNTERS,
        "stage": STAGE,
        "record_type": "open_swe_pilot_100_proof_slot_reconstruction_request_control_v1",
        "decision": "fail_closed_public_safe_proof_slot_reconstruction_request_no_rows_admitted",
        "claim_boundary": (
            "Stage12432 reads only the Stage12431 public summary and requests private proof-slot "
            "reconstruction. It emits no row values and performs no replay, checkout, patch application, "
            "verifier, test, admission, or training execution."
        ),
        "input_summary_hashes": {
            "stage12431_summary": file_hash(STAGE12431_SUMMARY),
        },
        "input_summary_presence": {
            "stage12431_summary": STAGE12431_SUMMARY.exists(),
        },
        "source_summary": source,
        "source_preconditions": {
            "stage12431_summary_present": bool(stage12431),
            "stage12431_guardrail_scan_passed": source["source_guardrail_scan_passed"] is True,
            "stage12431_raw_leak_count_zero": source["source_raw_leak_count"] == 0,
            "stage12431_overclaim_count_zero": source["source_overclaim_count"] == 0,
            "stage12431_training_allowed_false": source["source_training_allowed"] is False,
            "stage12431_admission_allowed_false": source["source_admission_allowed"] is False,
            "stage12431_no_rows_admitted_or_emitted": (
                source["source_admitted_rows"] == 0 and source["source_emitted_rows"] == 0
            ),
            "stage12431_countable_new_rows_zero": source["source_countable_new_rows"] == 0,
            "stage12431_expected_public_accounting_present": source_ok,
            "source_eligible_for_private_reconstruction_request_only": source_ok,
        },
        "metadata_candidate_supply_rows": source["source_metadata_candidate_supply_rows"],
        "private_sampled_rows": source["source_private_sampled_rows"],
        "private_dedupe_survivors": source["source_private_dedupe_survivors"],
        "proof_complete_candidates": source["source_proof_complete_candidates"],
        "level3_candidates_after_private_replay": source["source_level3_candidates_after_private_replay"],
        "patch_trace_candidates": source["source_patch_trace_candidates"],
        "source_accounting_table": {
            "metadata_candidate_supply_rows": source["source_metadata_candidate_supply_rows"],
            "private_sampled_rows": source["source_private_sampled_rows"],
            "private_dedupe_survivors": source["source_private_dedupe_survivors"],
            "proof_complete_candidates": source["source_proof_complete_candidates"],
        },
        "candidate_supply_rows_are_not_training_rows": True,
        "private_reconstruction_request": {
            "request_status": "REQUESTED_FOR_PRIVATE_RUNNER_ONLY",
            "public_artifact_can_execute": False,
            "public_artifact_reads_stage12431_summary_only": True,
            "private_runner_must_not_return_private_values_to_public": True,
            "private_runner_output_must_be_public_safe_summary_only": True,
            "candidate_scope": "stage12431_private_dedupe_survivors",
            "candidate_scope_count": source_candidate_count,
            "required_tasks": RECONSTRUCTION_TASKS,
        },
        "private_reconstruction_tasks": task_map,
        "required_private_reconstruction_tasks": RECONSTRUCTION_TASKS,
        "public_safe_output_schema": {
            "allowed_top_level_fields": [
                "stage",
                "record_type",
                "decision",
                "training_allowed",
                "admission_allowed",
                "admitted_rows",
                "emitted_rows",
                "countable_new_rows",
                "metadata_candidate_supply_rows",
                "private_sampled_rows",
                "private_dedupe_survivors",
                "proof_complete_candidates",
                "proof_slot_status_counts",
                "blocker_counts",
                "acceptance_floor_status",
                "stop_condition_counts",
                "guardrail_scan_passed",
                "raw_leak_count",
                "overclaim_count",
                "next_stage_recommendation",
            ],
            "required_public_counts_after_private_reconstruction": [
                "checkout_before_anchor_present_count",
                "patch_application_proof_present_count",
                "same_verifier_before_after_present_count",
                "causal_transition_present_count",
                "state_after_present_count",
                "stop_continue_present_count",
                "all_required_slots_complete_count",
                "drop_reason_counts",
            ],
            "forbidden_public_values": [
                "raw row values",
                "raw locators",
                "commands",
                "command outputs",
                "patch or diff content",
                "file path values",
                "web addresses",
                "repository identities",
                "commit identities",
                "issue body text",
                "source text",
                "private proof-slot values",
            ],
            "aggregate_only": True,
            "hashes_allowed": True,
            "counts_allowed": True,
            "normalized_status_allowed": True,
        },
        "private_only_fields": [
            "raw_row_identifier",
            "raw_task_payload",
            "raw_event_sequence",
            "raw_locator_value",
            "raw_command_value",
            "raw_command_result",
            "raw_patch_value",
            "raw_diff_value",
            "raw_file_path_value",
            "raw_web_address_value",
            "raw_issue_text",
            "raw_source_text",
            "private_repository_identity",
            "private_commit_identity",
            "private_before_anchor_identifier",
            "private_after_state_identifier",
            "private_verifier_identity",
            "private_before_observation",
            "private_after_observation",
            "private_stop_or_continue_label",
        ],
        "proof_slot_status_counts": {
            **task_present_counts,
            **task_missing_counts,
            "all_required_slots_complete": 0,
            "all_required_slots_missing": all_slot_missing_count,
            "candidate_scope_count": source_candidate_count,
        },
        "blocker_counts": blocker_counts,
        "acceptance_floors": {
            "raw_leak_count_must_equal": 0,
            "overclaim_count_must_equal": 0,
            "protected_split_overlap_count_must_equal": 0,
            "private_sampled_rows_must_equal": EXPECTED_PRIVATE_SAMPLED_ROWS,
            "private_dedupe_survivors_must_equal": EXPECTED_PRIVATE_DEDUPE_SURVIVORS,
            "reconstruction_scope_should_attempt_all_dedupe_survivors": EXPECTED_PRIVATE_DEDUPE_SURVIVORS,
            "minimum_checkout_before_anchor_present_for_scope_accounting": EXPECTED_PRIVATE_DEDUPE_SURVIVORS,
            "minimum_same_verifier_before_after_present_for_scope_accounting": EXPECTED_PRIVATE_DEDUPE_SURVIVORS,
            "minimum_stop_continue_present_for_scope_accounting": EXPECTED_PRIVATE_DEDUPE_SURVIVORS,
            "minimum_all_required_slots_complete_for_pilot_pass": 20,
            "minimum_level3_candidates_after_private_replay_for_pilot_pass": 20,
            "minimum_patch_trace_candidates_for_pilot_pass": 12,
            "minimum_same_verifier_before_after_for_pilot_pass": 8,
            "minimum_state_transition_anchor_for_pilot_pass": 30,
            "minimum_stop_continue_anchor_for_pilot_pass": 20,
            "admitted_rows_must_equal_until_private_summary_passes": 0,
            "countable_new_rows_must_equal_until_private_summary_passes": 0,
        },
        "acceptance_floor_status": {
            "stage12431_public_accounting_floor": "PASS" if source_ok else "BLOCKED",
            "private_reconstruction_not_performed_by_public_artifact": "PASS",
            "checkout_before_anchor_scope_accounting": "BLOCKED",
            "patch_application_proof_scope_accounting": "BLOCKED",
            "same_verifier_before_after_scope_accounting": "BLOCKED",
            "causal_transition_scope_accounting": "BLOCKED",
            "state_after_scope_accounting": "BLOCKED",
            "stop_continue_scope_accounting": "BLOCKED",
            "pilot_level3_floor": "BLOCKED",
            "pilot_patch_trace_floor": "BLOCKED",
            "admission_floor": "BLOCKED_FAIL_CLOSED",
            "training_floor": "BLOCKED_FAIL_CLOSED",
        },
        "stop_conditions": [
            "stage12431_summary_missing_or_guardrail_not_clean",
            "stage12431_public_accounting_mismatch",
            "private_runner_attempts_to_return_private_values_to_public",
            "any_public_raw_leak_count_nonzero",
            "any_public_overclaim_count_nonzero",
            "protected_split_overlap_count_nonzero",
            "candidate_scope_count_mismatch",
            "checkout_before_anchor_missing",
            "patch_application_proof_missing",
            "same_verifier_before_after_missing",
            "causal_transition_missing",
            "state_after_missing",
            "stop_continue_missing",
            "same_verifier_before_after_incomparable",
            "causal_transition_not_attributable_to_patch",
            "public_summary_contains_private_field_values",
            "public_postrun_accounting_table_missing_or_incomplete",
        ],
        "stop_condition_counts": {
            "stage12431_summary_missing_or_guardrail_not_clean": 0 if source_ok else 1,
            "private_reconstruction_not_executed_by_public_artifact": 1,
            "candidate_scope_count_mismatch": 0,
            "all_required_slots_incomplete": source_candidate_count,
            **task_missing_counts,
        },
        "raw_content_policy": RAW_CONTENT_POLICY,
        "next_stage_recommendation": (
            "run_private_proof_slot_reconstruction_for_stage12431_dedupe_survivors_and_emit_public_safe_summary_only"
        ),
    }


def guardrail_scan(value: dict[str, Any]) -> dict[str, Any]:
    payload = json.dumps(value, sort_keys=True)
    raw_matches = FORBIDDEN_TEXT_RE.findall(payload)
    zero_counter_failures = [
        key for key, expected in ZERO_COUNTERS.items() if value.get(key) != expected
    ]
    raw_policy_failures = [
        key
        for key, expected in RAW_CONTENT_POLICY.items()
        if value.get("raw_content_policy", {}).get(key) != expected
    ]
    issues = (
        (["forbidden_raw_text_pattern_detected"] if raw_matches else [])
        + [f"nonzero_or_true_zero_counter:{key}" for key in zero_counter_failures]
        + [f"raw_content_policy_failure:{key}" for key in raw_policy_failures]
    )
    return {
        "scan_passed": not issues,
        "raw_leak_count": len(raw_matches),
        "overclaim_count": 0,
        "issue_count": len(issues),
        "issues": issues,
        "zero_counter_keys_checked": sorted(ZERO_COUNTERS),
        "raw_content_policy_keys_checked": sorted(RAW_CONTENT_POLICY),
        "scan_scope": "public_request_payload_stage12431_summary_only",
    }


def finalize(summary: dict[str, Any]) -> dict[str, Any]:
    pre_scan = guardrail_scan(summary)
    summary["guardrail_scan"] = pre_scan
    summary["guardrail_scan_passed"] = pre_scan["scan_passed"]
    summary["raw_leak_count"] = pre_scan["raw_leak_count"]
    summary["overclaim_count"] = pre_scan["overclaim_count"]
    summary["summary_hash"] = stable_hash({k: v for k, v in summary.items() if k != "summary_hash"})
    post_scan = guardrail_scan(summary)
    summary["guardrail_scan"] = post_scan
    summary["guardrail_scan_passed"] = post_scan["scan_passed"]
    summary["raw_leak_count"] = post_scan["raw_leak_count"]
    summary["overclaim_count"] = post_scan["overclaim_count"]
    summary["summary_hash"] = stable_hash({k: v for k, v in summary.items() if k != "summary_hash"})
    return summary


def main() -> None:
    stage12431 = read_json(STAGE12431_SUMMARY)
    summary = finalize(build_request(stage12431))

    write_json(OUT / f"{STAGE}.json", summary)
    write_json(OUT / "summary.json", summary)
    write_json(OUT / "guardrail_scan.json", summary["guardrail_scan"])
    write_json(SUMMARY, summary)

    if not summary["guardrail_scan_passed"]:
        raise SystemExit(f"guardrail scan failed with {summary['guardrail_scan']['issue_count']} issues")

    print(
        json.dumps(
            {
                "stage": STAGE,
                "decision": summary["decision"],
                "training_allowed": summary["training_allowed"],
                "admission_allowed": summary["admission_allowed"],
                "metadata_candidate_supply_rows": summary["metadata_candidate_supply_rows"],
                "private_sampled_rows": summary["private_sampled_rows"],
                "private_dedupe_survivors": summary["private_dedupe_survivors"],
                "proof_complete_candidates": summary["proof_complete_candidates"],
                "admitted_rows": summary["admitted_rows"],
                "emitted_rows": summary["emitted_rows"],
                "countable_new_rows": summary["countable_new_rows"],
                "required_tasks": summary["required_private_reconstruction_tasks"],
                "guardrail_scan_passed": summary["guardrail_scan_passed"],
                "raw_leak_count": summary["raw_leak_count"],
                "overclaim_count": summary["overclaim_count"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
