#!/usr/bin/env python3
"""Build Stage12270 horizon task mining contract.

Defines how to mine long Codex chats into task episodes and horizon slices
without admitting rows or creating training data.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12270_horizon_task_mining_contract"


def load_json(rel: str) -> dict[str, Any]:
    p = ROOT / rel
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def main() -> int:
    s12260 = load_json("runs/summaries/stage12260_codex_chat_task_boundary_miner.json")
    s12263 = load_json("runs/summaries/stage12263_high_value_window_profiler.json")
    s12269 = load_json("runs/summaries/stage12269_external_semantic_review_result_ingest.json")
    contract: dict[str, Any] = {
        "stage": STAGE,
        "artifact_type": "horizon_task_mining_contract",
        "decision": "horizon_task_mining_contract_ready_training_blocked",
        "training_allowed": False,
        "claim_boundary": "Contract/control artifact only. No root admission, no training rows, no raw content.",
        "current_funnel": {
            "source_chats": (s12260.get("counts") or {}).get("source_chats"),
            "task_windows": (s12260.get("counts") or {}).get("task_windows"),
            "command_observation_windows": (s12260.get("counts") or {}).get("candidate_windows_with_command_observation"),
            "patch_verifier_windows": (s12260.get("counts") or {}).get("patch_and_verifier_ref_windows"),
            "stage12263_audit_cap": (s12263.get("counts") or {}).get("selected_audit_windows"),
            "stage12269_external_comparable_repair_rows": (s12269.get("decisive_counter_progress") or {}).get("external_comparable_patch_trace_repair_rows"),
            "stage12269_external_fail_to_pass_rows": (s12269.get("decisive_counter_progress") or {}).get("external_fail_to_pass_rows"),
        },
        "diagnosis": {
            "twenty_five_is_audit_cap_not_total_supply": True,
            "whole_window_as_repair_row_failed": True,
            "reason": "Long windows are multi-loop traces; semantic review found split_required/quarantine rather than admissible repair rows.",
            "new_unit": "horizon_slice_inside_task_episode",
        },
        "hierarchy": [
            "source_session",
            "task_window",
            "episode_graph",
            "child_loop",
            "horizon_slice",
            "projection_row_after_admission",
        ],
        "horizon_levels": {
            "H1_next_action": {
                "span": "one decision boundary",
                "requires": ["state_before_ref", "candidate_action_set", "chosen_action_ref", "observation_ref"],
                "allowed_targets": ["next_action", "candidate_action_rank", "retrieve_or_act", "stop_continue_if_terminal"],
                "forbidden_targets": ["repair_success", "FAIL_TO_PASS", "patch_generation"],
            },
            "H3_micro_loop": {
                "span": "inspect/search/run/patch plus immediate observation",
                "requires": ["state_before_ref", "chosen_action_ref", "observation_ref", "state_update_ref"],
                "allowed_targets": ["state_update", "verifier_interpretation", "continue_or_stop", "evidence_role"],
                "forbidden_targets": ["external_repair_claim_without_pre_post_verifier"],
            },
            "H10_patch_verifier_loop": {
                "span": "one selected patch/action and bounded post-action verifier sequence",
                "requires": ["same_source_patch_or_action", "post_action_verifier", "no_intervening_patch_for_selected_loop"],
                "allowed_targets": ["patch_selection", "verifier_transition", "repair_vs_continue", "failure_origin"],
                "forbidden_targets": ["FAIL_TO_PASS unless same-verifier pre-fail and post-pass are proven"],
            },
            "H50_task_episode": {
                "span": "multi-step local task with hypotheses, edits, verifier feedback, terminal decision",
                "requires": ["multiple child loops", "state ledger", "terminal stop_continue"],
                "allowed_targets": ["milestone_selection", "replan_after_failure", "completion_gate", "trajectory_value"],
                "forbidden_targets": ["counting child slices as independent roots"],
            },
            "H100_plus_long_arc": {
                "span": "long session/task arc spanning many loops or days",
                "requires": ["parent_session_lineage", "task boundary", "child loop graph", "summary state ledger"],
                "allowed_targets": ["long_horizon_state_tracking", "stale_assumption_invalidation", "milestone_decomposition"],
                "forbidden_targets": ["direct SFT on raw transcript", "one-row whole-chat repair label"],
            },
        },
        "required_lineage_fields": [
            "source_session_id",
            "task_window_id",
            "episode_id",
            "child_loop_id",
            "horizon_slice_id",
            "parent_horizon_id",
            "snapshot_id",
            "source_file_hash_compat",
            "line_start",
            "line_end",
            "event_start_id",
            "event_end_id",
            "repo_cwd_digest",
            "state_prefix_hash",
            "candidate_action_set_hash",
            "chosen_action_hash",
            "observation_digest",
            "state_delta_hash",
            "verifier_ref_hash",
        ],
        "dedupe_and_caps": {
            "root_counting_rule": "count parent repo/root/task, not horizon slices",
            "max_horizon_slices_per_child_loop": 4,
            "max_child_loops_per_task_window": 8,
            "max_task_windows_per_chat_for_training": 20,
            "max_same_action_type_per_parent": 8,
            "max_same_verifier_shape_per_parent": 5,
            "max_same_state_delta_class_per_parent": 5,
            "train_eval_split_rule": "all descendants of a source_session/task_window/root lineage stay in one split",
        },
        "admission_levels": {
            "V0_source": "source/session/task refs only",
            "V1_action_observation": "paired action and observation refs",
            "V2_task_boundary": "coherent task window with root/cwd lineage",
            "V3_horizon_slice": "state_before, candidate actions, chosen action, observation, state_update, stop_continue when applicable",
            "V4_patch_verifier_loop": "same-source patch/action plus verifier sequence and semantic relevance",
            "V5_external_comparable_repair": "external root, same-verifier pre-fail/post-pass, no leakage, no cross-source joins",
        },
        "next_stage": {
            "stage": "stage12271_horizon_slice_miner_pilot",
            "scope": "mine a capped pilot of horizon slices from command-observation and patch-verifier windows; no training rows",
            "training_allowed": False,
        },
        "guardrails": {
            "raw_message_text_emitted": False,
            "raw_patch_body_emitted": False,
            "raw_tool_arguments_emitted": False,
            "raw_tool_output_emitted": False,
            "root_admission_emitted": False,
            "training_rows_emitted_now": False,
        },
    }
    out_dir = ROOT / "runs/local/artifacts" / STAGE
    write_json(ROOT / "runs/summaries" / f"{STAGE}.json", contract)
    write_json(out_dir / "horizon_task_mining_contract.json", contract)
    md = f"""# Stage12270 Horizon Task Mining Contract

## Decision

`{contract["decision"]}`

The dataset unit is no longer whole long windows as repair rows. The unit is a lineage-preserving `horizon_slice` inside a task episode.

No training is allowed.
"""
    write_text(out_dir / "HORIZON_TASK_MINING_CONTRACT_STAGE12270.md", md)
    print(ROOT / "runs/summaries" / f"{STAGE}.json")
    print(out_dir / "HORIZON_TASK_MINING_CONTRACT_STAGE12270.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
