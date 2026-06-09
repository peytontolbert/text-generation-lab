#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "runs/local/artifacts/knowledge_compression_moe_residual_10k_stage525_stage502_rule_replay_lr1e4_steps300"
CANDIDATE = ROOT / "runs/local/artifacts/knowledge_compression_moe_residual_10k_stage594_stage525_residual_answer_equiv_lr1e5_steps80"
STAGE525_HISTORICAL_BATCH_EXACT_TOP1 = 0.9952107279693486
STAGE525_HISTORICAL_BATCH_ANSWER_TOP1 = 0.9971264367816092
STAGE525_HISTORICAL_BITS_PER_PARAM = 1.410325570323004


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def metric_delta(candidate: dict[str, Any], baseline: dict[str, Any], key: str) -> float | None:
    if candidate.get(key) is None or baseline.get(key) is None:
        return None
    return float(candidate[key]) - float(baseline[key])


def by_op_delta(candidate: dict[str, Any], baseline: dict[str, Any], op: str) -> dict[str, Any]:
    cand = candidate["by_operation"].get(op, {})
    base = baseline["by_operation"].get(op, {})
    cand_answer = cand.get("answer_top1_accuracy")
    base_answer = base.get("answer_top1_accuracy")
    return {
        "candidate_exact_top1": cand.get("top1_accuracy"),
        "baseline_exact_top1": base.get("top1_accuracy"),
        "exact_top1_delta": (float(cand.get("top1_accuracy", 0.0)) - float(base.get("top1_accuracy", 0.0))) if cand and base else None,
        "candidate_answer_top1": cand_answer,
        "baseline_answer_top1": base_answer,
        "answer_top1_delta": (float(cand_answer) - float(base_answer)) if cand_answer is not None and base_answer is not None else None,
        "evaluated_pairs": cand.get("evaluated_pairs", base.get("evaluated_pairs")),
    }


def build_summary() -> dict[str, Any]:
    baseline = {
        "batch_local": load(BASE / "retrieval_eval_full_answer_equiv_refresh.json"),
        "operation_gated": load(BASE / "retrieval_eval_full_operation_gated_answer_equiv_refresh.json"),
    }
    candidate = {
        "batch_local": load(CANDIDATE / "retrieval_eval_full.json"),
        "operation_gated": load(CANDIDATE / "retrieval_eval_full_operation_gated.json"),
        "strict_full_corpus_operation_gated": load(CANDIDATE / "retrieval_eval_full_corpus_operation_gated.json"),
        "manifest": load(CANDIDATE / "agentkernel_lite_encdec_manifest.json"),
    }

    comparisons = {}
    for name in ("batch_local", "operation_gated"):
        cand = candidate[name]
        base = baseline[name]
        baseline_answer = base.get("answer_top1_accuracy")
        comparisons[name] = {
            "candidate_exact_top1": cand["top1_accuracy"],
            "baseline_exact_top1": base["top1_accuracy"],
            "exact_top1_delta": metric_delta(cand, base, "top1_accuracy"),
            "candidate_answer_top1": cand.get("answer_top1_accuracy"),
            "baseline_answer_top1": baseline_answer,
            "answer_top1_delta": (float(cand["answer_top1_accuracy"]) - float(baseline_answer)) if cand.get("answer_top1_accuracy") is not None and baseline_answer is not None else None,
            "candidate_mrr": cand["mean_reciprocal_rank"],
            "baseline_mrr": base["mean_reciprocal_rank"],
            "mrr_delta": metric_delta(cand, base, "mean_reciprocal_rank"),
            "candidate_exact_bits_per_param": cand["verified_density"]["exact_verified_bits"] / cand["verified_density"]["parameter_count"],
            "candidate_answer_bits_per_param": cand["verified_density"]["answer_verified_bits"] / cand["verified_density"]["parameter_count"],
        }

    target_ops = [
        "set_count",
        "set_member",
        "set_intersection_count",
        "set_intersection_member",
        "rule_case_count",
        "rule_case_member",
        "rule_case_intersection_count",
        "rule_case_intersection_member",
    ]
    op_deltas = {
        op: by_op_delta(candidate["operation_gated"], baseline["operation_gated"], op)
        for op in target_ops
    }

    strict = candidate["strict_full_corpus_operation_gated"]
    manifest = candidate["manifest"]
    eval_history = manifest.get("training_summary", {}).get("eval_history", [])
    summary = {
        "artifact_kind": "stage594_residual_answer_contrast_summary",
        "baseline": "stage525_16k_rule_replay_from_stage502_2400step",
        "candidate": "stage594_stage525_residual_answer_equiv_lr1e5_steps80",
        "bundle_dir": str(CANDIDATE.relative_to(ROOT)),
        "checkpoint": str((CANDIDATE / "checkpoints/step_00000080.pt").relative_to(ROOT)),
        "dataset_manifest": "runs/local/tmp/pocketpal_stage594_stage525_operation_gated_residual_only_seed461/agentkernel_lite_encdec_dataset_manifest.json",
        "evaluation_manifest": "runs/local/tmp/pocketpal_stage521_stage497_rule_replay_seed461/agentkernel_lite_encdec_dataset_manifest.json",
        "training": {
            "init_from": str((BASE / "checkpoints/step_00000300.pt").relative_to(ROOT)),
            "steps": 80,
            "cumulative_density_steps": 2480,
            "learning_rate": 1e-5,
            "residual_train_examples": 140,
            "missed_eval_source_ids": 7,
            "near_miss_eval_source_ids": 7,
            "retrieval_answer_contrastive_weight": 0.05,
            "retrieval_answer_contrastive_operation_ids": [6, 7, 8, 9, 11, 12, 13, 14],
            "eval_loss_step_80": eval_history[-1]["eval_loss"] if eval_history else None,
        },
        "comparisons": comparisons,
        "target_operation_deltas": op_deltas,
        "strict_full_corpus_operation_gated": {
            "exact_top1": strict["top1_accuracy"],
            "answer_top1": strict["answer_top1_accuracy"],
            "mrr": strict["mean_reciprocal_rank"],
            "exact_bits_per_param": strict["verified_density"]["exact_verified_bits"] / strict["verified_density"]["parameter_count"],
            "answer_bits_per_param": strict["verified_density"]["answer_verified_bits"] / strict["verified_density"]["parameter_count"],
        },
        "historical_frontier_reference": {
            "stage525_historical_batch_exact_top1": STAGE525_HISTORICAL_BATCH_EXACT_TOP1,
            "stage525_historical_batch_answer_top1": STAGE525_HISTORICAL_BATCH_ANSWER_TOP1,
            "stage525_historical_bits_per_param": STAGE525_HISTORICAL_BITS_PER_PARAM,
            "note": "The current evaluator refresh produces lower Stage525 exact/answer than the established historical artifact, so Stage594 is judged as a current-evaluator micro-gain but not a new historical raw-density frontier.",
        },
        "decision": "current_evaluator_micro_gain_not_new_historical_frontier",
        "finding": (
            "Residual-only answer-equivalence contrast is less destructive than broad Stage593 and gives a tiny current-evaluator "
            "gain over a refreshed Stage525 baseline. The gain is only one to two eval rows, and it still does not supersede the "
            "established historical Stage525 raw-density frontier. Treat this as evidence that residual-only contrast can polish "
            "specific residuals, not as a robust KBPP lever. The next lever should be deterministic answer-equivalent filtering, "
            "eval-time structured correction, or higher-entropy target schemas."
        ),
    }
    return summary


