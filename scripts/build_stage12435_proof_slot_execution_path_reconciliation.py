#!/usr/bin/env python3
"""Stage12435 proof-slot execution path reconciliation.

This control artifact reconciles the session-like materializer lane with the
Open-SWE proof-slot execution lane. It reads only public-safe summaries, emits
aggregate counts and decision metadata, performs no execution, admits no rows,
and keeps training closed.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12435_proof_slot_execution_path_reconciliation"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

INPUTS = {
    "stage12316_session_like_joiner": ROOT / "runs/summaries/stage12316_transition_local_event_joiner.json",
    "stage12386_session_like_gap_audit": ROOT / "runs/summaries/stage12386_transition_local_event_joiner_gap_audit.json",
    "stage12433_open_swe_proof_slot_postrun": ROOT
    / "runs/summaries/stage12433_open_swe_pilot_100_private_proof_slot_runner_postrun.json",
    "stage12434_open_swe_adapter_decision": ROOT
    / "runs/summaries/stage12434_replay_source_adapter_decision_after_open_swe_probe.json",
}

ZERO_COUNTERS: dict[str, bool | int] = {
    "training_allowed": False,
    "admission_allowed": False,
    "execution_allowed": False,
    "admitted_rows": 0,
    "emitted_rows": 0,
    "emitted_training_rows": 0,
    "new_training_rows_emitted": 0,
    "countable_rows": 0,
    "countable_new_rows": 0,
    "countable_as_new_train_support_rows": 0,
    "countable_as_new_proof_floor_rows": 0,
    "raw_rows_inspected": 0,
    "raw_rows_copied": 0,
    "raw_content_emitted": False,
    "replay_attempted_count": 0,
    "checkout_execution_attempted_count": 0,
    "patch_apply_attempted_count": 0,
    "verifier_execution_attempted_count": 0,
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

OVERCLAIM_RE = re.compile(
    r"\b(?:training rows|admitted training|admission allowed|level3 complete|"
    r"closed loop|verified repair|causal proof|patch applied|replay succeeded|tests passed)\b",
    re.IGNORECASE,
)

ALLOWED_OVERCLAIM_CONTEXT_RE = re.compile(
    r"(false|zero|none|not_|no_|blocked|fail_closed|candidate|control|proof_slot|"
    r"training_allowed|admission_allowed|admitted_rows|emitted_training_rows|"
    r"level3_control|level3_candidates|attempted_count|not_executed|required|"
    r"gate|floor|pilot|ramp|reconciliation|materializer|executor)",
    re.IGNORECASE,
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


def nested_int(payload: dict[str, Any], *path: str) -> int:
    value: Any = payload
    for key in path:
        if not isinstance(value, dict):
            return 0
        value = value.get(key)
    return safe_int(value)


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def guardrail_clean(payload: dict[str, Any]) -> bool:
    if payload.get("guardrail_scan_passed") is True:
        return True
    guardrail = payload.get("guardrail_scan")
    return isinstance(guardrail, dict) and guardrail.get("scan_passed") is True


def input_inventory() -> dict[str, dict[str, Any]]:
    return {
        label: {
            "present": path.exists() and path.is_file(),
            "sha256_24": file_hash(path),
        }
        for label, path in INPUTS.items()
    }


def source_controls(inputs: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    controls: dict[str, dict[str, Any]] = {}
    for label, payload in inputs.items():
        controls[label] = {
            "present": bool(payload),
            "stage_hash": stable_hash(payload.get("stage"), 16),
            "decision_hash": stable_hash(payload.get("decision"), 16),
            "guardrail_scan_passed": guardrail_clean(payload),
            "training_allowed": payload.get("training_allowed", False),
            "admission_allowed": payload.get("admission_allowed", False),
            "admitted_rows": safe_int(payload.get("admitted_rows")),
            "emitted_training_rows": safe_int(
                payload.get("emitted_training_rows", payload.get("new_training_rows_emitted", 0))
            ),
            "raw_leak_count": safe_int(payload.get("raw_leak_count")),
            "overclaim_count": safe_int(payload.get("overclaim_count")),
        }
    return controls


def session_lane_counts(stage12316: dict[str, Any], stage12386: dict[str, Any]) -> dict[str, Any]:
    classification_counts = safe_dict(stage12386.get("classification_counts"))
    missing_transition = safe_dict(stage12386.get("missing_transition_local_field_counts"))
    missing_level3 = safe_dict(stage12386.get("missing_level3_baseline_field_counts"))
    blocked_reason_counts = safe_dict(stage12316.get("blocked_reason_counts"))
    return {
        "lane": "session_like_materializer_upgrade",
        "stage12316_records": safe_int(stage12316.get("records")),
        "stage12316_semantic_rule_candidate_records": safe_int(stage12316.get("semantic_rule_candidate_records")),
        "stage12316_train_grade_after_policy_label_review": safe_int(
            stage12316.get("train_grade_after_policy_label_review")
        ),
        "stage12316_training_rows_emitted": safe_int(stage12316.get("training_rows_emitted")),
        "stage12316_level3_admitted": safe_int(stage12316.get("level3_admitted")),
        "stage12316_patch_trace_admitted": safe_int(stage12316.get("patch_trace_admitted")),
        "stage12316_blocked_reason_counts": blocked_reason_counts,
        "stage12386_records_audited": safe_int(stage12386.get("records_audited")),
        "stage12386_classification_counts": classification_counts,
        "stage12386_true_new_transition_rows_available_without_manual_review": safe_int(
            stage12386.get("true_new_transition_rows_available_without_manual_review")
        ),
        "stage12386_new_training_rows_emitted": safe_int(stage12386.get("new_training_rows_emitted")),
        "stage12386_missing_transition_local_field_counts": missing_transition,
        "stage12386_missing_level3_baseline_field_counts": missing_level3,
        "candidate_only_rows": safe_int(classification_counts.get("candidate_only")),
        "transition_local_incomplete_rows": safe_int(classification_counts.get("transition_local_incomplete")),
        "verifier_observation_support_rows": safe_int(classification_counts.get("verifier_observation_support")),
        "level3_control_complete_rows": safe_int(classification_counts.get("level3_control_complete")),
        "admitted_rows": 0,
        "training_allowed": False,
        "execution_attempted_by_stage12435": False,
    }


def open_swe_lane_counts(stage12433: dict[str, Any], stage12434: dict[str, Any]) -> dict[str, Any]:
    current = safe_dict(stage12434.get("current_counts_from_stage12433")) or stage12433
    return {
        "lane": "open_swe_replay_executor_pilot_20",
        "metadata_candidate_supply_rows": safe_int(current.get("metadata_candidate_supply_rows")),
        "metadata_rows_observed_private": safe_int(current.get("metadata_rows_observed_private")),
        "parquet_shard_count": safe_int(current.get("parquet_shard_count")),
        "dataset_root_hit_count": safe_int(current.get("dataset_root_hit_count")),
        "private_sampled_rows": safe_int(current.get("private_sampled_rows")),
        "private_rows_inspected": safe_int(current.get("private_rows_inspected")),
        "private_dedupe_survivors": safe_int(current.get("private_dedupe_survivors")),
        "proof_complete_candidates": safe_int(current.get("proof_complete_candidates")),
        "patch_trace_candidates": safe_int(current.get("patch_trace_candidates")),
        "level3_candidates_after_private_replay": safe_int(current.get("level3_candidates_after_private_replay")),
        "proof_slot_present_counts": safe_dict(current.get("proof_slot_present_counts")),
        "proof_slot_recoverable_counts": safe_dict(current.get("proof_slot_recoverable_counts")),
        "proof_slot_missing_counts": safe_dict(current.get("proof_slot_missing_counts")),
        "actual_execution_attempt_counts": safe_dict(current.get("actual_execution_attempt_counts")),
        "checkout_execution_attempted_count": safe_int(current.get("checkout_execution_attempted_count")),
        "patch_apply_attempted_count": safe_int(current.get("patch_apply_attempted_count")),
        "verifier_execution_attempted_count": safe_int(current.get("verifier_execution_attempted_count")),
        "replay_attempted_count": safe_int(current.get("replay_attempted_count")),
        "stage12434_rank1_option_hash": stable_hash(
            (stage12434.get("ranked_next_adapter_options") or [{}])[0]
            if isinstance(stage12434.get("ranked_next_adapter_options"), list)
            and stage12434.get("ranked_next_adapter_options")
            else {},
            16,
        ),
        "admitted_rows": 0,
        "training_allowed": False,
        "execution_attempted_by_stage12435": False,
    }


def required_next_stages() -> list[dict[str, Any]]:
    return [
        {
            "stage": "stage12436_parallel_two_lane_control_request",
            "lane": "control",
            "required": True,
            "purpose": "Freeze lane ownership, public-safe outputs, and no-admission gates before either lane produces a postrun.",
            "training_allowed": False,
            "admitted_rows": 0,
            "must_emit": [
                "lane_contracts",
                "shared_stop_conditions",
                "dedupe_and_protected_split_gate_plan",
                "public_summary_guardrail_plan",
            ],
        },
        {
            "stage": "stage12437_open_swe_replay_executor_pilot_20_postrun",
            "lane": "open_swe_replay_executor_pilot_20",
            "required": True,
            "purpose": "Execute at most 20 private Open-SWE candidates and emit aggregate proof-slot counts only.",
            "training_allowed": False,
            "admitted_rows": 0,
            "must_emit": [
                "checkout_before_anchor_proof_count",
                "patch_application_proof_count",
                "same_verifier_before_after_proof_count",
                "causal_transition_proof_count",
                "state_after_anchor_count",
                "raw_leak_count_zero_guardrail",
            ],
        },
        {
            "stage": "stage12438_session_like_materializer_upgrade_postrun",
            "lane": "session_like_materializer_upgrade",
            "required": True,
            "purpose": "Upgrade Stage12316/12386 materialization seeds against the Level-3 control contract without admitting rows.",
            "training_allowed": False,
            "admitted_rows": 0,
            "must_emit": [
                "repo_family_recovered_count",
                "safe_command_result_recovered_count",
                "state_update_recovered_count",
                "stop_decision_recovered_count",
                "policy_label_review_queue_count",
                "manual_review_required_count",
            ],
        },
    ]


def pilot_and_ramp_floors(stage12434: dict[str, Any]) -> dict[str, Any]:
    floors = safe_dict(stage12434.get("pilot_and_ramp_floors"))
    if floors:
        return floors
    common = {
        "training_release_allowed_by_this_artifact": False,
        "admission_release_allowed_by_this_artifact": False,
        "failure_mode": "remain_fail_closed_and_emit_no_rows",
    }
    return {
        "pilot_20": {
            **common,
            "target_private_candidates_to_execute": 20,
            "minimum_same_verifier_before_after_proofs": 6,
            "minimum_patch_apply_proofs": 6,
            "minimum_checkout_before_anchor_proofs": 6,
            "minimum_causal_transition_proofs": 4,
            "minimum_state_transition_anchors": 8,
            "minimum_distinct_repositories": 4,
            "maximum_duplicate_cluster_share": 0.10,
        },
        "scale_500": {
            **common,
            "target_private_candidates_to_execute": 500,
            "minimum_same_verifier_before_after_proofs": 80,
            "minimum_patch_apply_proofs": 100,
            "minimum_checkout_before_anchor_proofs": 120,
            "minimum_causal_transition_proofs": 60,
            "minimum_state_transition_anchors": 150,
            "minimum_distinct_repositories": 25,
            "maximum_duplicate_cluster_share": 0.08,
        },
    }


def ranked_decision(session_counts: dict[str, Any], open_swe_counts: dict[str, Any]) -> list[dict[str, Any]]:
    session_blocked = (
        session_counts["stage12386_true_new_transition_rows_available_without_manual_review"] == 0
        and session_counts["stage12316_train_grade_after_policy_label_review"] == 0
    )
    open_swe_has_supply = open_swe_counts["metadata_candidate_supply_rows"] > 0
    open_swe_needs_execution = (
        open_swe_counts["proof_complete_candidates"] == 0
        and open_swe_counts["replay_attempted_count"] == 0
        and open_swe_counts["patch_apply_attempted_count"] == 0
        and open_swe_counts["verifier_execution_attempted_count"] == 0
    )
    return [
        {
            "rank": 1,
            "path": "parallel_two_lane_control",
            "decision": "selected_fail_closed",
            "why_ranked_here": (
                "The Open-SWE lane has large candidate supply but needs real proof-slot execution, while the "
                "session-like lane has useful materializer seeds but needs field recovery and review. Running both "
                "under one fail-closed controller reduces serial path risk without releasing admission."
            ),
            "open_swe_lane_enabled_for_private_pilot_20_request": open_swe_has_supply and open_swe_needs_execution,
            "session_like_lane_enabled_for_materializer_upgrade_request": session_blocked,
            "training_allowed_by_this_artifact": False,
            "admission_allowed_by_this_artifact": False,
            "required_first_control_stage": "stage12436_parallel_two_lane_control_request",
        },
        {
            "rank": 2,
            "path": "open_swe_replay_executor_pilot_20",
            "decision": "serial_fallback_if_parallel_control_is_not_available",
            "why_ranked_here": (
                "Stage12434 already selected the Open-SWE private replay pilot-20 as the strongest single next "
                "execution path because supply exists and the blocker is missing execution proof rather than source volume."
            ),
            "candidate_supply_rows": open_swe_counts["metadata_candidate_supply_rows"],
            "training_allowed_by_this_artifact": False,
            "admission_allowed_by_this_artifact": False,
        },
        {
            "rank": 3,
            "path": "session_like_materializer_upgrade",
            "decision": "parallel_lane_or_serial_fallback_after_open_swe_pilot_request",
            "why_ranked_here": (
                "Stage12386 points to materializer upgrade as necessary, but current session-like rows remain blocked "
                "by missing command result, state update, stop decision, verifier identity, and policy-label review."
            ),
            "records_audited": session_counts["stage12386_records_audited"],
            "training_allowed_by_this_artifact": False,
            "admission_allowed_by_this_artifact": False,
        },
    ]


def hard_blockers(session_counts: dict[str, Any], open_swe_counts: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "blocker": "session_like_rows_not_admission_grade",
            "lane": "session_like_materializer_upgrade",
            "count": session_counts["candidate_only_rows"]
            + session_counts["transition_local_incomplete_rows"]
            + session_counts["verifier_observation_support_rows"],
            "evidence": "Stage12386 candidate/incomplete/support classifications cannot be promoted without materializer upgrade and review.",
        },
        {
            "blocker": "session_like_level3_controls_are_exemplars_not_new_rows",
            "lane": "session_like_materializer_upgrade",
            "count": session_counts["level3_control_complete_rows"],
            "evidence": "Existing Level-3 control rows are controls, not new Stage12435 admissions.",
        },
        {
            "blocker": "open_swe_no_checkout_patch_verifier_execution",
            "lane": "open_swe_replay_executor_pilot_20",
            "count": 1,
            "evidence": "Stage12433/12434 show zero replay, checkout, patch-apply, verifier, and test execution attempts.",
        },
        {
            "blocker": "open_swe_zero_complete_proof_candidates",
            "lane": "open_swe_replay_executor_pilot_20",
            "count": open_swe_counts["private_dedupe_survivors"],
            "evidence": "Sampled Open-SWE rows have zero proof-complete, patch-trace, or Level-3 candidates after private structure inspection.",
        },
        {
            "blocker": "training_and_admission_must_remain_closed",
            "lane": "both",
            "count": 1,
            "evidence": "This artifact is reconciliation/control only and emits no rows.",
        },
    ]


def stop_conditions() -> list[str]:
    return [
        "any_public_raw_leak_count_nonzero",
        "any_public_overclaim_count_nonzero",
        "stage12435_or_successor_training_allowed_not_false",
        "stage12435_or_successor_admitted_rows_nonzero_before_explicit_admission_gate",
        "raw_locator_values_or_private_slot_values_escape_public_artifacts",
        "open_swe_executor_cannot_bind_checkout_before_anchor_to_same_source_lineage",
        "open_swe_executor_cannot_record_patch_apply_status_hash",
        "open_swe_executor_cannot_record_same_verifier_before_after_status_classes",
        "resolved_metadata_used_as_repair_success_shortcut",
        "pilot_20_has_zero_causal_transition_proofs",
        "session_like_materializer_cannot_recover_command_result_state_update_stop_decision",
        "session_like_observed_action_used_as_policy_gold_without_review",
        "dedupe_or_protected_split_overlap_gate_not_run",
        "single_repo_or_duplicate_cluster_exceeds_cap",
    ]


def scan_payload(payload: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    for key, expected in ZERO_COUNTERS.items():
        if payload.get(key) != expected:
            issues.append(f"zero_counter_mismatch:{key}")
    for key, expected in RAW_CONTENT_POLICY.items():
        if payload.get("raw_content_policy", {}).get(key) != expected:
            issues.append(f"raw_content_policy_mismatch:{key}")

    text = json.dumps(payload, sort_keys=True, indent=2)
    raw_leaks = sorted(set(match.group(0)[:80] for match in FORBIDDEN_TEXT_RE.finditer(text)))
    overclaims: list[str] = []
    for match in OVERCLAIM_RE.finditer(text):
        start = max(0, match.start() - 80)
        end = min(len(text), match.end() + 80)
        context = text[start:end]
        if not ALLOWED_OVERCLAIM_CONTEXT_RE.search(context):
            overclaims.append(match.group(0))
    issues.extend(f"raw_leak_pattern:{item}" for item in raw_leaks)
    issues.extend(f"overclaim_pattern:{item}" for item in sorted(set(overclaims)))
    return {
        "scan_passed": not issues,
        "issue_count": len(issues),
        "issues": issues,
        "raw_leak_count": len(raw_leaks),
        "overclaim_count": len(set(overclaims)),
        "zero_counter_keys_checked": sorted(ZERO_COUNTERS),
        "raw_content_policy_keys_checked": sorted(RAW_CONTENT_POLICY),
        "scan_scope": "stage12435_public_reconciliation_payload_no_private_rows",
    }


def build_artifact(inputs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    stage12316 = inputs["stage12316_session_like_joiner"]
    stage12386 = inputs["stage12386_session_like_gap_audit"]
    stage12433 = inputs["stage12433_open_swe_proof_slot_postrun"]
    stage12434 = inputs["stage12434_open_swe_adapter_decision"]
    session_counts = session_lane_counts(stage12316, stage12386)
    open_swe_counts = open_swe_lane_counts(stage12433, stage12434)
    decisions = ranked_decision(session_counts, open_swe_counts)
    blockers = hard_blockers(session_counts, open_swe_counts)
    floors = pilot_and_ramp_floors(stage12434)
    next_stages = required_next_stages()

    artifact = {
        "stage": STAGE,
        "record_type": "proof_slot_execution_path_reconciliation_v1",
        "decision": "fail_closed_select_parallel_two_lane_control",
        "ranked_decision": decisions,
        "ranked_decision_selected_path": decisions[0]["path"],
        "claim_boundary": (
            "Stage12435 reconciles next execution path only. It reads public-safe summaries, emits no private row "
            "material, performs no replay or materialization, admits no rows, and cannot be counted as training data."
        ),
        **ZERO_COUNTERS,
        "raw_content_policy": RAW_CONTENT_POLICY,
        "input_inventory": input_inventory(),
        "input_summary_hashes": {key: file_hash(path) for key, path in INPUTS.items()},
        "source_controls": source_controls(inputs),
        "lane_top_level_counts": {
            "session_like_materializer_upgrade": session_counts,
            "open_swe_replay_executor_pilot_20": open_swe_counts,
        },
        "top_level_counts": {
            "session_like_records_audited": session_counts["stage12386_records_audited"],
            "session_like_candidate_or_incomplete_or_support_rows": session_counts["candidate_only_rows"]
            + session_counts["transition_local_incomplete_rows"]
            + session_counts["verifier_observation_support_rows"],
            "session_like_level3_control_complete_rows": session_counts["level3_control_complete_rows"],
            "session_like_new_training_rows_emitted": 0,
            "open_swe_metadata_candidate_supply_rows": open_swe_counts["metadata_candidate_supply_rows"],
            "open_swe_private_sampled_rows": open_swe_counts["private_sampled_rows"],
            "open_swe_private_dedupe_survivors": open_swe_counts["private_dedupe_survivors"],
            "open_swe_proof_complete_candidates": open_swe_counts["proof_complete_candidates"],
            "open_swe_patch_trace_candidates": open_swe_counts["patch_trace_candidates"],
            "open_swe_level3_candidates_after_private_replay": open_swe_counts[
                "level3_candidates_after_private_replay"
            ],
            "open_swe_execution_attempts_total": open_swe_counts["replay_attempted_count"]
            + open_swe_counts["checkout_execution_attempted_count"]
            + open_swe_counts["patch_apply_attempted_count"]
            + open_swe_counts["verifier_execution_attempted_count"],
            "admitted_rows": 0,
            "training_allowed": False,
        },
        "required_next_stages": next_stages,
        "hard_blockers": blockers,
        "hard_blocker_counts": {item["blocker"]: item["count"] for item in blockers},
        "pilot_and_ramp_floors": floors,
        "stop_conditions": stop_conditions(),
        "promotion_gate_status": {
            "artifact_is_control_only": "PASS",
            "training_allowed_false": "PASS",
            "admission_allowed_false": "PASS",
            "no_rows_admitted": "PASS",
            "no_rows_emitted": "PASS",
            "stage12316_summary_present": "PASS" if bool(stage12316) else "MISSING_INPUT_FAIL_CLOSED",
            "stage12386_summary_present": "PASS" if bool(stage12386) else "MISSING_INPUT_FAIL_CLOSED",
            "stage12433_summary_present": "PASS" if bool(stage12433) else "MISSING_INPUT_FAIL_CLOSED",
            "stage12434_summary_present": "PASS" if bool(stage12434) else "MISSING_INPUT_FAIL_CLOSED",
            "next_path_selected": "PARALLEL_TWO_LANE_CONTROL",
            "serial_fallback_path": "OPEN_SWE_REPLAY_EXECUTOR_PILOT_20",
            "admission_release_allowed": "PASS_FALSE",
            "training_release_allowed": "PASS_FALSE",
        },
        "next_stage_recommendation": (
            "build_stage12436_parallel_two_lane_control_request; then run public-safe postrun summaries for "
            "open_swe_replay_executor_pilot_20 and session_like_materializer_upgrade as separate fail-closed lanes; "
            "if parallel execution is unavailable, run the Open-SWE pilot-20 request first and keep the session-like "
            "materializer upgrade queued."
        ),
    }
    guardrail = scan_payload(artifact)
    artifact["guardrail_scan"] = guardrail
    artifact["guardrail_scan_passed"] = guardrail["scan_passed"]
    artifact["raw_leak_count"] = guardrail["raw_leak_count"]
    artifact["overclaim_count"] = guardrail["overclaim_count"]
    artifact["summary_hash"] = stable_hash({k: v for k, v in artifact.items() if k != "summary_hash"})
    return artifact


def main() -> None:
    inputs = {key: read_json(path) for key, path in INPUTS.items()}
    artifact = build_artifact(inputs)
    write_json(OUT / f"{STAGE}.json", artifact)
    write_json(OUT / "lane_top_level_counts.json", artifact["lane_top_level_counts"])
    write_json(OUT / "ranked_decision.json", artifact["ranked_decision"])
    write_json(OUT / "required_next_stages.json", artifact["required_next_stages"])
    write_json(OUT / "hard_blockers.json", artifact["hard_blockers"])
    write_json(OUT / "pilot_and_ramp_floors.json", artifact["pilot_and_ramp_floors"])
    write_json(OUT / "stop_conditions.json", artifact["stop_conditions"])
    write_json(OUT / "guardrail_scan.json", artifact["guardrail_scan"])
    write_json(OUT / "summary.json", artifact)
    write_json(SUMMARY, artifact)
    print(json.dumps(artifact, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
