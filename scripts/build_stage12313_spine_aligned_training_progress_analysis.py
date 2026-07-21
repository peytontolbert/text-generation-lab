#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12313_spine_aligned_training_progress_analysis"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    analysis = {
        "stage": STAGE,
        "decision": "spine_aligned_analysis_complete_training_still_blocked",
        "claim_boundary": "Analysis/control artifact only. It admits no rows and authorizes no training.",
        "training_allowed": False,
        "model_frontier_status": {
            "selected_transition_baseline": {
                "stage": "stage11924_transition_listwise_head_only",
                "score": "364/640",
            },
            "best_routed_transition_candidate": {
                "stage": "stage12099_task_routed_candidate_selection_composite_audit",
                "score": "375/640",
                "gemma_same_manifest": "386/640",
                "status": "route_candidate_only_not_sealed_confirmed",
            },
            "actual_score_progress_since_stage11924": "+11/640 routed candidate only",
            "not_yet_supported": [
                "sealed/root-disjoint transition win",
                "standalone unbounded maintainer training win",
                "full product repair or patch-generation claim",
            ],
        },
        "dataset_admissibility_status": {
            "level_3_plus_episodes": 0,
            "patch_trace_episodes": 0,
            "level_4_episodes": 0,
            "train_support_rows_from_stage12304_to_12312": 0,
            "strict_eval_rows_from_stage12304_to_12312": 0,
            "source_heldout_rows_from_stage12304_to_12312": 0,
            "candidate_records": {
                "stage12312_expanded_session_candidates": 100,
                "stage12307_rust_cpp_queue_records": 20,
                "stage12308_h1_rule_feasibility_records": 59,
                "stage12311_coarse_state_hydration_records": 25,
            },
            "blockers": [
                "repo_family_unknown_until_cwd_or_repo_join",
                "raw_session_event_root_requires_causal_review",
                "transition-local state proof missing",
                "semantic_rule_id_missing",
                "transition_function_key_missing",
                "verifier_run_status_unknown_without_structured_output_class",
                "patch_ref_not_patch_plan_or_apply_proof",
                "Rust/C++ selected-test roots missing commit/test/source hashes and executed verifier logs",
            ],
        },
        "trainer_alignment_status": {
            "can_consume_today": [
                "serialized prompt/input rows",
                "bounded/listwise candidate options",
                "transition_candidate_selection",
                "transition_next_action",
                "transition_verifier_transition",
                "transition_continue_or_stop",
                "episode pre-action fields as auxiliary inputs",
            ],
            "cannot_yet_consume_as_primary_unit": [
                "root+task closed-loop trajectory tuple",
                "patch trace with apply/minimality evidence",
                "verifier feedback targets with structured output class",
                "state delta targets with facts added/removed/hypotheses invalidated",
                "stop policy grounded in verifier/task completion",
            ],
            "next_trainer_work": "contract-only trajectory_data.py and closed_loop_trajectory_probe after data gates, not GPU training now",
        },
        "central_spine_gate_before_training": {
            "level_3_plus_episodes_min": 20,
            "patch_trace_episodes_min": 8,
            "repositories_min": 10,
            "languages_min": 3,
            "candidate_action_floors_met": False,
            "cross_source_fabrication_audit_clean": False,
            "leak_and_protected_overlap_audits_clean": False,
            "current_gate_pass": False,
        },
        "plateau_risks": [
            "Expanding Stage12312-style session candidates without repo joins creates Python-heavy unadmitted projections.",
            "Hydrating only coarse window metadata cannot teach transition functions; it cannot distinguish localization, verifier status, patch state, or open questions.",
            "Training bounded/listwise rows before Level-3 tuple proof repeats the localization/classification plateau.",
            "Rust/C++ queue records improve coverage planning but do not become canonical roots until selected verifier logs and hashes are materialized.",
        ],
        "next_two_lanes": [
            {
                "lane": "session_event_level3_join",
                "goal": "Turn Stage12312 candidates into canonical roots by adding repo_family/cwd joins, transition-local state ledgers, verifier status classes, state deltas, and stop/continue proof.",
                "next_stage": "stage12314_session_candidate_repo_and_state_joiner",
                "success_counter": ">=20 Level-3 candidates across >=10 repos and >=3 languages; no training until quality gate passes",
            },
            {
                "lane": "rust_cpp_selected_test_hydration",
                "goal": "Hydrate Stage12307 Rust/C++ queue records with commit SHA, source/test hashes, selected verifier commands/logs, and non-singleton semantic candidates.",
                "next_stage": "stage12315_rust_cpp_selected_test_hydration_worklist",
                "success_counter": "at least 5 Rust and 5 C/C++ roots upgraded from queue-only to reviewed canonical candidates",
            },
        ],
    }

    (OUT / "spine_aligned_training_progress_analysis.json").write_text(
        json.dumps(analysis, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (OUT / "SPINE_ALIGNED_TRAINING_PROGRESS_ANALYSIS_STAGE12313.md").write_text(
        "# Stage12313 Spine-Aligned Training Progress Analysis\n\n"
        "Training remains blocked. Recent work improved candidate/root organization, not trainable unbounded maintainer supply.\n\n"
        "## Decision\n\n"
        f"`{analysis['decision']}`\n\n"
        "## Next Lanes\n\n"
        + "\n".join(f"- `{lane['lane']}`: {lane['goal']}" for lane in analysis["next_two_lanes"])
        + "\n",
        encoding="utf-8",
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(analysis, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
