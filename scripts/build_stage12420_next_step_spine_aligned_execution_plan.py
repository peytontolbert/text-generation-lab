#!/usr/bin/env python3
"""Stage12420 spine-aligned next-step execution plan.

This stage emits a control artifact only. It does not admit rows, render
training data, execute replay, or change training_allowed.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12420_next_step_spine_aligned_execution_plan"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12419_CONTROL = (
    ROOT
    / "runs/local/artifacts/stage12419_current_dataset_control_board_v17/current_dataset_control_board_v17.json"
)
CORE_INPUTS = {
    "stage12413_summary": ROOT / "runs/summaries/stage12413_open_swe_level3_proof_gap_replay_manifest.json",
    "stage12415_summary": ROOT / "runs/summaries/stage12415_selected_test_lineage_repair_audit.json",
    "stage12418_summary": ROOT / "runs/summaries/stage12418_normalized_verifier_observation_sanitized_canonicalizer.json",
    "stage12419_control": STAGE12419_CONTROL,
    "central_graph_realignment_doc": ROOT / "docs/CENTRAL_RESEARCH_GRAPH_WITH_STAGE12194_REALIGNMENT_STAGE12195.md",
    "unbounded_task_spine_doc": ROOT / "docs/UNBOUNDED_SOFTWARE_TASK_COMPLETION_SPINE_STAGE12195.md",
    "research_graph_layering_doc": ROOT / "docs/RESEARCH_GRAPH_LAYERING_STAGE12197.md",
    "current_research_spine_doc": ROOT / "docs/CURRENT_RESEARCH_SPINE_RECONSTRUCTED.md",
}

TARGET_TRAIN_SUPPORT_ROWS = 500
LEVEL3_EPISODE_FLOOR = 20
PATCH_TRACE_EPISODE_FLOOR = 8
REPO_FLOOR = 10
LANGUAGE_FLOOR = 3


def stable_hash(value: Any, n: int = 24) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:n]


def file_sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def int_at(mapping: dict[str, Any], key: str, default: int = 0) -> int:
    try:
        return int(mapping.get(key) or default)
    except (TypeError, ValueError):
        return default


def input_inventory() -> dict[str, dict[str, Any]]:
    inventory: dict[str, dict[str, Any]] = {}
    for name, path in CORE_INPUTS.items():
        inventory[name] = {
            "path": str(path.relative_to(ROOT)),
            "present": path.exists(),
            "sha256": file_sha256(path),
        }
    return inventory


def spine_alignment_summary(inventory: dict[str, dict[str, Any]]) -> dict[str, Any]:
    present_docs = sorted(name for name, meta in inventory.items() if name.endswith("_doc") and meta["present"])
    return {
        "control_spine_used_as_current_authority": "stage12419_control",
        "present_core_spine_docs": present_docs,
        "active_rules": [
            "control spine artifacts carry current authority for blockers, gates, claim boundaries, and next plans",
            "bounded transition rows and selected-test rows are auxiliary/projection lanes unless exact verifier-log lineage and proof gates pass",
            "full task-completion training requires verified episode supervision, not raw freeform imitation",
            "raw summaries are evidence, not authority",
        ],
        "unbounded_episode_floor": {
            "level3_plus_episodes": LEVEL3_EPISODE_FLOOR,
            "patch_trace_episodes": PATCH_TRACE_EPISODE_FLOOR,
            "repositories": REPO_FLOOR,
            "languages": LANGUAGE_FLOOR,
            "candidate_action_floors": "must_be_met_by_a_later_episode_quality_gate",
            "leak_and_protected_overlap_audits": "must_be_clean",
        },
    }


def lane_countable_supply(stage12419: dict[str, Any], stage12418: dict[str, Any]) -> dict[str, Any]:
    countable = stage12419.get("countable_train_support") or {}
    current = int_at(countable, "stage12417_current_admitted_train_support_tasks")
    remaining = max(0, TARGET_TRAIN_SUPPORT_ROWS - current)
    return {
        "lane_id": "countable_root_task_supply",
        "purpose": "increase genuine root/task train-support supply only from non-derivative direct evidence",
        "current_state": {
            "target_train_support_rows": TARGET_TRAIN_SUPPORT_ROWS,
            "current_countable_train_support_tasks": current,
            "remaining_gap_to_target": remaining,
            "stage12385_baseline_tasks": int_at(countable, "stage12385_baseline_tasks"),
            "stage12416_net_new_direct_real_log_rows": int_at(countable, "stage12416_net_new_direct_real_log_rows"),
            "language_counts_countable": stage12419.get("language_counts_countable") or {},
            "task_counts_countable": stage12419.get("task_counts_countable") or {},
            "derived_stage12418_rows_counted_here": int_at(stage12418, "countable_as_new_train_support_rows"),
        },
        "next_actions": [
            "mine genuinely new direct real verifier observations not already normalized or counted",
            "dedupe by stable root/task/source/verifier lineage before any future admission stage",
            "prefer source stages with exact command_result_id, verifier_anchor_id, state_update_id, and stop_decision_id",
        ],
        "promotion_gates_exact": [
            f"current_countable_train_support_tasks >= {TARGET_TRAIN_SUPPORT_ROWS}",
            "remaining_gap_to_target == 0",
            "every promoted row has exact non-derived root/task identity and direct real verifier-log lineage",
            "every promoted row has stable dedupe key absent from the existing countable ledger",
            "raw_leak_count == 0 and overclaim_count == 0 in the admission artifact",
            "training_allowed may remain false until downstream trainer and protected-overlap gates also pass",
        ],
        "reject_conditions_exact": [
            "source is a derived projection lane such as Stage12216/Stage12418",
            "source is a control board, request, hash inventory, or blocked lineage audit",
            "row lacks exact root_lineage_key_hash or exact task/root identity",
            "row lacks direct real verifier observation anchors",
            "row duplicates an already countable root/task/training target",
            "row claims repair, source-heldout, strict-eval, or level3 evidence without the required proof slots",
        ],
        "training_allowed": False,
    }


def lane_derived_projection(stage12418: dict[str, Any]) -> dict[str, Any]:
    return {
        "lane_id": "derived_projection_training_data",
        "purpose": "sanitized auxiliary objective/projection rows only; no root-supply or proof-floor accounting",
        "current_state": {
            "source_stage": stage12418.get("source_stage") or "stage12216_normalized_verifier_observation_dataset",
            "source_row_count": int_at(stage12418, "source_row_count"),
            "emitted_sanitized_projection_rows": int_at(stage12418, "emitted_sanitized_projection_rows"),
            "allowed_projections": stage12418.get("allowed_projections") or [],
            "task_projection_counts": stage12418.get("task_projection_counts") or {},
            "target_semantic_counts": stage12418.get("target_semantic_counts") or {},
            "countable_as_new_train_support_rows": int_at(stage12418, "countable_as_new_train_support_rows"),
            "countable_as_new_proof_floor_rows": int_at(stage12418, "countable_as_new_proof_floor_rows"),
            "guardrail_scan_passed": bool(stage12418.get("guardrail_scan_passed")),
            "legacy_input_text_copied_rows": int_at(stage12418, "legacy_input_text_copied_rows"),
        },
        "next_actions": [
            "keep Stage12418 rows in a derived projection lane with explicit lineage back to Stage12216",
            "use only sanitized fields and compact target semantics",
            "do not merge derived rows into countable supply ledgers",
        ],
        "promotion_gates_exact": [
            "guardrail_scan_passed is true",
            "legacy_input_text_copied_rows == 0",
            "raw_command_rows == 0 and raw_leak_count == 0 and overclaim_count == 0",
            "countable_as_new_train_support_rows == 0",
            "countable_as_new_proof_floor_rows == 0",
            "allowed_projections are exactly transition_verifier_transition and transition_continue_or_stop",
        ],
        "reject_conditions_exact": [
            "artifact copies raw input_text, command, path, URL, stdout/stderr, diff, patch, or source text",
            "artifact claims new root/task supply",
            "artifact claims fail-to-pass repair, patch-trace, source-heldout, strict-eval, level3, or level4 admission",
            "artifact emits transition_next_action without an explicit later authorization gate",
            "artifact converts PASS_TO_PASS or PASS_CURRENT_STATE into repair proof",
        ],
        "training_allowed": False,
    }


def lane_replay_proof_gap(stage12413: dict[str, Any]) -> dict[str, Any]:
    return {
        "lane_id": "replay_proof_gap_work",
        "purpose": "turn hash-only proof-gap requests into replay-backed proof, or keep them blocked",
        "current_state": {
            "input_rows": int_at(stage12413, "input_rows"),
            "blocked_rows": int_at(stage12413, "blocked_rows"),
            "admitted_rows": int_at(stage12413, "admitted_rows"),
            "micro_pilot_request_count": int_at(stage12413, "micro_pilot_request_count"),
            "micro_pilot_limit": int_at(stage12413, "micro_pilot_limit"),
            "replay_attempted_count": int_at(stage12413, "replay_attempted_count"),
            "required_missing_proof_slots": stage12413.get("required_missing_proof_slots") or [],
            "causal_linkage_status_counts": stage12413.get("causal_linkage_status_counts") or {},
            "safe_return_schema": stage12413.get("stage12414_safe_return_schema") or [],
            "replay_requirements": stage12413.get("stage12414_replay_requirements") or [],
        },
        "next_actions": [
            "execute only the bounded Stage12413 micro-pilot requests first",
            "return safe hashes/status codes only through the Stage12414 safe schema",
            "promote no proof claim until replay establishes state_before, patch_application, state_after, verifier_relevance, causal_linkage, stop_continue, and correct_next_action_policy",
        ],
        "promotion_gates_exact": [
            "replay_attempted_count > 0 in the replay executor artifact",
            "state_before_checkout_status == PASS",
            "patch_application_status == PASS or explicit_no_patch_reason_status == PASS for no-patch rows",
            "state_before_identity_hash and state_after_identity_hash are present and non-empty",
            "verifier_before_status_code and verifier_after_status_code are present",
            "verifier_relevance_status == PASS",
            "causal_linkage_status == PASS",
            "stop_continue_status == PASS",
            "correct_next_action_policy_status == PASS",
            "raw_content_policy emits no raw commands, paths, locators, outputs, diffs, patches, URLs, issue bodies, or source text",
        ],
        "reject_conditions_exact": [
            "hash-only raw inspection is the only evidence",
            "verifier_before_patch_not_causal_proof",
            "patch_and_verifier_co_present_ordered_not_causal_proof",
            "any required proof slot remains missing or blocked_required_safe_evidence_missing",
            "FAIL_TO_PASS is claimed without before/after verifier causality",
            "PASS_TO_PASS or PASS_CURRENT_STATE is treated as repair proof",
            "raw replay content is emitted into public/model-facing artifacts",
        ],
        "training_allowed": False,
    }


def lane_selected_test_sanitizer(stage12415: dict[str, Any], stage12419: dict[str, Any]) -> dict[str, Any]:
    counters = stage12415.get("counters") or {}
    blocked_lane = stage12419.get("blocked_or_request_lanes") or {}
    required = stage12415.get("required_upstream_fields") or counters.get("required_upstream_fields") or {}
    return {
        "lane_id": "legacy_selected_test_sanitizer_work",
        "purpose": "repair or quarantine legacy selected-test rows before any model-facing reuse",
        "current_state": {
            "unrepaired_selected_test_items": int_at(blocked_lane, "stage12415_unrepaired_selected_test_items", int_at(counters, "unrepaired_items")),
            "repairable_items": int_at(blocked_lane, "stage12415_repairable_items", int_at(counters, "repairable_items")),
            "admitted_rows": int_at(stage12415, "admitted_rows"),
            "missing_join_key_counts": stage12415.get("missing_join_key_counts") or counters.get("missing_join_key_counts") or {},
            "required_upstream_fields": required,
            "decision": stage12415.get("decision") or "zero_admission_required_schema_fix",
        },
        "next_actions": [
            "build a sanitizer/control pass for legacy selected-test model-facing text, or keep these rows legacy-only",
            "attempt exact joins to Stage12203/Stage12207/Stage12215 real verifier-log records before any future row emission",
            "preserve a fail-closed path for rows sourced only from adapters, requests, summaries, or hash inventories",
        ],
        "promotion_gates_exact": [
            "one exact Stage12203/Stage12207/Stage12215 real verifier-log record is joined for each promoted item",
            "stable_real_log_record_id, episode_id, command_result_id, and verifier_anchor_id are present",
            "selected_test_anchor_hash and source_or_test_hash are present",
            "repo_family_hash and root_lineage_key_hash are present",
            "verifier_status and verifier_output_class are present",
            "state_update_id and stop_decision_id are present",
            "raw_leak_count == 0 and overclaim_count == 0",
            "sanitized model-facing projection contains no raw legacy input_text",
        ],
        "reject_conditions_exact": [
            "source_ref_hash is not joined to an exact upstream real verifier-log row",
            "source stage is selected-test adapter/control/review material rather than a direct real verifier-log stage",
            "row is derived only from Stage12406/Stage12407 hashes",
            "target_semantic_id is null or blindly reused from legacy selected-test material",
            "any required join key is missing",
            "raw legacy input_text, selected-test text, command output, path, diff, or source text would be emitted",
        ],
        "training_allowed": False,
    }


def build_plan() -> dict[str, Any]:
    stage12413 = read_json(CORE_INPUTS["stage12413_summary"])
    stage12415 = read_json(CORE_INPUTS["stage12415_summary"])
    stage12418 = read_json(CORE_INPUTS["stage12418_summary"])
    stage12419 = read_json(CORE_INPUTS["stage12419_control"])
    inventory = input_inventory()

    lanes = [
        lane_countable_supply(stage12419, stage12418),
        lane_derived_projection(stage12418),
        lane_replay_proof_gap(stage12413),
        lane_selected_test_sanitizer(stage12415, stage12419),
    ]
    priority_order = [
        "stage12421_new_direct_real_verifier_observation_miner",
        "stage12422_open_swe_replay_micro_pilot",
        "stage12423_legacy_selected_test_sanitizer_if_needed",
    ]
    self_counters = {
        "admitted_rows": 0,
        "emitted_training_rows": 0,
        "countable_as_new_train_support_rows": 0,
        "countable_as_new_proof_floor_rows": 0,
        "replay_attempted_count": 0,
        "patch_apply_attempted_count": 0,
        "tests_run_count": 0,
        "training_allowed": False,
    }
    plan = {
        "stage": STAGE,
        "record_type": "spine_aligned_next_step_execution_plan_v1",
        "decision": "control_artifact_only_training_blocked_no_rows_admitted",
        "claim_boundary": (
            "Stage12420 is a machine-readable next-step execution plan. It separates "
            "countable root/task supply, derived projection training data, replay/proof-gap work, "
            "and legacy selected-test sanitizer work. It emits no training rows and changes no admission state."
        ),
        "admitted_rows": 0,
        "emitted_rows": 0,
        "emitted_training_rows": 0,
        "countable_new_rows": 0,
        "countable_as_new_train_support_rows": 0,
        "countable_as_new_proof_floor_rows": 0,
        "priority_order": priority_order,
        "next_stage_sequence": priority_order,
        "input_inventory": inventory,
        "spine_alignment": spine_alignment_summary(inventory),
        "execution_lanes": lanes,
        "global_promotion_gates_exact": [
            f"countable train-support supply reaches {TARGET_TRAIN_SUPPORT_ROWS} before general training promotion",
            f"unbounded closed-loop promotion requires at least {LEVEL3_EPISODE_FLOOR} level_3+ episodes",
            f"unbounded closed-loop promotion requires at least {PATCH_TRACE_EPISODE_FLOOR} patch-trace episodes",
            f"unbounded closed-loop promotion requires at least {REPO_FLOOR} repositories",
            f"unbounded closed-loop promotion requires at least {LANGUAGE_FLOOR} languages",
            "candidate-action floors are met by a later episode quality gate",
            "no cross-source episode fabrication",
            "raw leak, overclaim, protected-overlap, and shortcut audits are clean",
            "trainer changes are contract-only until data gates pass",
        ],
        "global_reject_conditions_exact": [
            "any Stage12420 artifact emits jsonl training rows",
            "training_allowed is true in any Stage12420 artifact",
            "admitted_rows or emitted_training_rows is non-zero",
            "raw commands, outputs, paths, URLs, source text, diffs, patches, or legacy input_text are emitted",
            "derived projection rows are counted as new root/task supply",
            "hash-only proof-gap requests are counted as replay proof",
            "legacy selected-test rows are reused without the required real verifier-log joins and sanitizer pass",
        ],
        "stage12420_self_counters": self_counters,
        "artifact_manifest": {
            "primary_plan": "next_step_spine_aligned_execution_plan.json",
            "summary": str(SUMMARY.relative_to(ROOT)),
            "jsonl_outputs": [],
            "training_package_outputs": [],
        },
        "training_allowed": False,
    }
    plan["promotion_gates"] = plan["global_promotion_gates_exact"]
    plan["reject_conditions"] = plan["global_reject_conditions_exact"]
    plan["next_stage_recommendation"] = priority_order[0]
    plan["plan_hash"] = stable_hash({k: v for k, v in plan.items() if k != "plan_hash"})
    return plan


def main() -> None:
    plan = build_plan()
    write_json(OUT / "next_step_spine_aligned_execution_plan.json", plan)
    write_json(SUMMARY, plan)
    print(json.dumps(plan, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
