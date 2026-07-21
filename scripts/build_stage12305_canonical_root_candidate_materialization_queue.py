#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12305_canonical_root_candidate_materialization_queue"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

SOURCE_PATHS = {
    "stage12304_summary": "runs/summaries/stage12304_canonical_root_mining_spine_alignment.json",
    "stage12303_work_items": "runs/local/artifacts/stage12303_semantic_transition_function_reconstruction/semantic_transition_reconstruction_work_items.jsonl",
    "stage12121_rust_plan": "runs/local/artifacts/stage12121_rust_verifier_ready_candidate_plan/rust_verifier_ready_candidate_plan.jsonl",
    "stage12121_cpp_plan": "runs/local/artifacts/stage12121_cpp_verifier_ready_candidate_plan/cpp_verifier_ready_candidate_plan.jsonl",
    "stage12146_selected_test_rollup": "runs/local/artifacts/stage12146_selected_test_supply_rollup/selected_test_supply_rollup.jsonl",
    "stage11968_transition_repair_queue": "runs/local/artifacts/stage11968_transition_root_250_candidate_miner/transition_root_250_repair_queue.jsonl",
    "stage12256_session_inventory": "runs/local/artifacts/stage12256_live_physical_session_inventory_refresh/live_physical_source_records.jsonl",
}


def path_exists(rel: str) -> bool:
    return (ROOT / rel).exists()


