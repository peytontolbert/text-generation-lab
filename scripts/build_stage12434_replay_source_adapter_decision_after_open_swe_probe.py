#!/usr/bin/env python3
"""Stage12434 replay/source-adapter decision after Open-SWE probe.

This public control artifact decides the next concrete path after Stage12433:
Open-SWE private replay executor, Open-SWE locator-worklist builder, or an
alternative source adapter. It reads only public-safe summaries, emits no raw
private material, runs no replay, admits no rows, and keeps training closed.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12434_replay_source_adapter_decision_after_open_swe_probe"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

INPUTS = {
    "stage12406_source_expansion": ROOT / "runs/summaries/stage12406_transition_source_expansion_preflight.json",
    "stage12407_adapter_worklist": ROOT / "runs/summaries/stage12407_prioritized_adapter_materialization_worklist.json",
    "stage12425_adapter_feasibility": ROOT / "runs/summaries/stage12425_source_adapter_feasibility_miner.json",
    "stage12426_sakana_metadata": ROOT / "runs/summaries/stage12426_sakana_cuda_safe_metadata_profiler.json",
    "stage12427_open_swe_metadata": ROOT / "runs/summaries/stage12427_open_swe_safe_metadata_profiler.json",
    "stage12429_ramp_control": ROOT / "runs/summaries/stage12429_open_swe_scaling_ramp_control.json",
    "stage12433_open_swe_probe": ROOT / "runs/summaries/stage12433_open_swe_pilot_100_private_proof_slot_runner_postrun.json",
}

ZERO_COUNTERS: dict[str, bool | int] = {
    "training_allowed": False,
    "admission_allowed": False,
    "execution_allowed": False,
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
    r"(false|zero|none|not_|no_|blocked|fail_closed|candidate|proof_slot|"
    r"training_allowed|admission_allowed|admitted_rows|execution_allowed|"
    r"not_executed|attempted_count|requires|required|gate|floor|pilot|ramp)",
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


def safe_bool_false(value: Any) -> bool:
    return value is False


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


def summarize_source_controls(inputs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, payload in inputs.items():
        out[key] = {
            "stage_hash": stable_hash(payload.get("stage"), 16),
            "decision_hash": stable_hash(payload.get("decision"), 16),
            "guardrail_scan_passed": guardrail_clean(payload),
            "training_allowed": payload.get("training_allowed", False),
            "admission_allowed": payload.get("admission_allowed", False),
            "admitted_rows": safe_int(payload.get("admitted_rows")),
            "raw_leak_count": safe_int(payload.get("raw_leak_count")),
            "overclaim_count": safe_int(payload.get("overclaim_count")),
        }
    return out


def stage12433_current_counts(stage12433: dict[str, Any]) -> dict[str, Any]:
    proof_present = stage12433.get("proof_slot_present_counts")
    proof_recoverable = stage12433.get("proof_slot_recoverable_counts")
    proof_missing = stage12433.get("proof_slot_missing_counts")
    execution_attempts = stage12433.get("actual_execution_attempt_counts")
    return {
        "metadata_candidate_supply_rows": safe_int(stage12433.get("metadata_candidate_supply_rows")),
        "metadata_rows_observed_private": safe_int(stage12433.get("metadata_rows_observed_private")),
        "parquet_shard_count": safe_int(stage12433.get("parquet_shard_count")),
        "dataset_root_hit_count": safe_int(stage12433.get("dataset_root_hit_count")),
        "private_sampled_rows": safe_int(stage12433.get("private_sampled_rows")),
        "private_rows_inspected": safe_int(stage12433.get("private_rows_inspected")),
        "private_dedupe_survivors": safe_int(stage12433.get("private_dedupe_survivors")),
        "proof_complete_candidates": safe_int(stage12433.get("proof_complete_candidates")),
        "patch_trace_candidates": safe_int(stage12433.get("patch_trace_candidates")),
        "level3_candidates_after_private_replay": safe_int(stage12433.get("level3_candidates_after_private_replay")),
        "admitted_rows": safe_int(stage12433.get("admitted_rows")),
        "emitted_rows": safe_int(stage12433.get("emitted_rows")),
        "emitted_training_rows": safe_int(stage12433.get("emitted_training_rows")),
        "raw_leak_count": safe_int(stage12433.get("raw_leak_count")),
        "overclaim_count": safe_int(stage12433.get("overclaim_count")),
        "replay_attempted_count": safe_int(stage12433.get("replay_attempted_count")),
        "checkout_execution_attempted_count": safe_int(stage12433.get("checkout_execution_attempted_count")),
        "patch_apply_attempted_count": safe_int(stage12433.get("patch_apply_attempted_count")),
        "verifier_execution_attempted_count": safe_int(stage12433.get("verifier_execution_attempted_count")),
        "tests_run_count": safe_int(stage12433.get("tests_run_count")),
        "proof_slot_present_counts": proof_present if isinstance(proof_present, dict) else {},
        "proof_slot_recoverable_counts": proof_recoverable if isinstance(proof_recoverable, dict) else {},
        "proof_slot_missing_counts": proof_missing if isinstance(proof_missing, dict) else {},
        "actual_execution_attempt_counts": execution_attempts if isinstance(execution_attempts, dict) else {},
    }


def required_proof_slot_gates() -> dict[str, dict[str, Any]]:
    return {
        "checkout_before_anchor": {
            "required_before": "any_open_swe_replay_admission_or_level3_claim",
            "proof_source": "private_executor_record_with_same_source_checkout_anchor_hashes",
            "public_output_allowed": "aggregate_count_and_hash_only",
            "gate_status": "BLOCKED_BY_STAGE12433_ZERO_EXECUTION_PROOF",
        },
        "patch_application_proof": {
            "required_before": "patch_trace_candidate_or_repair_transition_claim",
            "proof_source": "private_patch_apply_log_redacted_to_status_hash_and_exit_class",
            "public_output_allowed": "aggregate_count_and_hash_only",
            "gate_status": "BLOCKED_BY_STAGE12433_NO_PATCH_APPLY_EXECUTION",
        },
        "same_verifier_before_after": {
            "required_before": "level3_candidate_after_private_replay",
            "proof_source": "same_verifier_identity_hash_with_before_and_after_status_classes",
            "public_output_allowed": "aggregate_count_and_hash_only",
            "gate_status": "BLOCKED_BY_STAGE12433_ZERO_SAME_VERIFIER_PROOF",
        },
        "causal_transition": {
            "required_before": "any_countable_repair_or_transition_support_row",
            "proof_source": "checkout_before_plus_patch_apply_plus_same_verifier_before_after",
            "public_output_allowed": "aggregate_count_and_hash_only",
            "gate_status": "BLOCKED_BY_MISSING_COMPONENT_PROOF_SLOTS",
        },
        "state_after": {
            "required_before": "state_transition_anchor_floor",
            "proof_source": "private_after_state_or_after_status_class_bound_to_same_source_lineage",
            "public_output_allowed": "aggregate_count_and_hash_only",
            "gate_status": "PARTIALLY_RECOVERABLE_BUT_NOT_PROOF_PRESENT",
        },
        "stop_continue": {
            "required_before": "policy_head_or_stop_continue_training_support",
            "proof_source": "public_safe_stop_or_continue_class_only",
            "public_output_allowed": "aggregate_count_and_hash_only",
            "gate_status": "PRESENT_IN_STAGE12433_BUT_NOT_SUFFICIENT_ALONE",
        },
    }


def pilot_and_ramp_floors() -> dict[str, dict[str, Any]]:
    common = {
        "training_release_allowed_by_this_artifact": False,
        "admission_release_allowed_by_this_artifact": False,
        "failure_mode": "remain_fail_closed_and_emit_no_rows",
    }
    return {
        "pilot_20": {
            **common,
            "target_private_candidates_to_execute": 20,
            "purpose": "executor safety pilot only, not a scale floor and not an admission floor",
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
            "purpose": "first material ramp after a clean pilot-20 executor postrun",
            "minimum_same_verifier_before_after_proofs": 80,
            "minimum_patch_apply_proofs": 100,
            "minimum_checkout_before_anchor_proofs": 120,
            "minimum_causal_transition_proofs": 60,
            "minimum_state_transition_anchors": 150,
            "minimum_distinct_repositories": 25,
            "maximum_duplicate_cluster_share": 0.08,
        },
        "ramp_1k": {
            **common,
            "target_private_candidates_to_execute": 1000,
            "purpose": "higher confidence ramp after clean scale-500 postrun",
            "minimum_same_verifier_before_after_proofs": 180,
            "minimum_patch_apply_proofs": 220,
            "minimum_checkout_before_anchor_proofs": 250,
            "minimum_causal_transition_proofs": 140,
            "minimum_state_transition_anchors": 350,
            "minimum_distinct_repositories": 50,
            "maximum_duplicate_cluster_share": 0.06,
        },
        "scale_5k": {
            **common,
            "target_private_candidates_to_execute": 5000,
            "purpose": "large ramp only after 1k proof floors and caps pass",
            "minimum_same_verifier_before_after_proofs": 1000,
            "minimum_patch_apply_proofs": 1250,
            "minimum_checkout_before_anchor_proofs": 1500,
            "minimum_causal_transition_proofs": 800,
            "minimum_state_transition_anchors": 1800,
            "minimum_distinct_repositories": 150,
            "maximum_duplicate_cluster_share": 0.04,
        },
    }


def ranked_next_adapter_options(
    stage12433: dict[str, Any],
    stage12425: dict[str, Any],
    stage12426: dict[str, Any],
    stage12427: dict[str, Any],
) -> list[dict[str, Any]]:
    current = stage12433_current_counts(stage12433)
    metadata_supply = current["metadata_candidate_supply_rows"] or safe_int(stage12427.get("candidate_count"))
    sakana_supply = safe_int(stage12426.get("candidate_count"))
    stage12425_rankings = stage12425.get("ranked_adapter_feasibility")
    ranking_hash = stable_hash(stage12425_rankings if isinstance(stage12425_rankings, list) else [], 24)
    open_swe_ready = (
        safe_bool_false(stage12433.get("training_allowed"))
        and safe_bool_false(stage12433.get("admission_allowed"))
        and stage12433.get("guardrail_scan_passed") is True
        and safe_int(stage12433.get("raw_leak_count")) == 0
        and safe_int(stage12433.get("overclaim_count")) == 0
        and safe_int(stage12433.get("level3_candidates_after_private_replay")) == 0
    )
    return [
        {
            "rank": 1,
            "adapter_option": "open_swe_private_replay_executor_pilot_20",
            "decision": "recommended_next_if_private_executor_can_record_required_proof_slots",
            "why_ranked_here": "largest safe metadata supply and Stage12433 already proved the blocker is missing execution proof rather than candidate supply",
            "candidate_supply_rows": metadata_supply,
            "current_stage12433_level3_candidates": current["level3_candidates_after_private_replay"],
            "current_stage12433_patch_trace_candidates": current["patch_trace_candidates"],
            "processing_allowed_by_this_artifact": False,
            "admission_allowed_by_this_artifact": False,
            "training_allowed_by_this_artifact": False,
            "required_before_start": [
                "private_executor_workdir_isolation",
                "raw_locator_values_never_written_to_public_artifacts",
                "same_source_checkout_before_anchor_capture",
                "patch_apply_status_capture",
                "same_verifier_identity_before_after_capture",
                "public_summary_only_after_run",
            ],
            "open_swe_preconditions_from_stage12433": "PASS_FOR_CONTROL_ONLY" if open_swe_ready else "BLOCKED",
        },
        {
            "rank": 2,
            "adapter_option": "open_swe_locator_worklist_builder",
            "decision": "fallback_if_executor_cannot_safely_bind_checkout_and_verifier_slots",
            "why_ranked_here": "use only to prepare private locator hashes and missing-slot buckets; it must not be counted as replay or training evidence",
            "candidate_supply_rows": metadata_supply,
            "processing_allowed_by_this_artifact": False,
            "admission_allowed_by_this_artifact": False,
            "training_allowed_by_this_artifact": False,
            "required_before_start": [
                "hash_only_locator_plan",
                "no_raw_paths_urls_or_repo_names_in_public_output",
                "dedupe_key_hashes_against_existing_countable_ledgers",
                "handoff_to_private_executor_before_any_proof_claim",
            ],
        },
        {
            "rank": 3,
            "adapter_option": "sakana_cuda_safe_private_verifier_observation_adapter",
            "decision": "alternative_if_open_swe_replay_remains_blocked",
            "why_ranked_here": "Stage12425 ranked it first for feasibility, but its best use is verifier-observation support rather than patch-trace or Level-3 repair proof",
            "candidate_supply_rows": sakana_supply,
            "processing_allowed_by_this_artifact": False,
            "admission_allowed_by_this_artifact": False,
            "training_allowed_by_this_artifact": False,
            "source_feasibility_ranking_hash": ranking_hash,
            "required_before_start": [
                "authoritative_status_or_local_rerun",
                "same_source_lineage_hashes",
                "dedupe_against_existing_countable_ledgers",
                "do_not_claim_patch_trace_or_fail_to_pass_repair",
            ],
        },
        {
            "rank": 4,
            "adapter_option": "external_benchmark_patch_log_or_local_repo_task_adapter",
            "decision": "secondary_alternative_for_lower_volume_stronger_lineage",
            "why_ranked_here": "may provide stronger before-after lineage than Open-SWE metadata, but expected volume is lower and still requires execution or authoritative verifier proof",
            "candidate_supply_rows": 0,
            "processing_allowed_by_this_artifact": False,
            "admission_allowed_by_this_artifact": False,
            "training_allowed_by_this_artifact": False,
            "required_before_start": [
                "same_verifier_before_after",
                "patch_lineage_hash",
                "repo_lineage_hash",
                "protected_split_overlap_zero",
                "public_summary_guardrail_clean",
            ],
        },
    ]


def source_preconditions(inputs: dict[str, dict[str, Any]]) -> dict[str, bool]:
    checks: dict[str, bool] = {}
    for key in INPUTS:
        payload = inputs.get(key, {})
        checks[f"{key}_present"] = bool(payload)
        checks[f"{key}_guardrail_clean"] = guardrail_clean(payload)
        checks[f"{key}_training_allowed_false"] = safe_bool_false(payload.get("training_allowed"))
        checks[f"{key}_admitted_rows_zero"] = safe_int(payload.get("admitted_rows")) == 0
        checks[f"{key}_raw_leak_zero"] = safe_int(payload.get("raw_leak_count")) == 0
    stage12433 = inputs.get("stage12433_open_swe_probe", {})
    checks["stage12433_no_replay_execution_attempted"] = safe_int(stage12433.get("replay_attempted_count")) == 0
    checks["stage12433_no_patch_apply_attempted"] = safe_int(stage12433.get("patch_apply_attempted_count")) == 0
    checks["stage12433_no_verifier_execution_attempted"] = safe_int(stage12433.get("verifier_execution_attempted_count")) == 0
    checks["stage12433_no_rows_admitted"] = safe_int(stage12433.get("admitted_rows")) == 0
    return checks


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
        "scan_scope": "stage12434_public_control_payload_no_private_rows",
    }


def build_artifact(inputs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    stage12433 = inputs["stage12433_open_swe_probe"]
    stage12425 = inputs["stage12425_adapter_feasibility"]
    stage12426 = inputs["stage12426_sakana_metadata"]
    stage12427 = inputs["stage12427_open_swe_metadata"]
    current = stage12433_current_counts(stage12433)
    proof_gates = required_proof_slot_gates()
    floors = pilot_and_ramp_floors()
    ranked = ranked_next_adapter_options(stage12433, stage12425, stage12426, stage12427)
    preconditions = source_preconditions(inputs)
    blocker_counts = {
        "stage12433_zero_level3_candidates_after_private_replay": 1,
        "stage12433_zero_patch_trace_candidates": 1,
        "stage12433_zero_proof_complete_candidates": 1,
        "stage12433_no_checkout_execution": 1,
        "stage12433_no_patch_apply_execution": 1,
        "stage12433_no_verifier_execution": 1,
        "admission_gate_forced_closed": 1,
        "training_gate_forced_closed": 1,
    }
    artifact = {
        "stage": STAGE,
        "record_type": "replay_source_adapter_decision_after_open_swe_probe_v1",
        "decision": "fail_closed_recommend_open_swe_private_replay_executor_pilot_20_before_locator_or_alternative_adapter",
        "claim_boundary": (
            "Stage12434 is a control decision only. It reads public-safe summaries, emits no private row material, "
            "executes no replay, admits no rows, and cannot be counted as training data."
        ),
        **ZERO_COUNTERS,
        "raw_content_policy": RAW_CONTENT_POLICY,
        "input_inventory": input_inventory(),
        "input_summary_hashes": {key: file_hash(path) for key, path in INPUTS.items()},
        "source_preconditions": preconditions,
        "source_controls": summarize_source_controls(inputs),
        "current_counts_from_stage12433": current,
        "current_stage12433_counts": current,
        "metadata_candidate_supply_rows": current["metadata_candidate_supply_rows"],
        "private_sampled_rows": current["private_sampled_rows"],
        "private_dedupe_survivors": current["private_dedupe_survivors"],
        "level3_candidates_after_private_replay": current["level3_candidates_after_private_replay"],
        "patch_trace_candidates": current["patch_trace_candidates"],
        "proof_complete_candidates": current["proof_complete_candidates"],
        "ranked_next_adapter_options": ranked,
        "required_proof_slot_gates": proof_gates,
        "pilot_and_ramp_floors": floors,
        "proof_floor_policy": {
            "pilot_20_is_pilot_only": True,
            "pilot_20_is_not_training_or_admission_floor": True,
            "scale_500_ramp_1k_scale_5k_require_much_higher_floors": True,
            "resolved_status_alone_is_never_repair_proof": True,
            "locator_worklists_are_never_countable_rows": True,
        },
        "stop_conditions": [
            "any_public_raw_leak_count_nonzero",
            "any_public_overclaim_count_nonzero",
            "stage12433_or_successor_training_allowed_not_false",
            "stage12433_or_successor_admitted_rows_nonzero_before_named_admission_gate",
            "raw_locator_values_or_private_slot_values_escape_public_artifacts",
            "executor_cannot_bind_checkout_before_anchor_to_same_source_lineage",
            "executor_cannot_record_same_verifier_before_after_status_classes",
            "patch_apply_status_or_patch_lineage_hash_missing",
            "resolved_metadata_used_as_repair_success_shortcut",
            "pilot_20_has_zero_causal_transition_proofs",
            "scale_500_or_1k_or_5k_attempted_before_prior_clean_public_postrun_summary",
            "dedupe_or_protected_split_overlap_gate_not_run",
            "single_repo_or_duplicate_cluster_exceeds_cap",
        ],
        "blocked_reason_counts": blocker_counts,
        "promotion_gate_status": {
            "artifact_is_control_only": "PASS",
            "training_allowed_false": "PASS",
            "admission_allowed_false": "PASS",
            "no_rows_admitted": "PASS",
            "no_rows_emitted": "PASS",
            "stage12433_guardrail_clean": "PASS" if stage12433.get("guardrail_scan_passed") is True else "BLOCKED",
            "stage12433_no_execution": "PASS"
            if (
                current["replay_attempted_count"] == 0
                and current["patch_apply_attempted_count"] == 0
                and current["verifier_execution_attempted_count"] == 0
            )
            else "BLOCKED",
            "next_path_selected": "OPEN_SWE_PRIVATE_REPLAY_EXECUTOR_PILOT_20",
            "admission_release_allowed": "PASS_FALSE",
            "training_release_allowed": "PASS_FALSE",
        },
        "next_stage_recommendation": (
            "build_stage12435_open_swe_private_replay_executor_pilot_20_request_then_public_safe_postrun_summary; "
            "use_locator_worklist_only_if_executor_prerequisite_binding_is_blocked; pivot_to_sakana_cuda_or_external_patch_log_adapter_if_open_swe_executor_remains_blocked"
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
    write_json(OUT / "ranked_next_adapter_options.json", artifact["ranked_next_adapter_options"])
    write_json(OUT / "required_proof_slot_gates.json", artifact["required_proof_slot_gates"])
    write_json(OUT / "pilot_and_ramp_floors.json", artifact["pilot_and_ramp_floors"])
    write_json(OUT / "guardrail_scan.json", artifact["guardrail_scan"])
    write_json(OUT / "summary.json", artifact)
    write_json(SUMMARY, artifact)
    print(json.dumps(artifact, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