def write_doc(summary: dict[str, Any]) -> None:
    batch = summary["comparisons"]["batch_local"]
    gated = summary["comparisons"]["operation_gated"]
    strict = summary["strict_full_corpus_operation_gated"]
    historical = summary["historical_frontier_reference"]
    doc = f"""# Stage594 Residual Answer-Equivalence Contrast

Artifact: `runs/local/artifacts/stage594_residual_answer_contrast_summary.json`

## Result

Stage594 continued Stage525 for `80` steps on only the operation-gated residual set: `140` residual examples from `7` misses plus `7` near-miss eval source ids.

Training kept answer-level contrastive loss on count/member operation families:

`--retrieval-answer-contrastive-weight 0.05 --retrieval-answer-contrastive-operation-ids 6,7,8,9,11,12,13,14`

Against a refreshed current-evaluator Stage525 baseline, batch-local exact/answer moved from `{batch['baseline_exact_top1']}` / `{batch['baseline_answer_top1']}` to `{batch['candidate_exact_top1']}` / `{batch['candidate_answer_top1']}`.

Against the same refreshed baseline, operation-gated exact/answer moved from `{gated['baseline_exact_top1']}` / `{gated['baseline_answer_top1']}` to `{gated['candidate_exact_top1']}` / `{gated['candidate_answer_top1']}`.

Strict full-corpus operation-gated exact/answer: `{strict['exact_top1']}` / `{strict['answer_top1']}`.

The established historical Stage525 raw-density artifact remains higher: exact/answer `{historical['stage525_historical_batch_exact_top1']}` / `{historical['stage525_historical_batch_answer_top1']}`, bits/param `{historical['stage525_historical_bits_per_param']}`.

## Decision

`current_evaluator_micro_gain_not_new_historical_frontier`

## Finding

{summary['finding']}
"""
    (ROOT / "docs/stage594_residual_answer_contrast.md").write_text(doc, encoding="utf-8")


def main() -> None:
    summary = build_summary()
    output = ROOT / "runs/local/artifacts/stage594_residual_answer_contrast_summary.json"
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_doc(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
