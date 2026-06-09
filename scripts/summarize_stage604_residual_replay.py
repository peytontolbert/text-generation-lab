#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "runs/local/artifacts/knowledge_compression_moe_residual_10k_stage602_stage601_entity_field_balanced_replay_lr3e6_steps200"
CAND = ROOT / "runs/local/artifacts/knowledge_compression_moe_residual_10k_stage604_stage602_residual_replay_lr1e6_steps80"
OUT = ROOT / "runs/local/artifacts/stage604_residual_replay_summary.json"
DOC = ROOT / "docs/stage604_residual_replay.md"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def bits_per_param(result: dict[str, Any], kind: str) -> float:
    density = result["verified_density"]
    return density[f"{kind}_verified_bits"] / density["parameter_count"]


def op_delta(base: dict[str, Any], cand: dict[str, Any], op: str) -> dict[str, Any]:
    base_op = base["by_operation"][op]
    cand_op = cand["by_operation"][op]
    return {
        "baseline_exact_top1": base_op["top1_accuracy"],
        "candidate_exact_top1": cand_op["top1_accuracy"],
        "exact_top1_delta": cand_op["top1_accuracy"] - base_op["top1_accuracy"],
        "baseline_answer_top1": base_op["answer_top1_accuracy"],
        "candidate_answer_top1": cand_op["answer_top1_accuracy"],
        "answer_top1_delta": cand_op["answer_top1_accuracy"] - base_op["answer_top1_accuracy"],
        "baseline_mrr": base_op["mean_reciprocal_rank"],
        "candidate_mrr": cand_op["mean_reciprocal_rank"],
        "mrr_delta": cand_op["mean_reciprocal_rank"] - base_op["mean_reciprocal_rank"],
    }


def compact(result: dict[str, Any], hard: dict[str, Any]) -> dict[str, Any]:
    stats = hard["structured_key_hard_filter_stats"]
    return {
        "exact_top1": result["top1_accuracy"],
        "answer_top1": result["answer_top1_accuracy"],
        "mrr": result["mean_reciprocal_rank"],
        "exact_bits_per_param": bits_per_param(result, "exact"),
        "answer_bits_per_param": bits_per_param(result, "answer"),
        "hard_filter_exact_top1": hard["top1_accuracy"],
        "hard_filter_answer_top1": hard["answer_top1_accuracy"],
        "hard_filter_corrections": stats["top1_corrected_by_hard_filter"],
        "hard_filter_damage": stats["top1_damaged_by_hard_filter"],
        "hard_filter_masked_neural_top1": stats["neural_top1_masked_by_hard_filter"],
    }


def build_summary() -> dict[str, Any]:
    base_no = load(BASE / "retrieval_eval_stage601_entity_field_context_full_corpus_operation_gated.json")
    base_hard = load(BASE / "retrieval_eval_stage601_entity_field_context_full_corpus_operation_gated_structured_hard_filter.json")
    cand_no = load(CAND / "retrieval_eval_stage601_entity_field_context_full_corpus_operation_gated.json")
    cand_hard = load(CAND / "retrieval_eval_stage601_entity_field_context_full_corpus_operation_gated_structured_hard_filter.json")
    manifest = load(CAND / "agentkernel_lite_encdec_manifest.json")
    residual_manifest = load(ROOT / "runs/local/tmp/pocketpal_stage604_stage602_residual_replay_seed461/agentkernel_lite_encdec_dataset_manifest.json")
    return {
        "artifact_kind": "stage604_residual_replay_summary",
        "candidate": "stage604_stage602_residual_replay_lr1e6_steps80",
        "bundle_dir": str(CAND.relative_to(ROOT)),
        "checkpoint": str((CAND / "checkpoints/step_00000080.pt").relative_to(ROOT)),
        "train_dataset_manifest": "runs/local/tmp/pocketpal_stage604_stage602_residual_replay_seed461/agentkernel_lite_encdec_dataset_manifest.json",
        "eval_manifest": "runs/local/tmp/pocketpal_stage601_entity_field_context_seed461/agentkernel_lite_encdec_dataset_manifest.json",
        "dataset": {
            "missed_eval_source_ids": residual_manifest["missed_eval_source_ids"],
            "near_miss_eval_source_ids": residual_manifest["near_miss_eval_source_ids"],
            "repeat_failures": residual_manifest["repeat_failures"],
            "repeat_near_misses": residual_manifest["repeat_near_misses"],
            "mixed_original_train": residual_manifest["mixed_original_train"],
            "train_examples": residual_manifest["train_examples"],
        },
        "training": {
            "init_from": str((BASE / "checkpoints/step_00000200.pt").relative_to(ROOT)),
            "steps": 80,
            "cumulative_steps": 3880,
            "learning_rate": 1e-6,
            "eval_loss_step_80": manifest["training_summary"]["eval_history"][-1]["eval_loss"],
        },
        "baseline_stage602": compact(base_no, base_hard),
        "candidate_stage604": compact(cand_no, cand_hard),
        "deltas_vs_stage602": {
            "exact_top1": cand_no["top1_accuracy"] - base_no["top1_accuracy"],
            "answer_top1": cand_no["answer_top1_accuracy"] - base_no["answer_top1_accuracy"],
            "mrr": cand_no["mean_reciprocal_rank"] - base_no["mean_reciprocal_rank"],
            "exact_bits_per_param": bits_per_param(cand_no, "exact") - bits_per_param(base_no, "exact"),
            "answer_bits_per_param": bits_per_param(cand_no, "answer") - bits_per_param(base_no, "answer"),
            "hard_filter_corrections": cand_hard["structured_key_hard_filter_stats"]["top1_corrected_by_hard_filter"]
            - base_hard["structured_key_hard_filter_stats"]["top1_corrected_by_hard_filter"],
        },
        "operation_deltas": {
            "direct_fact": op_delta(base_no, cand_no, "direct_fact"),
            "entity_context": op_delta(base_no, cand_no, "entity_context"),
            "rule_case_intersection_member": op_delta(base_no, cand_no, "rule_case_intersection_member"),
            "set_intersection_member": op_delta(base_no, cand_no, "set_intersection_member"),
        },
        "decision": "rejected_residual_replay_too_blunt_keep_stage602_best",
        "finding": (
            "Naive residual replay from all Stage602 exact misses does not improve the field surface. It lowers no-filter "
            "exact/answer and increases hard-filter corrections, mostly by giving back direct_fact margin while leaving "
            "entity_context unchanged. Future residual work should filter to answer misses with high rank margin or repair "
            "one operation at a time with tighter stopping."
        ),
    }


def write_doc(summary: dict[str, Any]) -> None:
    base = summary["baseline_stage602"]
    cand = summary["candidate_stage604"]
    doc = f"""# Stage604 Residual Replay

Artifact: `runs/local/artifacts/stage604_residual_replay_summary.json`

## Result

Stage604 continued Stage602 for `80` steps on residual replay from Stage602 exact misses plus the Stage602 train mix.

No-filter exact/answer moved from `{base['exact_top1']}` / `{base['answer_top1']}` to `{cand['exact_top1']}` / `{cand['answer_top1']}`.

Hard-filter corrections moved from `{base['hard_filter_corrections']}` to `{cand['hard_filter_corrections']}`.

## Decision

`rejected_residual_replay_too_blunt_keep_stage602_best`

## Finding

{summary['finding']}
"""
    DOC.write_text(doc, encoding="utf-8")


def main() -> None:
    summary = build_summary()
    OUT.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_doc(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
