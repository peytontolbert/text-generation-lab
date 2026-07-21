#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12325_remaining_384_supply_plan"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    plan = {
        "stage": STAGE,
        "decision": "remaining_384_supply_plan_ready_waiting_on_source_materialization",
        "claim_boundary": "Planning/control artifact only. No rows admitted and no training authorized.",
        "training_allowed": False,
        "current_ledger": {
            "stage12324_current_admitted_train_support_tasks": 116,
            "remaining_gap_to_500": 384,
            "do_not_count": [
                "Stage12295 observed-action imitation rows",
                "Stage12317 review candidates",
                "Stage12318 semantic-review candidates before admission",
                "Stage12321 V4 candidates before extraction/review",
                "controlled fixtures as broad maintainer proof",
            ],
        },
        "next_supply_lanes_ranked": [
            {
                "lane": "selected_test_root_batch_v2",
                "goal": "Add 100-150 train-support rows from selected-test roots across Python/Rust/C++/Web.",
                "inputs_to_mine": [
                    "stage12143_no_install_selected_test_expansion",
                    "stage12144_rust_hydrated_selected_test_success_package",
                    "stage12145_web_hydrated_selected_test_success_package",
                    "stage12146_selected_test_supply_rollup",
                    "stage12149_corrected_selected_test_row_materialization_package",
                    "stage12307_rust_cpp_selected_test_root_candidate_queue",
                ],
                "admission_requirements": [
                    "commit_sha",
                    "selected_test_id_or_scope",
                    "executed_verifier_log_ref",
                    "source_hash_refs",
                    "test_hash_refs",
                    "non_singleton_opaque_options",
                    "target label/value not visible before options",
                    "deterministic option shuffle",
                ],
                "do_not_claim": ["strict_eval", "source_heldout", "Level3 repair"],
            },
            {
                "lane": "remaining_v4_extraction",
                "goal": "Extract/review 27 Stage12321 V4 parents plus any linked-but-unadmitted V4 refs.",
                "expected_rows": "small; likely <50 under current caps",
                "admission_requirements": [
                    "Stage12316-style semantic status extraction",
                    "Stage12320-style target-hidden observation/status admission",
                    "no observed-action policy labels",
                ],
            },
            {
                "lane": "external_trace_adapter_batch",
                "goal": "Materialize 100-200 train-support rows from external trajectory/trace sources.",
                "candidate_sources": [
                    "Open-SWE-Traces",
                    "RepairThemAll/Bears",
                    "RepairThemAll/Defects4J",
                    "SWE-bench local fixtures if full instances exist",
                    "long-context compiled traces with verifier logs",
                ],
                "admission_requirements": [
                    "same-source event ordering",
                    "tool/verifier output class",
                    "patch/no-patch status if applicable",
                    "source/test/verifier refs",
                    "target-hidden model input",
                ],
                "do_not_count": [
                    "metadata-only commit pairs",
                    "PASS_TO_PASS rows as repair proof",
                    "cross-source patch/log joins",
                    "raw chat imitation",
                ],
            },
            {
                "lane": "transition_next_action_policy_roots",
                "goal": "Only after selected-test/trace supply improves, build true next-action policy rows.",
                "why_later": "Current observed session actions are telemetry, not gold policy; next-action rows need reviewed state-conditioned alternatives.",
            },
        ],
        "proposed_stage_sequence": [
            {
                "stage": "stage12326_selected_test_root_batch_v2_atlas",
                "purpose": "Find all additional selected-test roots that can pass the Stage12322-style admission contract.",
                "target": ">=20 roots, >=100 candidate rows",
            },
            {
                "stage": "stage12327_selected_test_root_batch_v2_admission",
                "purpose": "Admit only leak-clean selected-test train-support rows.",
                "target": ">=75 admitted rows",
            },
            {
                "stage": "stage12328_external_trace_adapter_preflight",
                "purpose": "Choose one external trace adapter with concrete local evidence and no network dependency.",
                "target": ">=50 materializable rows in first adapter batch",
            },
            {
                "stage": "stage12329_v4_remaining_extraction",
                "purpose": "Process 27 V4 parents needing extraction and update combined ledger.",
                "target": "any clean additional rows, no quota relaxation",
            },
        ],
        "plateau_risks": [
            "Hitting 500 by duplicating event-local status functions from the same chats.",
            "Training observed-action telemetry as next-action policy.",
            "Treating selected-test support rows as repair episodes.",
            "Mixing source adapters without same-source lineage and anti-leak fields.",
        ],
    }
    (OUT / "remaining_384_supply_plan.json").write_text(
        json.dumps(plan, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (OUT / "REMAINING_384_SUPPLY_PLAN_STAGE12325.md").write_text(
        "# Stage12325 Remaining 384 Supply Plan\n\n"
        "Current admitted train-support count is 116/500. The remaining 384 require new source supply, primarily selected-test roots and external trace adapters.\n",
        encoding="utf-8",
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
