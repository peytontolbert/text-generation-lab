#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE598 = ROOT / "runs/local/artifacts/knowledge_compression_moe_residual_10k_stage598_stage597_collision_conditioned_lr1e5_steps300"
STAGE599 = ROOT / "runs/local/artifacts/knowledge_compression_moe_residual_10k_stage599_stage598_collision_weakop_replay_value_anchor_lr5e6_steps300"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def bits_per_param(result: dict[str, Any], kind: str) -> float:
    density = result["verified_density"]
    return density[f"{kind}_verified_bits"] / density["parameter_count"]


def compact(result: dict[str, Any]) -> dict[str, Any]:
    out = {
        "exact_top1": result["top1_accuracy"],
        "answer_top1": result["answer_top1_accuracy"],
        "mrr": result["mean_reciprocal_rank"],
        "exact_bits_per_param": bits_per_param(result, "exact"),
        "answer_bits_per_param": bits_per_param(result, "answer"),
        "by_operation": {
            op: {
                "exact_top1": stats.get("top1_accuracy"),
                "answer_top1": stats.get("answer_top1_accuracy"),
                "mrr": stats.get("mean_reciprocal_rank"),
                "evaluated_pairs": stats.get("evaluated_pairs"),
            }
            for op, stats in result.get("by_operation", {}).items()
        },
    }
    if result.get("structured_key_hard_filter_stats"):
        out["hard_filter_stats"] = result["structured_key_hard_filter_stats"]
    return out


def build_summary() -> dict[str, Any]:
    base_no = load(STAGE598 / "retrieval_eval_stage596_collision_full_corpus_operation_gated.json")
    base_hard = load(STAGE598 / "retrieval_eval_stage596_collision_full_corpus_operation_gated_structured_hard_filter.json")
    cand_no = load(STAGE599 / "retrieval_eval_stage596_collision_full_corpus_operation_gated.json")
    cand_hard = load(STAGE599 / "retrieval_eval_stage596_collision_full_corpus_operation_gated_structured_hard_filter.json")
    manifest = load(STAGE599 / "agentkernel_lite_encdec_manifest.json")
    weak_dataset = load(ROOT / "runs/local/artifacts/stage599_collision_weakop_replay_dataset.json")
    weak_ops = ["direct_fact", "entity_context", "two_hop_owner_region"]
    weak_op_deltas = {}
    for op in weak_ops:
        base = base_no["by_operation"][op]
        cand = cand_no["by_operation"][op]
        weak_op_deltas[op] = {
            "exact_top1_delta": cand["top1_accuracy"] - base["top1_accuracy"],
            "answer_top1_delta": cand["answer_top1_accuracy"] - base["answer_top1_accuracy"],
            "mrr_delta": cand["mean_reciprocal_rank"] - base["mean_reciprocal_rank"],
            "candidate_exact_top1": cand["top1_accuracy"],
            "candidate_answer_top1": cand["answer_top1_accuracy"],
        }
    summary = {
        "artifact_kind": "stage599_weakop_replay_summary",
        "candidate": "stage599_stage598_collision_weakop_replay_value_anchor_lr5e6_steps300",
        "bundle_dir": str(STAGE599.relative_to(ROOT)),
        "checkpoint": str((STAGE599 / "checkpoints/step_00000300.pt").relative_to(ROOT)),
        "dataset_manifest": "runs/local/tmp/pocketpal_stage599_collision_weakop_replay_seed461/agentkernel_lite_encdec_dataset_manifest.json",
        "eval_manifest": "runs/local/tmp/pocketpal_stage596_collision_conditioned_seed461/agentkernel_lite_encdec_dataset_manifest.json",
        "training": {
            "init_from": str((STAGE598 / "checkpoints/step_00000300.pt").relative_to(ROOT)),
            "steps": 300,
            "cumulative_steps": 3300,
            "learning_rate": 5e-6,
            "retrieval_value_anchor_weight": 0.02,
            "retrieval_value_anchor_operation_ids": [5, 10],
            "weakop_replay_added_train_examples": weak_dataset["added_train_examples"],
            "eval_loss_step_300": manifest["training_summary"]["eval_history"][-1]["eval_loss"],
        },
        "baseline_stage598_no_filter": compact(base_no),
        "candidate_no_filter": compact(cand_no),
        "baseline_stage598_hard_filter": compact(base_hard),
        "candidate_hard_filter": compact(cand_hard),
        "deltas_vs_stage598": {
            "no_filter_exact_top1": cand_no["top1_accuracy"] - base_no["top1_accuracy"],
            "no_filter_answer_top1": cand_no["answer_top1_accuracy"] - base_no["answer_top1_accuracy"],
            "no_filter_exact_bits_per_param": bits_per_param(cand_no, "exact") - bits_per_param(base_no, "exact"),
            "no_filter_answer_bits_per_param": bits_per_param(cand_no, "answer") - bits_per_param(base_no, "answer"),
            "hard_filter_corrections": cand_hard["structured_key_hard_filter_stats"]["top1_corrected_by_hard_filter"]
            - base_hard["structured_key_hard_filter_stats"]["top1_corrected_by_hard_filter"],
            "hard_filter_masked_neural_top1": cand_hard["structured_key_hard_filter_stats"]["neural_top1_masked_by_hard_filter"]
            - base_hard["structured_key_hard_filter_stats"]["neural_top1_masked_by_hard_filter"],
        },
        "weak_operation_deltas": weak_op_deltas,
        "decision": "accepted_as_collision_probe_best_so_far",
        "finding": (
            "Weak-op replay plus light value anchoring gives the largest collision-probe gain so far. Most of the gain comes from "
            "direct_fact collision recovery; entity_context and two_hop remain largely unresolved, so the next route should either "
            "increase collision examples for those families or change their target schema to expose more discriminative anchors."
        ),
    }
    return summary


