#!/usr/bin/env python3
"""Stage12436 fail-closed parallel two-lane control request.

This stage reads only the public-safe Stage12435 reconciliation artifact,
canonicalizes the next-lane names, and emits public accounting contracts. It
does not run private replay, inspect private rows, admit rows, or emit training
rows.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12436_parallel_two_lane_control_request"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12435_PRIMARY = (
    ROOT
    / "runs/local/artifacts/stage12435_proof_slot_execution_path_reconciliation"
    / "stage12435_proof_slot_execution_path_reconciliation.json"
)
STAGE12435_FALLBACK = ROOT / "runs/summaries/stage12435_proof_slot_execution_path_reconciliation.json"

CANONICAL_OPEN_SWE_LANE = "open_swe_private_replay_executor_pilot_20"
STAGE12435_OPEN_SWE_LANE_KEY = "open_swe_replay_executor_pilot_20"
SESSION_LIKE_LANE = "session_like_materializer_upgrade"

NEXT_LANES = [CANONICAL_OPEN_SWE_LANE, SESSION_LIKE_LANE]
LANE_ALIAS_MAP = {
    STAGE12435_OPEN_SWE_LANE_KEY: CANONICAL_OPEN_SWE_LANE,
    CANONICAL_OPEN_SWE_LANE: CANONICAL_OPEN_SWE_LANE,
    SESSION_LIKE_LANE: SESSION_LIKE_LANE,
}
EXPECTED_STAGE12435_LANE_KEYS = [STAGE12435_OPEN_SWE_LANE_KEY, SESSION_LIKE_LANE]

REQUIRED_OPEN_SWE_COUNTERS = {
    "metadata_candidate_supply_rows": 207489,
    "private_sampled_rows": 100,
    "private_dedupe_survivors": 100,
    "proof_complete_candidates": 0,
    "level3_candidates_after_private_replay": 0,
    "patch_trace_candidates": 0,
}
REQUIRED_SESSION_LIKE_COUNTERS = {
    "stage12386_records_audited": 4374,
    "level3_control_complete_rows": 149,
    "candidate_only_rows": 4034,
    "transition_local_incomplete_rows": 185,
    "verifier_observation_support_rows": 6,
    "stage12386_new_training_rows_emitted": 0,
}

ZERO_COUNTERS: dict[str, bool | int] = {
    "training_allowed": False,
    "admission_allowed": False,
    "execution_allowed": False,
    "admitted_rows": 0,
    "emitted_training_rows": 0,
    "countable_new_rows": 0,
    "emitted_rows": 0,
    "new_training_rows_emitted": 0,
    "countable_rows": 0,
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
    "raw_leak_count": 0,
    "overclaim_count": 0,
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
    "urls_emitted": False,
    "source_text_emitted": False,
    "row_values_emitted": False,
    "locator_values_emitted": False,
    "schema_field_names_emitted": False,
    "private_slot_values_emitted": False,
    "training_rows_emitted": False,
    "model_facing_output_emitted": False,
}

RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:Traceback \(most recent call last\)|stdout|stderr|stack trace|"
    r"terminal output|command output|pytest |npm |pip |git clone|git apply|curl |"
    r"bash -|sh -|python -c)\b",
    re.IGNORECASE | re.MULTILINE,
)

OVERCLAIM_OR_ADMISSION_RE = re.compile(
    r"\b(?:admission|admitted|training row|training rows|trainable|"
    r"execution succeeded|replay succeeded|verified repair|closed loop|"
    r"level3 complete|causal proof|patch applied|tests passed)\b",
    re.IGNORECASE,
)

ALLOWED_FAIL_CLOSED_CONTEXT_RE = re.compile(
    r"(false|zero|none|no_|not_|blocked|fail_closed|control|contract|"
    r"guardrail|counter|denominator|floor|required|candidate|pilot|postrun|"
    r"allowed_by_this_artifact|training_allowed|admission_allowed|admitted_rows|"
    r"emitted_training_rows|countable_new_rows|release_allowed|must_remain_closed|"
    r"not_observed_action_imitation|policy_label|explicit_gate)",
    re.IGNORECASE,
)


class SchemaIssueCollector:
    def __init__(self) -> None:
        self.issues: list[str] = []

    def add(self, issue: str) -> None:
        self.issues.append(issue)

    def required_int(self, lane: str, payload: dict[str, Any], key: str, expected: int | None = None) -> int | None:
        if key not in payload:
            self.add(f"missing_required_counter:{lane}.{key}")
            return None
        value = payload.get(key)
        if value is None:
            self.add(f"null_required_counter:{lane}.{key}")
            return None
        if isinstance(value, bool) or not isinstance(value, int):
            self.add(f"non_integer_required_counter:{lane}.{key}")
            return None
        if expected is not None and value != expected:
            self.add(f"unexpected_required_counter_value:{lane}.{key}:expected_{expected}:actual_{value}")
        return value


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
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def source_guardrail_status(payload: dict[str, Any]) -> str:
    if not payload:
        return "failed"
    if payload.get("guardrail_scan_passed") is True:
        return "passed"
    guardrail = payload.get("guardrail_scan")
    if isinstance(guardrail, dict) and guardrail.get("scan_passed") is True:
        return "passed"
    if "guardrail_scan_passed" in payload or isinstance(guardrail, dict):
        return "failed"
    return "legacy_no_scan_fail_closed"


def stage12435_input() -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    source_path = STAGE12435_PRIMARY if STAGE12435_PRIMARY.exists() else STAGE12435_FALLBACK
    payload = read_json(source_path)
    status = source_guardrail_status(payload)
    return payload, {
        "stage12435_public_artifact_present": bool(payload),
        "stage12435_public_artifact_sha256_24": file_hash(source_path),
        "stage12435_source_label": "artifact" if source_path == STAGE12435_PRIMARY else "summary",
    }, {"stage12435_proof_slot_execution_path_reconciliation": status}


def carried_lane_top_level_counts(stage12435: dict[str, Any], schema: SchemaIssueCollector) -> dict[str, Any]:
    source_counts = safe_dict(stage12435.get("lane_top_level_counts"))
    carried: dict[str, Any] = {}
    for key in EXPECTED_STAGE12435_LANE_KEYS:
        value = source_counts.get(key)
        if not isinstance(value, dict):
            schema.add(f"missing_required_lane_top_level_counts_key:{key}")
            carried[key] = None
        else:
            carried[key] = value
    for bad_key in ("session_like", "open_swe"):
        if bad_key in source_counts:
            schema.add(f"forbidden_generic_lane_top_level_counts_key:{bad_key}")
    return carried


def normalized_top_level_counters(lane_counts: dict[str, Any], schema: SchemaIssueCollector) -> dict[str, int | None]:
    open_swe = safe_dict(lane_counts.get(STAGE12435_OPEN_SWE_LANE_KEY))
    session_like = safe_dict(lane_counts.get(SESSION_LIKE_LANE))
    values: dict[str, int | None] = {
        "allowed_lane_count": len(NEXT_LANES),
        "open_swe_requested_private_candidate_count": 20,
    }
    for key, expected in REQUIRED_OPEN_SWE_COUNTERS.items():
        values[f"open_swe_{key}"] = schema.required_int(CANONICAL_OPEN_SWE_LANE, open_swe, key, expected)
    values["session_like_records_audited"] = schema.required_int(
        SESSION_LIKE_LANE, session_like, "stage12386_records_audited", 4374
    )
    for key, expected in REQUIRED_SESSION_LIKE_COUNTERS.items():
        if key == "stage12386_records_audited":
            continue
        normalized_key = (
            "session_like_new_training_rows_emitted"
            if key == "stage12386_new_training_rows_emitted"
            else f"session_like_{key}"
        )
        values[normalized_key] = schema.required_int(SESSION_LIKE_LANE, session_like, key, expected)
    return values


def open_swe_lane_contract(normalized: dict[str, int | None]) -> dict[str, Any]:
    return {
        "lane": CANONICAL_OPEN_SWE_LANE,
        "aliases": [STAGE12435_OPEN_SWE_LANE_KEY],
        "source_count_key_carried_from_stage12435": STAGE12435_OPEN_SWE_LANE_KEY,
        "next_stage": "stage12437_open_swe_private_pilot_20_postrun",
        "stage12437_contract": "private_pilot_20_postrun",
        "stage12436_execution_allowed": False,
        "stage12436_private_replay_executed": False,
        "stage12436_private_rows_inspected": 0,
        "stage12436_training_allowed": False,
        "stage12436_admission_allowed": False,
        "stage12436_admitted_rows": 0,
        "stage12437_candidate_execution_cap": 20,
        "control_exemplar_rows": 0,
        "trainable_level3_rows": 0,
        "public_output_mode": "aggregate_counts_only",
        "raw_private_material_public_output_allowed": False,
        "carried_public_denominators": {
            "metadata_candidate_supply_rows": normalized["open_swe_metadata_candidate_supply_rows"],
            "private_sampled_rows": normalized["open_swe_private_sampled_rows"],
            "private_dedupe_survivors": normalized["open_swe_private_dedupe_survivors"],
        },
        "public_output_allowed_fields": [
            "candidate_denominator_total",
            "candidate_denominator_after_dedupe",
            "executed_candidate_denominator",
            "checkout_before_anchor_proof_count",
            "patch_application_proof_count",
            "same_verifier_before_after_proof_count",
            "causal_transition_proof_count",
            "state_after_anchor_count",
            "distinct_repo_count",
            "duplicate_cluster_max_share",
            "raw_leak_count",
            "overclaim_count",
        ],
        "pilot_20_floors": {
            "purpose": "executor_safety_pilot_only_not_admission_goal_not_scale_goal",
            "admission_or_scale_goal": False,
            "maximum_candidates_to_execute": 20,
            "minimum_checkout_before_anchor_proofs": 6,
            "minimum_patch_apply_proofs": 6,
            "minimum_same_verifier_before_after_proofs": 6,
            "minimum_causal_transition_proofs": 4,
            "minimum_state_after_anchors": 8,
            "minimum_distinct_repositories": 4,
            "maximum_duplicate_cluster_share": 0.10,
        },
        "release_policy": {
            "training_allowed_after_postrun": False,
            "admission_allowed_after_postrun": False,
            "admission_release_requires_future_explicit_gate": True,
        },
    }


def session_like_lane_contract(normalized: dict[str, int | None]) -> dict[str, Any]:
    return {
        "lane": SESSION_LIKE_LANE,
        "aliases": [],
        "source_count_key_carried_from_stage12435": SESSION_LIKE_LANE,
        "next_stage": "stage12438_session_like_materializer_upgrade_postrun",
        "stage12438_contract": "materializer_upgrade_postrun",
        "stage12436_execution_allowed": False,
        "stage12436_materialization_executed": False,
        "stage12436_training_allowed": False,
        "stage12436_admission_allowed": False,
        "stage12436_admitted_rows": 0,
        "raw_model_facing_output_allowed": False,
        "control_exemplar_rows": normalized["session_like_level3_control_complete_rows"],
        "trainable_level3_rows": 0,
        "required_recovered_fields": [
            "root_id",
            "repo_family",
            "language",
            "safe_command_result_class",
            "state_update",
            "stop_decision",
            "verifier_transition",
            "semantic_rule_id",
            "transition_function_key",
        ],
        "policy_label_constraints": {
            "observed_action_imitation_allowed": False,
            "policy_labels_must_be_reviewed_semantic_transitions": True,
            "policy_labels_must_not_be_observed_action_imitation": True,
        },
        "public_output_allowed_fields": [
            "candidate_denominator_total",
            "candidate_denominator_with_root_id",
            "candidate_denominator_with_repo_family",
            "candidate_denominator_with_language",
            "safe_command_result_class_recovered_count",
            "state_update_recovered_count",
            "stop_decision_recovered_count",
            "verifier_transition_recovered_count",
            "semantic_rule_id_recovered_count",
            "transition_function_key_recovered_count",
            "policy_label_review_queue_count",
            "observed_action_imitation_policy_label_count",
            "raw_leak_count",
            "overclaim_count",
        ],
        "release_policy": {
            "training_allowed_after_postrun": False,
            "admission_allowed_after_postrun": False,
            "admission_release_requires_future_explicit_gate": True,
        },
    }


def shared_stop_conditions() -> list[str]:
    return [
        "any_public_raw_leak_count_nonzero",
        "any_public_overclaim_or_unqualified_admission_language_nonzero",
        "stage12436_training_allowed_not_false",
        "stage12436_admission_allowed_not_false",
        "stage12436_execution_allowed_not_false",
        "stage12436_admitted_rows_nonzero",
        "stage12436_emitted_training_rows_nonzero",
        "private_replay_attempted_by_stage12436",
        "private_rows_inspected_or_copied_by_stage12436",
        "raw_url_path_diff_command_or_output_like_text_in_public_artifact",
        "raw_urls_emitted_or_urls_emitted_alias_not_false",
        "generic_or_null_lane_top_level_count_key_emitted",
        "required_stage12435_lane_count_key_missing",
        "parser_critical_counter_missing_null_or_non_integer",
        "source_guardrail_status_not_passed",
        "open_swe_public_output_contains_nonaggregate_private_material",
        "open_swe_stage12437_executes_more_than_20_candidates",
        "open_swe_stage12437_duplicate_cluster_max_share_above_0_10",
        "open_swe_stage12437_public_denominator_counters_missing",
        "session_like_stage12438_raw_model_facing_output_emitted",
        "session_like_stage12438_required_recovered_field_counter_missing",
        "session_like_policy_label_uses_observed_action_imitation",
        "future_postrun_reports_nonzero_admission_without_explicit_gate",
    ]


def required_public_postrun_accounting_tables() -> dict[str, Any]:
    zero_admission = {
        "training_allowed": False,
        "admission_allowed": False,
        "admitted_rows": 0,
        "emitted_training_rows": 0,
        "countable_new_rows": 0,
    }
    return {
        "stage12437_open_swe_private_pilot_20_postrun": {
            "lane": CANONICAL_OPEN_SWE_LANE,
            "zero_admission_counters": zero_admission,
            "denominator_counters_required": [
                "candidate_denominator_total",
                "candidate_denominator_after_dedupe",
                "selected_candidate_denominator",
                "executed_candidate_denominator",
                "postrun_public_summary_denominator",
            ],
            "proof_floor_numerators_required": [
                "checkout_before_anchor_proof_count",
                "patch_application_proof_count",
                "same_verifier_before_after_proof_count",
                "causal_transition_proof_count",
                "state_after_anchor_count",
                "distinct_repo_count",
            ],
            "dedupe_and_diversity_counters_required": [
                "duplicate_cluster_count",
                "duplicate_cluster_max_share",
                "repo_family_count",
                "distinct_repo_count",
            ],
            "raw_leak_and_claim_counters_required": ["raw_leak_count", "overclaim_count"],
        },
        "stage12438_session_like_materializer_upgrade_postrun": {
            "lane": SESSION_LIKE_LANE,
            "zero_admission_counters": zero_admission,
            "denominator_counters_required": [
                "candidate_denominator_total",
                "candidate_denominator_with_root_id",
                "candidate_denominator_with_repo_family",
                "candidate_denominator_with_language",
                "candidate_denominator_after_policy_label_filter",
                "postrun_public_summary_denominator",
            ],
            "recovered_field_counters_required": [
                "root_id_recovered_count",
                "repo_family_recovered_count",
                "language_recovered_count",
                "safe_command_result_class_recovered_count",
                "state_update_recovered_count",
                "stop_decision_recovered_count",
                "verifier_transition_recovered_count",
                "semantic_rule_id_recovered_count",
                "transition_function_key_recovered_count",
            ],
            "policy_label_counters_required": [
                "policy_label_review_queue_count",
                "observed_action_imitation_policy_label_count",
                "policy_label_not_observed_action_imitation_count",
                "manual_review_required_count",
            ],
            "raw_leak_and_claim_counters_required": ["raw_leak_count", "overclaim_count"],
        },
    }


def pilot_and_ramp_floors(stage12435: dict[str, Any]) -> dict[str, Any]:
    floors = safe_dict(stage12435.get("pilot_and_ramp_floors"))
    pilot_20 = {
        "purpose": "executor_safety_pilot_only_not_admission_goal_not_scale_goal",
        "admission_or_scale_goal": False,
        "target_private_candidates_to_execute": 20,
        "maximum_candidates_to_execute": 20,
        "minimum_checkout_before_anchor_proofs": 6,
        "minimum_patch_apply_proofs": 6,
        "minimum_same_verifier_before_after_proofs": 6,
        "minimum_causal_transition_proofs": 4,
        "minimum_state_after_anchors": 8,
        "minimum_state_transition_anchors": 8,
        "minimum_distinct_repositories": 4,
        "maximum_duplicate_cluster_share": 0.10,
        "training_release_allowed_by_this_artifact": False,
        "admission_release_allowed_by_this_artifact": False,
        "failure_mode": "remain_fail_closed_and_emit_no_rows",
    }
    merged = dict(floors)
    merged["pilot_20"] = {**safe_dict(floors.get("pilot_20")), **pilot_20}
    return merged


def public_denominator_snapshot(normalized: dict[str, int | None]) -> dict[str, Any]:
    return {
        CANONICAL_OPEN_SWE_LANE: {
            "metadata_candidate_supply_rows": normalized["open_swe_metadata_candidate_supply_rows"],
            "private_sampled_rows_from_stage12435_public_summary": normalized["open_swe_private_sampled_rows"],
            "private_dedupe_survivors_from_stage12435_public_summary": normalized[
                "open_swe_private_dedupe_survivors"
            ],
            "stage12436_executed_candidate_denominator": 0,
            "stage12436_admitted_rows": 0,
        },
        SESSION_LIKE_LANE: {
            "records_audited_from_stage12435_public_summary": normalized["session_like_records_audited"],
            "candidate_only_rows_from_stage12435_public_summary": normalized["session_like_candidate_only_rows"],
            "transition_local_incomplete_rows_from_stage12435_public_summary": normalized[
                "session_like_transition_local_incomplete_rows"
            ],
            "verifier_observation_support_rows_from_stage12435_public_summary": normalized[
                "session_like_verifier_observation_support_rows"
            ],
            "control_exemplar_rows": normalized["session_like_level3_control_complete_rows"],
            "trainable_level3_rows": 0,
            "stage12436_materialized_row_denominator": 0,
            "stage12436_admitted_rows": 0,
        },
    }


def validate_lane_keys(lane_counts: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    for key in EXPECTED_STAGE12435_LANE_KEYS:
        if key not in lane_counts:
            issues.append(f"missing_required_lane_top_level_counts_key:{key}")
        if lane_counts.get(key) is None:
            issues.append(f"null_lane_top_level_counts_key:{key}")
        elif not isinstance(lane_counts.get(key), dict):
            issues.append(f"lane_top_level_counts_key_not_object:{key}")
    for bad_key in ("session_like", "open_swe", CANONICAL_OPEN_SWE_LANE):
        if bad_key in lane_counts:
            issues.append(f"forbidden_generic_or_noncarried_lane_top_level_counts_key:{bad_key}")
    return issues


def public_artifact_manifest() -> list[dict[str, Any]]:
    names = [
        f"{STAGE}.json",
        "summary.json",
        "lane_top_level_counts.json",
        "open_swe_lane_contract.json",
        "session_like_lane_contract.json",
        "shared_stop_conditions.json",
        "required_public_postrun_accounting_tables.json",
        "pilot_and_ramp_floors.json",
        "guardrail_scan.json",
    ]
    return [
        {
            "artifact_file": name,
            "public_safe": True,
            "raw_leak_count": 0,
            "overclaim_count": 0,
            "raw_urls_emitted": False,
            "urls_emitted": False,
        }
        for name in names
    ]


def scan_payload(payload: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    for key, expected in ZERO_COUNTERS.items():
        if payload.get(key) != expected:
            issues.append(f"zero_counter_mismatch:{key}")
    raw_policy = safe_dict(payload.get("raw_content_policy"))
    for key, expected in RAW_CONTENT_POLICY.items():
        if raw_policy.get(key) != expected:
            issues.append(f"raw_content_policy_mismatch:{key}")
    if raw_policy.get("raw_urls_emitted") is not False:
        issues.append("raw_urls_emitted_alias_not_false")
    if "urls_emitted" in raw_policy and raw_policy.get("urls_emitted") is not False:
        issues.append("urls_emitted_alias_not_false")

    issues.extend(validate_lane_keys(safe_dict(payload.get("lane_top_level_counts"))))
    issues.extend(payload.get("schema_errors", []))

    source_statuses = safe_dict(payload.get("source_guardrail_statuses"))
    for label, status in source_statuses.items():
        if status not in {"passed", "failed", "legacy_no_scan_fail_closed"}:
            issues.append(f"invalid_source_guardrail_status:{label}")
        if status != "passed":
            issues.append(f"source_guardrail_status_not_passed:{label}:{status}")

    for item in payload.get("public_artifact_manifest", []):
        if not isinstance(item, dict):
            issues.append("public_artifact_manifest_item_not_object")
            continue
        if item.get("raw_leak_count") != 0:
            issues.append(f"public_artifact_raw_leak_count_nonzero:{item.get('artifact_file')}")
        if item.get("overclaim_count") != 0:
            issues.append(f"public_artifact_overclaim_count_nonzero:{item.get('artifact_file')}")
        if item.get("raw_urls_emitted") is not False:
            issues.append(f"public_artifact_raw_urls_emitted_not_false:{item.get('artifact_file')}")
        if item.get("urls_emitted") is not False:
            issues.append(f"public_artifact_urls_emitted_not_false:{item.get('artifact_file')}")

    text = json.dumps(payload, sort_keys=True, indent=2)
    raw_leaks = sorted(set(match.group(0)[:80] for match in RAW_LEAK_RE.finditer(text)))
    overclaims: list[str] = []
    for match in OVERCLAIM_OR_ADMISSION_RE.finditer(text):
        start = max(0, match.start() - 100)
        end = min(len(text), match.end() + 100)
        context = text[start:end]
        if not ALLOWED_FAIL_CLOSED_CONTEXT_RE.search(context):
            overclaims.append(match.group(0))

    issues.extend(f"raw_leak_pattern:{item}" for item in raw_leaks)
    issues.extend(f"overclaim_or_admission_pattern:{item}" for item in sorted(set(overclaims)))
    return {
        "scan_passed": not issues,
        "issue_count": len(issues),
        "issues": issues,
        "raw_leak_count": len(raw_leaks),
        "overclaim_count": len(set(overclaims)),
        "zero_counter_keys_checked": sorted(ZERO_COUNTERS),
        "raw_content_policy_keys_checked": sorted(RAW_CONTENT_POLICY),
        "lane_top_level_count_keys_required": EXPECTED_STAGE12435_LANE_KEYS,
        "source_guardrail_status_values_allowed": ["passed", "failed", "legacy_no_scan_fail_closed"],
        "scan_scope": "stage12436_public_control_payload_no_private_rows_no_execution",
    }


def split_payload(stage: str, artifact_name: str, payload: Any) -> dict[str, Any]:
    return {
        "stage": stage,
        "artifact": artifact_name,
        "public_safe": True,
        "raw_leak_count": 0,
        "overclaim_count": 0,
        "raw_urls_emitted": False,
        "urls_emitted": False,
        "payload": payload,
    }


def build_artifact() -> dict[str, Any]:
    stage12435, input_inventory, source_statuses = stage12435_input()
    schema = SchemaIssueCollector()
    if source_statuses["stage12435_proof_slot_execution_path_reconciliation"] != "passed":
        schema.add(
            "source_guardrail_status_not_passed:stage12435_proof_slot_execution_path_reconciliation:"
            + source_statuses["stage12435_proof_slot_execution_path_reconciliation"]
        )
    lane_counts = carried_lane_top_level_counts(stage12435, schema)
    normalized = normalized_top_level_counters(lane_counts, schema)
    open_contract = open_swe_lane_contract(normalized)
    session_contract = session_like_lane_contract(normalized)
    lane_contracts = {
        "open_swe_private_replay_executor_pilot_20": open_contract,
        "session_like_materializer_upgrade": session_contract,
    }
    accounting = required_public_postrun_accounting_tables()
    floors = pilot_and_ramp_floors(stage12435)
    stops = shared_stop_conditions()
    schema_errors = sorted(set(schema.issues))
    recommendation_blocked = bool(schema_errors)

    artifact: dict[str, Any] = {
        "stage": STAGE,
        "record_type": "parallel_two_lane_control_request_v1",
        "decision": "fail_closed_freeze_parallel_two_lane_control_request",
        "selected_path": "parallel_two_lane_control" if not recommendation_blocked else "blocked_fail_closed_schema_error",
        "selected_lanes": NEXT_LANES,
        "canonical_lane_names": NEXT_LANES,
        "lane_alias_map": LANE_ALIAS_MAP,
        **normalized,
        **ZERO_COUNTERS,
        "schema_errors": schema_errors,
        "schema_error_count": len(schema_errors),
        "recommendation_blocked": recommendation_blocked,
        "raw_content_policy": RAW_CONTENT_POLICY,
        "source_stage": "stage12435_proof_slot_execution_path_reconciliation",
        "source_stage_decision_hash": stable_hash(stage12435.get("decision"), 16),
        "source_stage_summary_hash": stage12435.get("summary_hash", stable_hash(stage12435, 24)),
        "source_guardrail_statuses": source_statuses,
        "input_inventory": input_inventory,
        "lane_top_level_counts": lane_counts,
        "lane_contracts": lane_contracts,
        "public_denominator_snapshot": public_denominator_snapshot(normalized),
        "open_swe_lane_contract": open_contract,
        "session_like_lane_contract": session_contract,
        "shared_stop_conditions": stops,
        "required_public_postrun_accounting_tables": accounting,
        "pilot_and_ramp_floors": floors,
        "public_artifact_manifest": public_artifact_manifest(),
        "control_gate_status": {
            "artifact_is_control_only": "PASS",
            "private_replay_executed_by_stage12436": "PASS_FALSE",
            "private_rows_inspected_by_stage12436": "PASS_ZERO",
            "training_allowed_false": "PASS",
            "admission_allowed_false": "PASS",
            "execution_allowed_false": "PASS",
            "no_rows_admitted": "PASS",
            "no_training_rows_emitted": "PASS",
            "lane_top_level_counts_use_explicit_stage12435_keys": "PASS" if not schema_errors else "FAIL_CLOSED",
            "canonical_open_swe_lane": CANONICAL_OPEN_SWE_LANE,
            "open_swe_stage12435_alias": STAGE12435_OPEN_SWE_LANE_KEY,
            "generic_lane_top_level_counts_session_like_absent": "PASS",
            "open_swe_next_stage": "STAGE12437_PRIVATE_PILOT_20_POSTRUN",
            "session_like_next_stage": "STAGE12438_MATERIALIZER_UPGRADE_POSTRUN",
        },
        "next_stage_recommendation": (
            "BLOCKED_FAIL_CLOSED: repair schema_errors before running successor postruns. Do not run training, "
            "private replay, or admission."
            if recommendation_blocked
            else "Run stage12437_open_swe_private_pilot_20_postrun and "
            "stage12438_session_like_materializer_upgrade_postrun as separate fail-closed public-summary postruns. "
            "Keep training_allowed, admission_allowed, and all row admission counters false or zero until a later "
            "explicit admission gate reviews their aggregate accounting."
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
    artifact = build_artifact()
    write_json(OUT / f"{STAGE}.json", artifact)
    write_json(OUT / "summary.json", artifact)
    write_json(SUMMARY, artifact)
    write_json(OUT / "lane_top_level_counts.json", split_payload(STAGE, "lane_top_level_counts", artifact["lane_top_level_counts"]))
    write_json(OUT / "lane_contracts.json", split_payload(STAGE, "lane_contracts", artifact["lane_contracts"]))
    write_json(OUT / "open_swe_lane_contract.json", split_payload(STAGE, "open_swe_lane_contract", artifact["open_swe_lane_contract"]))
    write_json(
        OUT / "session_like_lane_contract.json",
        split_payload(STAGE, "session_like_lane_contract", artifact["session_like_lane_contract"]),
    )
    write_json(OUT / "shared_stop_conditions.json", split_payload(STAGE, "shared_stop_conditions", artifact["shared_stop_conditions"]))
    write_json(
        OUT / "required_public_postrun_accounting_tables.json",
        split_payload(
            STAGE,
            "required_public_postrun_accounting_tables",
            artifact["required_public_postrun_accounting_tables"],
        ),
    )
    write_json(OUT / "pilot_and_ramp_floors.json", split_payload(STAGE, "pilot_and_ramp_floors", artifact["pilot_and_ramp_floors"]))
    write_json(OUT / "guardrail_scan.json", split_payload(STAGE, "guardrail_scan", artifact["guardrail_scan"]))
    print(json.dumps(artifact, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