def count_jsonl(rel: str) -> int | None:
    path = ROOT / rel
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    source_status = {
        name: {
            "path": rel,
            "exists": path_exists(rel),
            "jsonl_rows": count_jsonl(rel) if rel.endswith(".jsonl") else None,
        }
        for name, rel in SOURCE_PATHS.items()
    }

    materialization_queue = [
        {
            "queue_id": "Q1_session_event_episode_graph_materialization",
            "priority": 1,
            "source_pool": "session_like_source_inventory_real",
            "goal": "Produce canonical root candidates from raw Codex/session events, not projection rows.",
            "target_count_initial": 25,
            "target_count_after_qc": 100,
            "expected_levels": ["level_1_verifier_only_no_patch", "level_3_single_step_closed_loop", "level_4_multi_step_maintainer_episode"],
            "source_artifacts": [SOURCE_PATHS["stage12256_session_inventory"]],
            "must_emit_fields": [
                "canonical_root_id",
                "repo_family",
                "language_family",
                "source_root_label",
                "root_lineage_key",
                "task_window_id",
                "ordered_events_ref",
                "state_before_ref",
                "candidate_action_set",
                "chosen_action_target_only",
                "observation_target_only",
                "verifier_result_target_only",
                "state_after_or_update_target_only",
                "stop_continue_target_only",
                "admission_level",
                "blocked_reasons",
            ],
            "hard_rejects": [
                "missing_source_root_label",
                "overlapping_task_window_without_parent_child_relation",
                "patch_and_verifier_only_co_present_not_ordered",
                "raw_tool_output_or_patch_body_emitted",
                "single_session_dominates_pool",
                "no_candidate_action_set",
            ],
            "subagent_instruction": "Materialize only episode_graph_candidate records. Do not emit training rows. Cap at 3 candidates per chat/session.",
        },
        {
            "queue_id": "Q2_external_rust_selected_test_transition_roots",
            "priority": 2,
            "source_pool": "selected_test_rust_supply",
            "goal": "Recover external Rust canonical transition roots because Stage12303 has zero external Rust.",
            "ready_or_seed_repos": ["assert-rs/predicates-rs", "toml-rs/toml", "dtolnay/anyhow"],
            "next_hydration_repos": ["BurntSushi/byteorder", "bytes-rs/bytes", "rust-cli/env_logger", "aho-corasick", "quote", "time", "uuid"],
            "source_artifacts": [
                "runs/summaries/stage12144_rust_hydrated_selected_test_success_package.json",
                SOURCE_PATHS["stage12121_rust_plan"],
                SOURCE_PATHS["stage12146_selected_test_rollup"],
            ],
            "target_count_initial": 20,
            "expected_levels": ["level_1_verifier_only_no_patch", "level_2_patch_context_no_execution"],
            "canonical_countable_only_if": [
                "external_non_self_repo_lineage",
                "commit_sha_source_hash_test_hash_present",
                "selected_verifier_command_exit_code_log_present",
                "non_singleton_semantic_candidate_set",
                "target_diversity_has_pass_fail_or_not_exercised",
            ],
            "hard_rejects": [
                "env_or_dependency_failure_labeled_as_verifier_outcome",
                "one_sided_target_shortcut",
                "selected_test_role_without_real_test",
                "raw_run_verify_patch_label_as_target",
            ],
            "subagent_instruction": "Create canonical_root_candidate records for Rust. Mark train_support_allowed=false unless semantic rule and candidate-set gates pass.",
        },
        {
            "queue_id": "Q3_external_cpp_selected_test_transition_roots",
            "priority": 3,
            "source_pool": "selected_test_cpp_supply",
            "goal": "Recover external C/C++ canonical transition roots because Stage12303 has zero external C/C++.",
            "ready_or_seed_repos": ["Neargye/magic_enum", "fastfloat/fast_float"],
            "next_hydration_repos": ["jarro2783/cxxopts", "p-ranav/argparse", "google/snappy", "google/crc32c", "google/re2", "Tencent/rapidjson", "USCiLab/cereal", "microsoft/GSL"],
            "source_artifacts": [
                SOURCE_PATHS["stage12121_cpp_plan"],
                "runs/local/artifacts/stage12130_selected_test_train_support_package/train_support_rows.jsonl",
                "runs/local/artifacts/stage12130_selected_test_train_support_package/train_support_package_audit.json",
                SOURCE_PATHS["stage12146_selected_test_rollup"],
            ],
            "target_count_initial": 20,
            "expected_levels": ["level_1_verifier_only_no_patch", "level_2_patch_context_no_execution"],
            "canonical_countable_only_if": [
                "external_non_self_repo_lineage",
                "commit_sha_source_hash_test_hash_present",
                "selected_verifier_command_exit_code_log_present",
                "non_singleton_semantic_candidate_set",
                "target_diversity_has_pass_fail_or_not_exercised",
            ],
            "hard_rejects": [
                "known_stage12130_semantic_collapse_unrepaired",
                "missing_competing_options",
                "already_in_base_transition_records_without_fresh_lineage",
                "raw_run_verify_patch_label_as_target",
            ],
            "subagent_instruction": "Create canonical_root_candidate records for C/C++. Do not reuse Stage12130 rows without task-specific semantic rewrite.",
        },
        {
            "queue_id": "Q4_semantic_h1_transition_rewrite",
            "priority": 4,
            "source_pool": "stage12303_external_h1_work_items",
            "goal": "Rewrite the 59 external H1 work items into semantic transition-function candidates if deterministic state/rule labels can be assigned.",
            "source_artifacts": [SOURCE_PATHS["stage12303_work_items"]],
            "target_count_initial": 59,
            "expected_levels": ["level_1_verifier_only_no_patch", "auxiliary_transition_function_support"],
            "canonical_countable_only_if": [
                "semantic_rule_id_assigned_from_pre_action_state",
                "candidate_roles_removed_from_model_visible_fields",
                "transition_function_key_present",
                "three_or_more_semantic_candidates",
                "two_or_more_hard_negative_reason_codes",
            ],
            "hard_rejects": [
                "observed_action_imitation",
                "state_update_requires_semantic_review",
                "candidate_count_below_floor",
                "raw_tool_action_target",
            ],
            "subagent_instruction": "Attempt deterministic semantic rewrite. If any label depends on observed action rather than pre-action state, block it.",
        },
        {
            "queue_id": "Q5_external_patch_effect_retargeting",
            "priority": 5,
            "source_pool": "external_commit_patch_corpora",
            "goal": "Find true patch-effect proof sources after Stage12244 replay exhausted broad commit-pair queue.",
            "target_count_initial": 15,
            "expected_levels": ["level_3_single_step_closed_loop"],
            "source_artifacts": [
                "stage12240_external_root_backlog",
                "stage12242_external_repair_acquisition_candidates",
                "external_repo_commit_family_v2",
            ],
            "canonical_countable_only_if": [
                "before_fail_command_output",
                "reference_or_candidate_patch_diff",
                "after_pass_command_output",
                "same_source_patch_verifier_lineage",
                "no_cross_source_join",
            ],
            "hard_rejects": [
                "before_did_not_fail",
                "commit_metadata_only",
                "patch_verifier_co_presence_only",
                "env_blocked_not_task_specific",
            ],
            "subagent_instruction": "Retarget only sources with authoritative verifier logs or locally executable tests. Do not replay broad commit pairs blindly.",
        },
    ]

    summary = {
        "stage": STAGE,
        "decision": "canonical_root_candidate_materialization_queue_ready_no_training",
        "claim_boundary": "This queue directs subagents/materializers. It admits no rows and authorizes no training.",
        "training_allowed": False,
        "source_status": source_status,
        "queue_count": len(materialization_queue),
        "materialization_queue": materialization_queue,
        "minimum_next_progress_counters": {
            "canonical_root_candidates": 100,
            "level_3_plus_candidates": 20,
            "patch_trace_candidates": 8,
            "languages": 3,
            "repositories": 10,
            "rust_external_candidates": 20,
            "cpp_external_candidates": 20,
            "semantic_h1_rewrites": 30,
        },
        "plateau_avoidance_rules": [
            "Do not count support/projection rows as canonical roots.",
            "Do not train on raw run/verify/patch action imitation.",
            "Do not count verifier-only rows as patch repair proof.",
            "Do not use self-research roots for external multilingual claims.",
            "Do not scale a source pool until its admission level and blocker distribution are explicit.",
        ],
        "next_stage": "stage12306_canonical_root_candidate_materializer",
    }

    (OUT / "canonical_root_candidate_materialization_queue.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (OUT / "canonical_root_candidate_materialization_queue.jsonl").open("w", encoding="utf-8") as handle:
        for item in materialization_queue:
            handle.write(json.dumps(item, sort_keys=True) + "\n")
    (OUT / "CANONICAL_ROOT_CANDIDATE_MATERIALIZATION_QUEUE_STAGE12305.md").write_text(
        "# Stage12305 Canonical Root Candidate Materialization Queue\n\n"
        "No training rows are admitted. This is the work queue for canonical root expansion.\n\n"
        "## Queues\n\n"
        + "\n".join(f"- `{item['queue_id']}`: {item['goal']}" for item in materialization_queue)
        + "\n",
        encoding="utf-8",
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