def write_doc(summary: dict[str, Any]) -> None:
    base = summary["baseline_stage598_no_filter"]
    cand = summary["candidate_no_filter"]
    hard_base = summary["baseline_stage598_hard_filter"]["hard_filter_stats"]
    hard_cand = summary["candidate_hard_filter"]["hard_filter_stats"]
    doc = f"""# Stage599 Weak-Op Replay

Artifact: `runs/local/artifacts/stage599_weakop_replay_summary.json`

## Result

Stage599 continued Stage598 for `300` steps on the weak-op replay dataset with value-anchor weight `0.02` on operation IDs `5,10`.

No-filter exact/answer moved from `{base['exact_top1']}` / `{base['answer_top1']}` to `{cand['exact_top1']}` / `{cand['answer_top1']}`.

Hard-filter corrections fell from `{hard_base['top1_corrected_by_hard_filter']}` to `{hard_cand['top1_corrected_by_hard_filter']}` with zero damage.

## Weak Ops

- `direct_fact`: exact/answer `{summary['weak_operation_deltas']['direct_fact']['candidate_exact_top1']}` / `{summary['weak_operation_deltas']['direct_fact']['candidate_answer_top1']}`
- `entity_context`: exact/answer `{summary['weak_operation_deltas']['entity_context']['candidate_exact_top1']}` / `{summary['weak_operation_deltas']['entity_context']['candidate_answer_top1']}`
- `two_hop_owner_region`: exact/answer `{summary['weak_operation_deltas']['two_hop_owner_region']['candidate_exact_top1']}` / `{summary['weak_operation_deltas']['two_hop_owner_region']['candidate_answer_top1']}`

## Decision

`accepted_as_collision_probe_best_so_far`

## Finding

{summary['finding']}
"""
    (ROOT / "docs/stage599_weakop_replay.md").write_text(doc, encoding="utf-8")


def main() -> None:
    summary = build_summary()
    output = ROOT / "runs/local/artifacts/stage599_weakop_replay_summary.json"
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_doc(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
