#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12294_patch_task_source_adapter_atlas"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"


def read_json(path: Path) -> dict:
    if not path.exists():
        return {"missing": True, "path": str(path)}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    s12216 = read_json(ROOT / "runs/summaries/stage12216_normalized_verifier_observation_dataset.json")
    s12225 = read_json(ROOT / "runs/summaries/stage12225_patch_trace_semantic_qc.json")
    s12240 = read_json(ROOT / "runs/summaries/stage12240_external_repair_acquisition_request_v2.json")
    s12242 = read_json(ROOT / "runs/summaries/stage12242_maintainer_500_candidate_intake_rollup.json")
    s12293 = read_json(ROOT / "runs/summaries/stage12293_commit_pair_queue_exhaustion_and_next_source_decision.json")

    source_adapters = [
        {
            "adapter_id": "explicit_patch_task_corpus_adapter",
            "priority": 1,
            "status": "needed_not_materialized",
            "target_sources": [
                "local benchmark/task corpora with explicit failing tests and reference patches",
                "repo-local task specs with before/after verifier logs",
                "SWE-style task records if present locally and reproducible without network",
            ],
            "why": "Stage12244 inferred patch effect from commits and failed. Explicit task corpora should provide the failing-test/reference-patch bracket directly.",
            "admission_gate": [
                "reference_patch_available_or_exact_commit_after_diff_materializable",
                "selected_verifier_exists_before_patch",
                "before_verifier_status_FAIL_behavior_not_missing_test_or_env",
                "before_plus_reference_patch_status_PASS",
                "after_status_PASS_when_after_commit_available",
                "semantic_patch_effect_audit_required_before_counting_external_comparable",
            ],
            "counts_now": {
                "admitted_external_comparable_patch_trace_rows": 0,
                "admitted_external_FAIL_TO_PASS_rows": 0,
            },
            "next_stage": "stage12295_local_explicit_patch_task_corpus_inventory",
        },
        {
            "adapter_id": "maintainer500_backlog_after_first_adapter",
            "priority": 2,
            "status": "candidate_backlog_only",
            "target_sources": [
                "stage12240_external_repair_acquisition_request_v2",
                "stage12242_maintainer_500_candidate_intake_rollup",
            ],
            "why": "There are 70 reported external repair acquisition candidates, but they are planned/backlog records without command-output tuples.",
            "admission_gate": [
                "materialize_full_resolved_repo_and_commit_or_patch_source",
                "run_after_verifier_first_and_require_PASS",
                "run_before_verifier_second_and_require_FAIL",
                "apply_reference_patch_and_require_PASS",
                "reject_if_command_output_tuple_missing",
            ],
            "counts_now": {
                "external_repair_acquisition_candidates": s12242.get("rollup_counts", {}).get("external_repair_acquisition_total"),
                "admitted_external_comparable_repair_roots": s12242.get("rollup_counts", {}).get("admitted_external_comparable_repair_roots"),
            },
            "next_stage": "stage12296_maintainer500_after_first_retarget_batch",
        },
        {
            "adapter_id": "verifier_observation_join_adapter",
            "priority": 3,
            "status": "auxiliary_support_only_until_patch_joined",
            "target_sources": [
                "stage12216_normalized_verifier_observation_dataset",
                "stage12143_to_stage12152_selected_test_verifier_roots",
            ],
            "why": "These records have runnable verifier evidence and multilingual coverage, but Stage12216 explicitly has no patch-trace floor.",
            "admission_gate": [
                "same_source_patch_or_reference_diff_join_required",
                "no_verifier_only_row_may_count_as_repair_proof",
                "FAIL_TO_PASS_label_must_be_revalidated_with_patch_effect_tuple",
            ],
            "counts_now": {
                "normalized_verifier_rows": s12216.get("row_count"),
                "runnable_verifier_proof_count": s12216.get("audit", {}).get("runnable_verifier_proof_count"),
                "patch_trace_floor_false_count": s12216.get("audit", {}).get("patch_trace_floor_false_count"),
            },
            "next_stage": "stage12297_verifier_observation_patch_join_candidates",
        },
        {
            "adapter_id": "codex_chat_horizon_transition_adapter",
            "priority": 4,
            "status": "transition_training_source_not_repair_proof_source",
            "target_sources": [
                "stage12257_to_stage12279 codex chat/window/horizon artifacts",
            ],
            "why": "Large event volume can train next_action, verifier_transition, continue_stop, and milestone policy, but must not be counted as patch-effect proof without V5.",
            "admission_gate": [
                "derive_canonical_transition_event_v1",
                "mask_future_observations_from_pre_action_inputs",
                "split_by_parent_root_lineage",
                "cap_by_chat_repo_verifier_action_state_delta",
                "external_repair_countable_only_if_V5_patch_effect_tuple_exists",
            ],
            "counts_now": {
                "external_comparable_patch_trace_rows": 0,
                "rendered_train_support_rows_from_current_chat_path": 2,
            },
            "next_stage": "stage12298_horizon_transition_ledger_builder",
        },
        {
            "adapter_id": "exhausted_commit_pair_adapter_v1",
            "priority": 99,
            "status": "blocked_exhausted_until_retargeted",
            "target_sources": [
                "stage12244_external_repair_commit_pair_replay_request",
            ],
            "why": "After-pass filtering and before replay proved the current queue has no PE2 candidates.",
            "admission_gate": [
                "do_not_reuse_without_new_after_first_target_construction",
            ],
            "counts_now": {
                "targets_checked_after": s12293.get("evidence", {}).get("stage12291", {}).get("targets_checked"),
                "after_pass_eligible": s12293.get("evidence", {}).get("stage12291", {}).get("eligible_after_pass"),
                "PE2_candidates_after_filter": s12293.get("evidence", {}).get("stage12292", {}).get("PE2_candidates"),
            },
            "next_stage": None,
        },
    ]

    summary = {
        "stage": STAGE,
        "decision": "patch_task_source_adapter_atlas_ready_no_training",
        "training_allowed": False,
        "admitted_rows": 0,
        "training_rows_emitted": 0,
        "source_adapters": source_adapters,
        "minimum_before_training": s12240.get("acquisition_goal", {}).get("minimum_before_training"),
        "preferred_batch": s12240.get("acquisition_goal", {}).get("preferred_batch"),
        "hard_rejects_inherited": s12240.get("hard_rejects"),
        "current_patch_trace_semantic_qc": {
            "stage12225_patch_trace_floor_count": s12225.get("patch_trace_floor_count"),
            "stage12225_fail_to_pass_floor_count": s12225.get("fail_to_pass_floor_count"),
            "stage12225_transition_counts": s12225.get("transition_counts"),
        },
        "next_stage": "stage12295_local_explicit_patch_task_corpus_inventory",
        "raw_output_emitted": False,
    }

    (OUT / "patch_task_source_adapter_atlas.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (OUT / "PATCH_TASK_SOURCE_ADAPTER_ATLAS_STAGE12294.md").write_text(
        "# Stage12294 Patch Task Source Adapter Atlas\n\n"
        + "No training rows are emitted. This atlas ranks source adapters after Stage12244 exhaustion.\n\n"
        + "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
