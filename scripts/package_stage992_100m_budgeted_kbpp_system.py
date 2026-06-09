#!/usr/bin/env python3
"""Package the accepted Stage981 budgeted-interface 100M KBPP system manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage981", type=Path, default=Path("runs/local/artifacts/stage981_100m_pair_interface_hybrid_summary.json"))
    parser.add_argument("--stage982", type=Path, default=Path("runs/local/artifacts/stage982_pair_comparator_budget_audit_summary.json"))
    parser.add_argument("--stage991", type=Path, default=Path("runs/local/artifacts/stage991_100m_budgeted_interface_extended_baseline_claim_gate_summary.json"))
    parser.add_argument("--output-json", type=Path, default=Path("runs/local/artifacts/stage992_100m_budgeted_kbpp_system_manifest.json"))
    args = parser.parse_args()

    stage981 = _read(args.stage981)
    stage982 = _read(args.stage982)
    stage991 = _read(args.stage991)
    manifest = {
        "artifact_kind": "stage992_100m_budgeted_kbpp_system_manifest",
        "status": "packaged_budgeted_interface_system",
        "system_name": "stage981_100m_budgeted_pair_interface_kbpp_system",
        "model_bundle": stage981["bundle_dir"],
        "scorer_script": "scripts/score_stage981_100m_pair_interface_hybrid.py",
        "targets_jsonl": stage981["targets_jsonl"],
        "prediction_export": "runs/local/artifacts/stage981_100m_pair_interface_hybrid_predictions.jsonl",
        "parameter_budget": {
            "model_parameter_count": stage982["model_parameter_count"],
            "router_parameter_count": stage982["router_parameter_count"],
            "fixed_pair_comparator_trainable_parameters": stage982["fixed_pair_comparator_trainable_parameters"],
            "counted_parameter_denominator_if_fixed_comparator_allowed": stage982["counted_parameter_denominator_if_fixed_comparator_allowed"],
        },
        "declared_primitives": {
            "fixed_pair_overlap_count": {
                "status": "declared_fixed_interface_primitive",
                "trainable_parameters": 0,
                "inputs": ["query qpair suffix set", "candidate dpair suffix set"],
                "operation": "count exact shared-anchor suffix intersections",
                "used_for_operations": [
                    op
                    for op, policy in stage981["policy_by_operation"].items()
                    if policy == "stage968_counted_pair_overlap"
                ],
                "eval_compute_audit": stage982["split_comparator_stats"]["eval"],
            },
            "pair_arity_router": {
                "status": "trainable_router",
                "trainable_parameters": stage982["router_parameter_count"],
                "router_state": stage981["router_state"],
                "selected_arities": stage981["selected_arities"],
                "threshold": stage981["threshold"],
            },
        },
        "operation_policy": stage981["policy_by_operation"],
        "score": {
            "eval_answer": stage981["split_scores"]["eval"]["answer"],
            "eval_exact": stage981["split_scores"]["eval"]["exact"],
            "implied_full_answer_exact": stage981["implied_full_answer_exact"],
            "by_operation": stage981["split_scores"]["eval"]["by_operation"],
        },
        "baseline_evidence": {
            "qwen3_8b_full_same_candidate_answer_exact": stage991["scores"]["qwen3_8b_full_same_candidate_answer_exact"],
            "qwen35_9b_full_same_candidate_answer_exact": stage991["scores"]["qwen35_9b_full_same_candidate_answer_exact"],
            "gemma3_12b_full_same_candidate_answer_exact": stage991["scores"]["gemma3_12b_full_same_candidate_answer_exact"],
            "stage981_minus_qwen3_8b": stage991["deltas"]["stage981_minus_qwen3_8b"],
            "stage981_minus_qwen35_9b": stage991["deltas"]["stage981_minus_qwen35_9b"],
            "stage981_minus_gemma3_12b": stage991["deltas"]["stage981_minus_gemma3_12b"],
        },
        "accepted_claim": stage991["allowed_claim"],
        "rejected_claims": stage991["disallowed_claims"],
        "reproduction_commands": {
            "score_stage981": (
                "/home/peyton/miniconda3/envs/ai/bin/python "
                "scripts/score_stage981_100m_pair_interface_hybrid.py "
                "--device cuda "
                "--output-json runs/local/artifacts/stage981_100m_pair_interface_hybrid_summary.json "
                "--predictions-jsonl runs/local/artifacts/stage981_100m_pair_interface_hybrid_predictions.jsonl"
            ),
            "audit_stage982": (
                "/home/peyton/miniconda3/envs/ai/bin/python "
                "scripts/audit_stage982_pair_comparator_budget.py "
                "--output-json runs/local/artifacts/stage982_pair_comparator_budget_audit_summary.json"
            ),
            "build_stage991": "Derived from Stage988 plus Stage990 comparison artifact.",
        },
        "next_best_steps": stage991["next_best_steps"],
        "decision": (
            "Packaged as the accepted 100M budgeted-interface KBPP system. "
            "This package intentionally does not claim bridge-free model-owned comparator internalization."
        ),
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
