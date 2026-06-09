#!/usr/bin/env python3
"""Build the Stage988 claim gate for the 100M budgeted-interface result."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage976", type=Path, default=Path("runs/local/artifacts/stage976_loadable_100m_pair_teacher_model_owned_frontier_summary.json"))
    parser.add_argument("--stage981", type=Path, default=Path("runs/local/artifacts/stage981_100m_pair_interface_hybrid_summary.json"))
    parser.add_argument("--stage982", type=Path, default=Path("runs/local/artifacts/stage982_pair_comparator_budget_audit_summary.json"))
    parser.add_argument("--stage985", type=Path, default=Path("runs/local/artifacts/stage985_qwen3_8b_vs_stage981_full_640_same_candidate_comparison_summary.json"))
    parser.add_argument("--stage987", type=Path, default=Path("runs/local/artifacts/stage987_qwen35_9b_vs_stage981_full_640_same_candidate_comparison_summary.json"))
    parser.add_argument("--output-json", type=Path, default=Path("runs/local/artifacts/stage988_100m_budgeted_interface_claim_gate_summary.json"))
    args = parser.parse_args()

    stage976 = _read(args.stage976)
    stage981 = _read(args.stage981)
    stage982 = _read(args.stage982)
    stage985 = _read(args.stage985)
    stage987 = _read(args.stage987)

    stage976_score = [
        int(stage976["operation_gated_eval"]["answer"]),
        int(stage976["operation_gated_eval"]["exact"]),
    ]
    stage981_score = [
        int(stage981["split_scores"]["eval"]["answer"]),
        int(stage981["split_scores"]["eval"]["exact"]),
    ]
    qwen3_8b_score = [int(stage985["qwen3_8b"]["answer"]), int(stage985["qwen3_8b"]["exact"])]
    qwen35_9b_score = [int(stage987["qwen35_9b"]["answer"]), int(stage987["qwen35_9b"]["exact"])]
    counted_denominator = int(stage982["counted_parameter_denominator_if_fixed_comparator_allowed"])
    summary = {
        "artifact_kind": "stage988_100m_budgeted_interface_claim_gate",
        "status": "completed_claim_gate",
        "scores": {
            "stage976_bridge_free_model_owned_answer_exact": stage976_score,
            "stage981_budgeted_interface_answer_exact": stage981_score,
            "qwen3_8b_full_same_candidate_answer_exact": qwen3_8b_score,
            "qwen35_9b_full_same_candidate_answer_exact": qwen35_9b_score,
        },
        "deltas": {
            "stage981_minus_qwen3_8b": [stage981_score[0] - qwen3_8b_score[0], stage981_score[1] - qwen3_8b_score[1]],
            "stage981_minus_qwen35_9b": [stage981_score[0] - qwen35_9b_score[0], stage981_score[1] - qwen35_9b_score[1]],
            "stage981_minus_stage976": [stage981_score[0] - stage976_score[0], stage981_score[1] - stage976_score[1]],
        },
        "budget": {
            "model_parameter_count": int(stage982["model_parameter_count"]),
            "router_parameter_count": int(stage982["router_parameter_count"]),
            "fixed_pair_comparator_trainable_parameters": int(stage982["fixed_pair_comparator_trainable_parameters"]),
            "counted_parameter_denominator_if_fixed_comparator_allowed": counted_denominator,
            "approx_parameter_ratio_vs_8b": 8_000_000_000 / float(counted_denominator),
            "approx_parameter_ratio_vs_9b": 9_000_000_000 / float(counted_denominator),
        },
        "claim_gates": {
            "budgeted_100m_plus_declared_comparator_beats_local_8b_9b_same_candidate": {
                "passed": stage981_score[0] > qwen3_8b_score[0] and stage981_score[1] > qwen3_8b_score[1] and stage981_score[0] > qwen35_9b_score[0] and stage981_score[1] > qwen35_9b_score[1],
                "evidence": ["stage985", "stage987", "stage981", "stage982"],
            },
            "bridge_free_100m_beats_local_8b_9b_same_candidate": {
                "passed": stage976_score[0] > qwen3_8b_score[0] and stage976_score[1] > qwen3_8b_score[1] and stage976_score[0] > qwen35_9b_score[0] and stage976_score[1] > qwen35_9b_score[1],
                "evidence": ["stage976", "stage985", "stage987"],
            },
            "direct_generation_or_free_form_reasoning_parity": {
                "passed": False,
                "evidence": [],
            },
        },
        "allowed_claim": "On this 640-row KBPP candidate-selection benchmark, the 100M system plus a declared fixed pair-overlap/count comparator and 97-parameter router beats local Qwen3 8B and Qwen3.5 9B prompt baselines on the same candidate sets.",
        "disallowed_claims": [
            "A bridge-free 100M model beats modern 7B/9B models.",
            "The 100M model has internalized the pair-overlap/count comparator.",
            "The 100M model has free-form/direct-generation parity.",
        ],
        "next_best_steps": [
            "Decide whether the fixed pair-overlap/count comparator is an allowed primitive in the 100M system contract.",
            "If yes, package Stage981 as the accepted 100M budgeted-interface system and run broader task/domain baselines.",
            "If no, build an encoder-owned or learned equality/count comparator and require it to reproduce Stage981 without external suffix set intersection.",
            "Run an optional local 12B same-candidate prompt baseline if runtime is acceptable.",
        ],
        "decision": "The budgeted-interface result is now strong and passes local 8B/9B same-candidate baselines. The bridge-free model-owned claim remains open and should not be asserted.",
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
