#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "runs/local/artifacts/knowledge_compression_moe_residual_10k_stage602_stage601_entity_field_balanced_replay_lr3e6_steps200"
CAND = ROOT / "runs/local/artifacts/knowledge_compression_moe_residual_10k_stage603_stage602_rule_intersection_repair_lr2e6_steps150"
OUT = ROOT / "runs/local/artifacts/stage603_rule_intersection_repair_summary.json"
DOC = ROOT / "docs/stage603_rule_intersection_repair.md"


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
    dataset = load(ROOT / "runs/local/artifacts/stage603_rule_intersection_repair_dataset.json")
    return {
        "artifact_kind": "stage603_rule_intersection_repair_summary",
        "candidate": "stage603_stage602_rule_intersection_repair_lr2e6_steps150",
        "bundle_dir": str(CAND.relative_to(ROOT)),
        "checkpoint": str((CAND / "checkpoints/step_00000150.pt").relative_to(ROOT)),
        "train_dataset_manifest": "runs/local/tmp/pocketpal_stage603_rule_intersection_repair_seed461/agentkernel_lite_encdec_dataset_manifest.json",
        "eval_manifest": "runs/local/tmp/pocketpal_stage601_entity_field_context_seed461/agentkernel_lite_encdec_dataset_manifest.json",
        "dataset": {
            "target_replay_ops": dataset["target_replay_ops"],
            "added_train_examples": dataset["added_train_examples"],
            "added_train_examples_by_op": dataset["added_train_examples_by_op"],
            "train_examples_after": dataset["train_examples_after"],
        },
        "training": {
            "init_from": str((BASE / "checkpoints/step_00000200.pt").relative_to(ROOT)),
            "steps": 150,
            "cumulative_steps": 3950,
            "learning_rate": 2e-6,
            "retrieval_value_anchor_weight": 0.01,
            "retrieval_value_anchor_operation_ids": [10],
            "eval_loss_step_150": manifest["training_summary"]["eval_history"][-1]["eval_loss"],
        },
        "baseline_stage602": compact(base_no, base_hard),
        "candidate_stage603": compact(cand_no, cand_hard),
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
            "rule_case_intersection_count": op_delta(base_no, cand_no, "rule_case_intersection_count"),
            "rule_case_intersection_member": op_delta(base_no, cand_no, "rule_case_intersection_member"),
            "set_intersection_member": op_delta(base_no, cand_no, "set_intersection_member"),
        },
        "decision": "neutral_rule_repair_tradeoff_keep_stage602_as_field_surface_best",
        "finding": (
            "Rule-intersection replay repairs rule_case_intersection_member exact/answer but does not improve global exact, "
            "answer, or hard-filter corrections over Stage602, and it gives back a small direct_fact margin. Stage602 remains "
            "the cleaner Stage601 field-surface best. The next gain likely needs residual-only replay from Stage602 details, "
            "not another broad operation replay."
        ),
    }


def write_doc(summary: dict[str, Any]) -> None:
    base = summary["baseline_stage602"]
    cand = summary["candidate_stage603"]
    rmember = summary["operation_deltas"]["rule_case_intersection_member"]
    direct = summary["operation_deltas"]["direct_fact"]
    doc = f"""# Stage603 Rule Intersection Repair

Artifact: `runs/local/artifacts/stage603_rule_intersection_repair_summary.json`

## Result

Stage603 continued Stage602 for `150` steps with one replay copy of `rule_case_intersection_count` and `rule_case_intersection_member`.

No-filter exact/answer stayed `{cand['exact_top1']}` / `{cand['answer_top1']}` versus Stage602 `{base['exact_top1']}` / `{base['answer_top1']}`.

Hard-filter corrections stayed `{cand['hard_filter_corrections']}` with `{cand['hard_filter_damage']}` damage.

- `rule_case_intersection_member`: exact/answer `{rmember['candidate_exact_top1']}` / `{rmember['candidate_answer_top1']}`; exact delta `{rmember['exact_top1_delta']}`
- `direct_fact`: exact/answer `{direct['candidate_exact_top1']}` / `{direct['candidate_answer_top1']}`; exact delta `{direct['exact_top1_delta']}`

## Decision

`neutral_rule_repair_tradeoff_keep_stage602_as_field_surface_best`

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
