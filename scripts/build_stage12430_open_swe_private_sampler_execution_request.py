#!/usr/bin/env python3
"""Stage12430 Open-SWE private sampler execution request.

This generator is intentionally public-safe and fail-closed. It reads only the
Stage12429 public summary, requests a private pilot sampler run, and emits no
raw Open-SWE rows, locators, commands, outputs, patches, paths, or URLs.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12430_open_swe_private_sampler_execution_request"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
STAGE12429_SUMMARY = ROOT / "runs/summaries/stage12429_open_swe_scaling_ramp_control.json"

CANDIDATE_SUPPLY_ROWS = 207489
REQUESTED_PHASE = "pilot_100"
REQUESTED_PRIVATE_CANDIDATE_COUNT = 100

ZERO_COUNTERS: dict[str, bool | int] = {
    "training_allowed": False,
    "admission_allowed": False,
    "execution_allowed_by_public_artifact": False,
    "sampler_executed_by_public_artifact": False,
    "admitted_rows": 0,
    "emitted_rows": 0,
    "emitted_training_rows": 0,
    "countable_rows": 0,
    "countable_new_rows": 0,
    "raw_rows_inspected": 0,
    "raw_rows_copied": 0,
    "raw_content_emitted": False,
    "replay_attempted_count": 0,
    "patch_apply_attempted_count": 0,
    "tests_run_count": 0,
}

RAW_CONTENT_POLICY: dict[str, bool] = {
    "raw_trajectories_emitted": False,
    "raw_locators_emitted": False,
    "raw_commands_emitted": False,
    "raw_outputs_emitted": False,
    "raw_diffs_emitted": False,
    "raw_patches_emitted": False,
    "raw_paths_emitted": False,
    "urls_emitted": False,
    "source_text_emitted": False,
    "training_rows_emitted": False,
    "row_values_emitted": False,
}

FORBIDDEN_TEXT_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:Traceback \(most recent call last\)|stdout|stderr|pytest |npm |pip |git clone|git apply|curl )\b",
    re.IGNORECASE | re.MULTILINE,
)

UNSAFE_FIELD_NAME_RE = re.compile(
    r"(?:url|uri|path|locator|command|output|stdout|stderr|patch|diff|trace|source_text|issue_body)",
    re.IGNORECASE,
)

SAFE_UNSAFE_FIELD_CONTEXTS = {
    "dedupe_ledger_requirements",
    "input_summary_hashes",
    "input_summary_presence",
    "minimum_public_postrun_floor_requirements",
    "private_only_field_list",
    "private_execution_request",
    "private_execution_controls",
    "promotion_gate_status",
    "proof_slot_checklist",
    "public_safe_output_schema",
    "quota_caps",
    "raw_content_policy",
    "required_public_postrun_accounting_table",
    "source_summary",
    "guardrail_scan",
}


SAFE_AGGREGATE_FIELD_NAMES = {
    "patch_apply_attempted_count",
    "public_safe_output_schema",
}


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


def source_stage12429_summary(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_stage": summary.get("stage"),
        "source_decision": summary.get("decision"),
        "source_training_allowed": summary.get("training_allowed", False),
        "source_admission_allowed": summary.get("admission_allowed", False),
        "source_guardrail_scan_passed": summary.get("guardrail_scan_passed", False),
        "source_raw_leak_count": safe_int(summary.get("raw_leak_count")),
        "source_overclaim_count": safe_int(summary.get("overclaim_count")),
        "source_candidate_supply_rows": safe_int(summary.get("candidate_supply_rows")),
        "source_admitted_rows": safe_int(summary.get("admitted_rows")),
        "source_emitted_rows": safe_int(summary.get("emitted_rows")),
        "source_countable_new_rows": safe_int(summary.get("countable_new_rows")),
        "source_requested_phase_available": REQUESTED_PHASE
        in summary.get("ramp_phases", {}),
    }


def ramp_option(
    *,
    phase: str,
    private_candidate_count: int,
    prior_public_summary_required: str,
    max_private_candidates_per_repository_family: int,
    max_private_candidates_per_language_family: int,
    max_private_candidates_per_source_bucket: int,
) -> dict[str, Any]:
    return {
        "phase": phase,
        "requested_private_candidate_count": private_candidate_count,
        "allowed_by_this_public_artifact": False,
        "prior_public_summary_required": prior_public_summary_required,
        "quota_caps": {
            "max_private_candidates_per_repository_family": max_private_candidates_per_repository_family,
            "max_private_candidates_per_language_family": max_private_candidates_per_language_family,
            "max_private_candidates_per_source_bucket": max_private_candidates_per_source_bucket,
            "max_resolved_label_share": 0.50,
            "max_unknown_or_other_label_share": 0.25,
            "max_duplicate_cluster_share": 0.08,
            "max_controlled_fixture_share": 0.0,
        },
        "release_gate": "requires_private_sampler_postrun_public_safe_summary_with_clean_guardrail_scan",
    }


def build_request(stage12429: dict[str, Any]) -> dict[str, Any]:
    source = source_stage12429_summary(stage12429)
    source_ok = (
        bool(stage12429)
        and source["source_stage"] == "stage12429_open_swe_scaling_ramp_control"
        and source["source_training_allowed"] is False
        and source["source_admission_allowed"] is False
        and source["source_guardrail_scan_passed"] is True
        and source["source_raw_leak_count"] == 0
        and source["source_overclaim_count"] == 0
        and source["source_candidate_supply_rows"] == CANDIDATE_SUPPLY_ROWS
        and source["source_admitted_rows"] == 0
        and source["source_emitted_rows"] == 0
        and source["source_countable_new_rows"] == 0
        and source["source_requested_phase_available"] is True
    )
    next_ramp_options = [
        ramp_option(
            phase="scale_500",
            private_candidate_count=500,
            prior_public_summary_required="pilot_100",
            max_private_candidates_per_repository_family=25,
            max_private_candidates_per_language_family=125,
            max_private_candidates_per_source_bucket=125,
        ),
        ramp_option(
            phase="scale_1k",
            private_candidate_count=1000,
            prior_public_summary_required="scale_500",
            max_private_candidates_per_repository_family=40,
            max_private_candidates_per_language_family=200,
            max_private_candidates_per_source_bucket=250,
        ),
        ramp_option(
            phase="scale_2k",
            private_candidate_count=2000,
            prior_public_summary_required="scale_1k",
            max_private_candidates_per_repository_family=60,
            max_private_candidates_per_language_family=350,
            max_private_candidates_per_source_bucket=500,
        ),
        ramp_option(
            phase="scale_5k",
            private_candidate_count=5000,
            prior_public_summary_required="scale_2k",
            max_private_candidates_per_repository_family=100,
            max_private_candidates_per_language_family=800,
            max_private_candidates_per_source_bucket=1250,
        ),
        ramp_option(
            phase="scale_10k",
            private_candidate_count=10000,
            prior_public_summary_required="scale_5k",
            max_private_candidates_per_repository_family=160,
            max_private_candidates_per_language_family=1400,
            max_private_candidates_per_source_bucket=2500,
        ),
    ]
    request = {
        **ZERO_COUNTERS,
        "stage": STAGE,
        "record_type": "open_swe_private_sampler_execution_request_control_v1",
        "decision": "fail_closed_public_safe_private_sampler_request_no_rows_admitted",
        "claim_boundary": (
            "This artifact requests private sampler execution only. It is public-safe, contains no private "
            "row values, and does not authorize training, admission, replay, patch application, or test execution."
        ),
        "input_summary_hashes": {
            "stage12429_summary": file_hash(STAGE12429_SUMMARY),
        },
        "input_summary_presence": {
            "stage12429_summary": STAGE12429_SUMMARY.exists(),
        },
        "source_summary": source,
        "source_preconditions": {
            "stage12429_summary_present": bool(stage12429),
            "stage12429_guardrail_scan_passed": source["source_guardrail_scan_passed"] is True,
            "stage12429_raw_leak_count_zero": source["source_raw_leak_count"] == 0,
            "stage12429_overclaim_count_zero": source["source_overclaim_count"] == 0,
            "stage12429_training_allowed_false": source["source_training_allowed"] is False,
            "stage12429_admission_allowed_false": source["source_admission_allowed"] is False,
            "stage12429_no_rows_admitted_or_emitted": (
                source["source_admitted_rows"] == 0 and source["source_emitted_rows"] == 0
            ),
            "stage12429_candidate_supply_matches_expected": (
                source["source_candidate_supply_rows"] == CANDIDATE_SUPPLY_ROWS
            ),
            "stage12429_requested_phase_available": source["source_requested_phase_available"] is True,
            "source_eligible_for_private_request_only": source_ok,
        },
        "candidate_supply_rows": CANDIDATE_SUPPLY_ROWS,
        "requested_phase": REQUESTED_PHASE,
        "requested_private_candidate_count": REQUESTED_PRIVATE_CANDIDATE_COUNT,
        "candidate_supply_rows_are_not_training_rows": True,
        "private_execution_request": {
            "request_status": "REQUESTED_FOR_PRIVATE_RUNNER_ONLY",
            "public_artifact_can_execute": False,
            "private_runner_must_not_return_private_values_to_public": True,
            "private_runner_output_must_be_public_safe_summary_only": True,
            "requested_sample_exactly": REQUESTED_PRIVATE_CANDIDATE_COUNT,
            "fail_closed_if_requested_count_unavailable_after_dedupe": True,
        },
        "private_only_field_list": [
            "raw_row_identifier",
            "raw_task_payload",
            "raw_event_sequence",
            "raw_locator_value",
            "raw_command_value",
            "raw_command_result",
            "raw_patch_value",
            "raw_diff_value",
            "raw_file_path_value",
            "raw_url_value",
            "raw_issue_text",
            "raw_source_text",
            "private_repo_identity",
            "private_commit_identity",
        ],
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
                "candidate_supply_rows",
                "requested_phase",
                "requested_private_candidate_count",
                "aggregate_bucket_counts",
                "proof_slot_status_counts",
                "dedupe_status_counts",
                "quota_status_counts",
                "stop_condition_counts",
                "guardrail_scan_passed",
                "raw_leak_count",
                "overclaim_count",
                "next_stage_recommendation",
            ],
            "forbidden_public_values": [
                "raw rows",
                "raw locators",
                "commands",
                "command output",
                "patch content",
                "file path values",
                "URLs",
                "repository identities",
                "commit identities",
                "issue body text",
            ],
            "aggregate_only": True,
            "hashes_allowed": True,
            "counts_allowed": True,
        },
        "proof_slot_checklist": {
            "same_source_lineage_present": "REQUIRED_PRIVATE",
            "private_locator_resolves": "REQUIRED_PRIVATE",
            "checkout_before_anchor_present": "REQUIRED_PRIVATE",
            "same_verifier_before_after_present": "REQUIRED_PRIVATE",
            "patch_application_proof_present": "REQUIRED_PRIVATE",
            "causal_transition_present": "REQUIRED_PRIVATE",
            "stop_or_continue_label_present": "REQUIRED_PRIVATE",
            "protected_overlap_and_leak_audit_present": "REQUIRED_PRIVATE",
            "public_safe_summary_guardrail_scan_passed": "REQUIRED_PUBLIC",
        },
        "dedupe_ledger_requirements": {
            "dedupe_against_existing_countable_ledgers": "REQUIRED_PRIVATE",
            "dedupe_against_current_stage_candidates": "REQUIRED_PRIVATE",
            "dedupe_keys_must_remain_private": True,
            "public_output_may_emit_counts_only": True,
            "protected_split_overlap_count_must_equal": 0,
            "duplicate_cluster_policy": "reject_or_downsample_before_public_summary",
        },
        "quota_caps": {
            "sample_exactly": REQUESTED_PRIVATE_CANDIDATE_COUNT,
            "max_private_candidates_per_repository_family": 10,
            "max_private_candidates_per_language_family": 25,
            "max_private_candidates_per_source_bucket": 25,
            "max_resolved_label_candidates": 50,
            "max_unresolved_label_candidates": 35,
            "max_unknown_or_other_label_candidates": 25,
            "min_distinct_repositories": 10,
            "min_distinct_language_families": 3,
            "min_absent_from_existing_countable_ledgers": 40,
            "min_direct_verifier_anchor_present": 40,
            "min_state_transition_anchor_present": 30,
            "min_stop_or_continue_anchor_present": 20,
            "min_same_verifier_before_after_present": 8,
            "min_replayable_patch_trace_candidates": 12,
            "min_level3_candidates_after_private_replay": 20,
            "max_controlled_fixture_share": 0.0,
        },
        "required_public_postrun_accounting_table": {
            "metadata_candidate_supply_rows": CANDIDATE_SUPPLY_ROWS,
            "private_sampled_rows": "REQUIRED_COUNT",
            "private_dedupe_survivors": "REQUIRED_COUNT",
            "proof_complete_candidates": "REQUIRED_COUNT",
            "level3_candidates_after_private_replay": "REQUIRED_COUNT",
            "patch_trace_candidates": "REQUIRED_COUNT",
            "admitted_training_rows": 0,
            "countable_new_rows": 0,
            "must_explain_each_drop_with_reason_counts": True,
        },
        "minimum_public_postrun_floor_requirements": {
            "private_sampled_rows_must_equal": REQUESTED_PRIVATE_CANDIDATE_COUNT,
            "minimum_distinct_repositories": 10,
            "minimum_distinct_language_families": 3,
            "minimum_level3_candidates_after_private_replay": 20,
            "minimum_replayable_patch_trace_candidates": 12,
            "minimum_same_verifier_before_after_present": 8,
            "minimum_state_transition_anchor_present": 30,
            "minimum_stop_or_continue_anchor_present": 20,
            "raw_leak_count_must_equal": 0,
            "overclaim_count_must_equal": 0,
            "protected_split_overlap_count_must_equal": 0,
        },
        "next_ramp_options": next_ramp_options,
        "stop_conditions": [
            "stage12429_summary_missing_or_guardrail_not_clean",
            "private_sampler_attempts_to_return_raw_values_to_public",
            "requested_private_candidate_count_not_met_after_dedupe",
            "any_public_raw_leak_count_nonzero",
            "any_public_overclaim_count_nonzero",
            "protected_split_overlap_count_nonzero",
            "dedupe_against_existing_countable_ledgers_incomplete",
            "quota_caps_exceeded",
            "proof_slot_floor_missing",
            "level3_or_stop_continue_floor_missing",
            "public_postrun_accounting_table_missing_or_incomplete",
            "public_summary_contains_private_field_values",
        ],
        "blocked_reason_counts": {
            "public_artifact_request_only": 1,
            "private_sampler_not_executed_here": 1,
            "no_raw_rows_read": 1,
            "no_rows_admitted": 1,
            "training_gate_not_open": 1,
            "public_safe_postrun_summary_required_before_admission": 1,
        },
        "promotion_gate_status": {
            "artifact_is_public_safe_request_only": "PASS",
            "stage12429_summary_reused_only": "PASS" if source_ok else "BLOCKED",
            "training_allowed": "PASS_FALSE",
            "admission_allowed": "PASS_FALSE",
            "no_rows_admitted": "PASS",
            "no_rows_emitted": "PASS",
            "raw_values_not_emitted": "PASS",
            "private_sampler_execution_not_performed_by_public_artifact": "PASS",
        },
        "raw_content_policy": RAW_CONTENT_POLICY,
        "next_stage_recommendation": (
            "run_private_pilot_100_sampler_and_emit_public_safe_postrun_summary_only"
        ),
    }
    return request


def scan_field_names(value: Any, parents: tuple[str, ...] = ()) -> list[str]:
    if isinstance(value, dict):
        failures: list[str] = []
        for key, child in value.items():
            if (
                UNSAFE_FIELD_NAME_RE.search(key)
                and key not in SAFE_AGGREGATE_FIELD_NAMES
                and not any(parent in SAFE_UNSAFE_FIELD_CONTEXTS for parent in parents)
            ):
                failures.append(f"unsafe_field_name_outside_policy_context:{'/'.join(parents + (str(key),))}")
            failures.extend(scan_field_names(child, parents + (str(key),)))
        return failures
    if isinstance(value, list):
        failures = []
        for child in value:
            failures.extend(scan_field_names(child, parents))
        return failures
    return []


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
    field_name_failures = scan_field_names(value)
    issues = (
        (["forbidden_raw_text_pattern_detected"] if raw_matches else [])
        + [f"nonzero_or_true_zero_counter:{key}" for key in zero_counter_failures]
        + [f"raw_content_policy_failure:{key}" for key in raw_policy_failures]
        + field_name_failures
    )
    return {
        "scan_passed": not issues,
        "raw_leak_count": len(raw_matches),
        "overclaim_count": 0,
        "issue_count": len(issues),
        "issues": issues,
        "zero_counter_keys_checked": sorted(ZERO_COUNTERS),
        "raw_content_policy_keys_checked": sorted(RAW_CONTENT_POLICY),
        "field_name_policy_checked": True,
    }


def main() -> None:
    stage12429 = read_json(STAGE12429_SUMMARY)
    request = build_request(stage12429)
    pre_scan = guardrail_scan(request)
    if not pre_scan["scan_passed"]:
        raise SystemExit(f"guardrail scan failed before artifact emission: {pre_scan['issue_count']} issues")

    request["guardrail_scan"] = pre_scan
    request["guardrail_scan_passed"] = True
    request["raw_leak_count"] = 0
    request["overclaim_count"] = 0
    request["summary_hash"] = stable_hash({k: v for k, v in request.items() if k != "summary_hash"})
    post_scan = guardrail_scan(request)
    if not post_scan["scan_passed"]:
        raise SystemExit(f"guardrail scan failed before artifact emission: {post_scan['issue_count']} issues")
    request["guardrail_scan"] = post_scan
    request["summary_hash"] = stable_hash({k: v for k, v in request.items() if k != "summary_hash"})

    write_json(OUT / "stage12430_open_swe_private_sampler_execution_request.json", request)
    write_json(OUT / "guardrail_scan.json", post_scan)
    write_json(OUT / "summary.json", request)
    write_json(SUMMARY, request)

    print(
        json.dumps(
            {
                "stage": STAGE,
                "decision": request["decision"],
                "training_allowed": request["training_allowed"],
                "admitted_rows": request["admitted_rows"],
                "emitted_rows": request["emitted_rows"],
                "countable_new_rows": request["countable_new_rows"],
                "candidate_supply_rows": request["candidate_supply_rows"],
                "requested_phase": request["requested_phase"],
                "requested_private_candidate_count": request["requested_private_candidate_count"],
                "guardrail_scan_passed": request["guardrail_scan_passed"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
