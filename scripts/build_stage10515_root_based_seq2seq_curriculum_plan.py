from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10515
NAME = "stage10515_root_based_seq2seq_curriculum_plan"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME

PLAN_JSON = OUT_DIR / "root_based_seq2seq_curriculum_plan.json"
ROOT_SCHEMA_JSON = OUT_DIR / "canonical_maintainer_root_schema.json"
EVENT_SCHEMA_JSON = OUT_DIR / "typed_long_context_event_schema.json"
STATE_SCHEMA_JSON = OUT_DIR / "causal_state_projection_schema.json"
SUMMARY_JSON = ROOT / "runs/summaries" / f"{NAME}.json"


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_JSON.parent.mkdir(parents=True, exist_ok=True)

    root_schema = {
        "schema_name": "canonical_maintainer_root_schema",
        "version": "v1",
        "core_rule": "all rows from the same root_id must stay in the same split_component",
        "entities": {
            "root": {
                "definition": "repo snapshot plus task, environment, verifier, and provenance bundle",
                "required_fields": [
                    "root_id",
                    "repo_id",
                    "repo_family",
                    "language_family",
                    "task_family",
                    "snapshot_id",
                    "environment_id",
                    "verifier_id",
                    "provenance",
                    "split_component",
                ],
            },
            "episode": {
                "definition": "one attempted trajectory on a root",
                "required_fields": [
                    "episode_id",
                    "root_id",
                    "episode_kind",
                    "agent_family",
                    "start_state_id",
                    "terminal_state_id",
                    "outcome_grade",
                ],
            },
            "state": {
                "definition": "causal prefix before a decision boundary",
                "required_fields": [
                    "state_id",
                    "episode_id",
                    "root_id",
                    "event_span",
                    "state_kind",
                    "visible_evidence_ids",
                    "candidate_set_ids",
                    "hypothesis_status",
                ],
            },
            "row": {
                "definition": "one supervised projection from a causal state",
                "required_fields": [
                    "row_id",
                    "root_id",
                    "episode_id",
                    "state_id",
                    "split_component",
                    "target_family",
                    "target_subtype",
                    "input_text",
                    "target_text",
                    "anti_cheat",
                ],
            },
        },
        "anti_leak_contract": {
            "same_root_across_splits_forbidden": True,
            "same_repo_family_across_time_holdout_requires_explicit_policy": True,
            "target_string_visible_before_options_forbidden": True,
            "post_fix_source_visible_in_pre_action_state_forbidden": True,
            "option_label_shortcuts_rejected": True,
        },
    }

    event_schema = {
        "schema_name": "typed_long_context_event_schema",
        "version": "v1",
        "event_types": [
            "USER_TASK",
            "FILE_READ",
            "SEARCH_RESULT",
            "COMMAND",
            "COMMAND_RESULT",
            "PATCH",
            "TEST_RESULT",
            "FINAL_RESPONSE",
        ],
        "required_event_fields": [
            "event_id",
            "episode_id",
            "root_id",
            "event_index",
            "event_type",
            "timestamp_utc",
            "actor",
            "content",
            "artifact_refs",
        ],
        "state_extraction_boundaries": [
            "new_relevant_file_found",
            "hypothesis_confirmed",
            "hypothesis_rejected",
            "patch_applied",
            "test_outcome_changed",
            "verifier_result_arrived",
            "terminal_condition_reached",
        ],
        "normalization_rules": [
            "do not train on raw conversation logs as the main format",
            "collapse repeated low-information executor chatter",
            "preserve direct evidence payloads with stable evidence_ids",
            "carry forward candidate sets and verifier anchors into states",
            "mark each state with the minimal event span needed to justify the projection targets",
        ],
    }

    state_schema = {
        "schema_name": "causal_state_projection_schema",
        "version": "v1",
        "projection_targets": [
            {
                "target_family": "bounded_decision",
                "target_subtypes": [
                    "relevant_file",
                    "relevant_symbol",
                    "decisive_evidence",
                    "verifier_outcome",
                    "retrieve_answer_abstain",
                ],
            },
            {
                "target_family": "short_structured_text",
                "target_subtypes": [
                    "next_action",
                    "repair_intent",
                    "structured_plan",
                    "abstention_rationale",
                ],
            },
            {
                "target_family": "constrained_generation",
                "target_subtypes": [
                    "patch_sketch",
                    "edit_anchor",
                    "expected_verifier_delta",
                ],
            },
        ],
        "candidate_scoring_shift": {
            "replace_internal_letter_prediction": True,
            "score_functions": [
                "(state, candidate_test) -> score",
                "(state, candidate_evidence) -> score",
                "(state, candidate_action) -> score",
            ],
            "presentation_only_labels": "A-F labels remain UI wrappers, not the latent target space",
        },
        "training_loss_mix": [
            "seq2seq_generation",
            "candidate_ranking",
            "evidence_role_classification",
            "verifier_transition_prediction",
            "retrieve_answer_abstain",
            "contrastive_hard_negatives",
        ],
        "bounded_choice_replay_policy": {
            "keep_fraction_during_later_training": "0.20-0.30",
            "purpose": "preserve current bounded strengths while generation and structured outputs expand",
        },
    }

    plan = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "core_message": (
            "Stop treating the repaired 24-row frontier as the training target. "
            "Freeze it as a canary/regression suite and shift the training loop to root-based seq2seq software-maintenance prediction."
        ),
        "current_canary_boundary": {
            "frontier_role": "regression_only",
            "uses": [
                "regression checks",
                "label permutation checks",
                "leak detection",
                "margin diagnostics",
            ],
            "forbidden_uses": [
                "direct residual-target training objective",
                "promotion headline for broad software-maintenance capability",
            ],
        },
        "stages": [
            {
                "stage_id": 0,
                "name": "Freeze Canary",
                "objective": "Keep the repaired v2.7 24-row frontier fixed as a regression/canary suite.",
            },
            {
                "stage_id": 1,
                "name": "Root Format",
                "objective": "Adopt canonical root, episode, state, and row schemas with root-level split isolation.",
                "artifact": str(ROOT_SCHEMA_JSON.relative_to(ROOT)),
            },
            {
                "stage_id": 2,
                "name": "Trace Compiler",
                "objective": "Turn long-context traces into typed events and extract causal states only at meaningful boundaries.",
                "artifact": str(EVENT_SCHEMA_JSON.relative_to(ROOT)),
            },
            {
                "stage_id": 3,
                "name": "Multi-Target Rows",
                "objective": "Project many seq2seq supervision targets from each causal state.",
                "artifact": str(STATE_SCHEMA_JSON.relative_to(ROOT)),
            },
            {
                "stage_id": 4,
                "name": "Semantic Candidate Scoring",
                "objective": "Score real candidate actions/evidence/tests instead of internal A/B/C labels.",
            },
            {
                "stage_id": 5,
                "name": "Structured Decoder",
                "objective": "Train grammar-constrained structured action outputs before freeform patch text.",
            },
            {
                "stage_id": 6,
                "name": "Patch Sketches",
                "objective": "Train constrained edit-intent and verifier-delta outputs before unified diffs.",
            },
            {
                "stage_id": 7,
                "name": "Verified Repair",
                "objective": "Train executable repair outputs with verifier-grade outcomes and hard negatives.",
            },
        ],
        "immediate_developer_tasks": [
            "Add root_id, episode_id, state_id, and split_component to every training row.",
            "Enforce root-level split isolation in every manifest compiler.",
            "Build the typed event normalizer for long-context traces.",
            "Build the causal state extractor for meaningful decision boundaries.",
            "Add target projectors for verifier outcome, evidence role, next action, repair intent, and patch sketch.",
            "Add leak audits for visible target paths, post-fix evidence, same-root split overlap, and option-label shortcuts.",
            "Keep the current bounded decoder, but move the internal training interface toward semantic candidate scoring.",
        ],
        "near_term_milestone": {
            "name": "Maintainer-5K",
            "targets": {
                "development_roots": 5000,
                "sealed_eval_roots": 1000,
                "repos": 100,
                "languages": ["python", "rust", "c_cpp", "web_js_ts_html"],
                "causal_states": "50k-150k",
                "candidate_comparisons": "150k-500k",
                "patch_sketches": "10k+",
            },
            "holdout_policy": "strict root/repo/time heldout split",
        },
        "long_context_positioning": {
            "statement": "5M+ token side-project traces are a data refinery, not the main model input contract.",
            "compiler_role": [
                "extract causal states",
                "extract verifier anchors",
                "extract evidence chains",
                "extract failed vs successful repair transitions",
                "build hard negatives near the true maintainer decision surface",
            ],
        },
        "next_best_step": (
            "Hook the new canonical root/event/state contracts into the existing bootstrap package lineage, "
            "then compile the first long-context-derived root manifests under strict root isolation."
        ),
    }

    write_json(ROOT_SCHEMA_JSON, root_schema)
    write_json(EVENT_SCHEMA_JSON, event_schema)
    write_json(STATE_SCHEMA_JSON, state_schema)
    write_json(PLAN_JSON, plan)
    write_json(SUMMARY_JSON, plan)


if __name__ == "__main__":
    main()
