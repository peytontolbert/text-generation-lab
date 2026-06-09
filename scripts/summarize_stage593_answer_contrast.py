#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "runs/local/artifacts/knowledge_compression_moe_residual_10k_stage525_stage502_rule_replay_lr1e4_steps300"
CANDIDATE = ROOT / "runs/local/artifacts/knowledge_compression_moe_residual_10k_stage593_stage525_answer_equiv_count_member_lr5e5_steps300"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def metric_delta(candidate: dict[str, Any], baseline: dict[str, Any], key: str) -> float | None:
    if candidate.get(key) is None or baseline.get(key) is None:
        return None
    return float(candidate[key]) - float(baseline[key])


def build_summary() -> dict[str, Any]:
    baseline = {
        "batch_local": load(BASE / "retrieval_eval_full.json"),
        "operation_gated": load(BASE / "retrieval_eval_full_operation_gated.json"),
    }
    candidate = {
        "batch_local": load(CANDIDATE / "retrieval_eval_full.json"),
        "operation_gated": load(CANDIDATE / "retrieval_eval_full_operation_gated.json"),
        "strict_full_corpus_operation_gated": load(CANDIDATE / "retrieval_eval_full_corpus_operation_gated.json"),
        "manifest": load(CANDIDATE / "agentkernel_lite_encdec_manifest.json"),
    }
    comparisons = {}
    for name in ("batch_local", "operation_gated"):
        comparisons[name] = {
            "candidate_exact_top1": candidate[name]["top1_accuracy"],
            "baseline_exact_top1": baseline[name]["top1_accuracy"],
            "exact_top1_delta": metric_delta(candidate[name], baseline[name], "top1_accuracy"),
            "candidate_answer_top1": candidate[name].get("answer_top1_accuracy"),
            "baseline_answer_top1": baseline[name].get("answer_top1_accuracy"),
            "candidate_mrr": candidate[name]["mean_reciprocal_rank"],
            "baseline_mrr": baseline[name]["mean_reciprocal_rank"],
            "mrr_delta": metric_delta(candidate[name], baseline[name], "mean_reciprocal_rank"),
        }

    target_ops = ["set_count", "set_member", "set_intersection_count", "set_intersection_member", "rule_case_count", "rule_case_member", "rule_case_intersection_count", "rule_case_intersection_member"]
    op_deltas = {}
    for op in target_ops:
        cand = candidate["operation_gated"]["by_operation"].get(op, {})
        base = baseline["operation_gated"]["by_operation"].get(op, {})
        op_deltas[op] = {
            "candidate_exact_top1": cand.get("top1_accuracy"),
            "baseline_exact_top1": base.get("top1_accuracy"),
            "exact_top1_delta": (float(cand.get("top1_accuracy", 0.0)) - float(base.get("top1_accuracy", 0.0))) if cand and base else None,
            "candidate_answer_top1": cand.get("answer_top1_accuracy"),
            "evaluated_pairs": cand.get("evaluated_pairs", base.get("evaluated_pairs")),
        }

    strict = candidate["strict_full_corpus_operation_gated"]
    summary = {
        "artifact_kind": "stage593_answer_equivalence_contrast_summary",
        "baseline": "stage525_16k_rule_replay_from_stage502_2400step",
        "candidate": "stage593_stage525_answer_equiv_count_member_lr5e5_steps300",
        "bundle_dir": str(CANDIDATE.relative_to(ROOT)),
        "checkpoint": str((CANDIDATE / "checkpoints/step_00000300.pt").relative_to(ROOT)),
        "dataset_manifest": "runs/local/tmp/pocketpal_stage521_stage497_rule_replay_seed461/agentkernel_lite_encdec_dataset_manifest.json",
        "training": {
            "init_from": str((BASE / "checkpoints/step_00000300.pt").relative_to(ROOT)),
            "steps": 300,
            "cumulative_steps": 2700,
            "learning_rate": 5e-5,
            "retrieval_answer_contrastive_weight": 0.05,
            "retrieval_answer_contrastive_operation_ids": [6, 7, 8, 9, 11, 12, 13, 14],
            "eval_loss_step_300": candidate["manifest"]["training_summary"]["eval_history"][-1]["eval_loss"],
        },
        "comparisons": comparisons,
        "target_operation_deltas": op_deltas,
        "strict_full_corpus_operation_gated": {
            "exact_top1": strict["top1_accuracy"],
            "answer_top1": strict["answer_top1_accuracy"],
            "mrr": strict["mean_reciprocal_rank"],
        },
        "decision": "rejected_as_new_best",
        "finding": (
            "Answer-equivalence contrast on count/member operation families improves some targeted answer-equivalent slices, "
            "but it damages global binding and direct/entity-context retrieval. The loss route is too broad even at weight 0.05; "
            "next work should use narrower residual-only examples or deterministic filtering rather than full-dataset answer contrast."
        ),
    }
    return summary


def write_doc(summary: dict[str, Any]) -> None:
    batch = summary["comparisons"]["batch_local"]
    gated = summary["comparisons"]["operation_gated"]
    strict = summary["strict_full_corpus_operation_gated"]
    doc = f"""# Stage593 Answer-Equivalence Contrast

Artifact: `runs/local/artifacts/stage593_answer_equivalence_contrast_summary.json`

## Result

Stage593 continued Stage525 for `300` steps with answer-level contrastive loss on count/member operation families:

`--retrieval-answer-contrastive-weight 0.05 --retrieval-answer-contrastive-operation-ids 6,7,8,9,11,12,13,14`

Batch-local exact top1 moved from `{batch['baseline_exact_top1']}` to `{batch['candidate_exact_top1']}`.

Operation-gated exact top1 moved from `{gated['baseline_exact_top1']}` to `{gated['candidate_exact_top1']}`.

Strict full-corpus operation-gated exact/answer: `{strict['exact_top1']}` / `{strict['answer_top1']}`.

## Decision

`rejected_as_new_best`

## Finding

{summary['finding']}
"""
    (ROOT / "docs/stage593_answer_equivalence_contrast.md").write_text(doc, encoding="utf-8")


def main() -> None:
    summary = build_summary()
    output = ROOT / "runs/local/artifacts/stage593_answer_equivalence_contrast_summary.json"
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_doc(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
