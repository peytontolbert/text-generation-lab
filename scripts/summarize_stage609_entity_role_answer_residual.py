#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "runs/local/artifacts/knowledge_compression_moe_residual_10k_stage602_stage601_entity_field_balanced_replay_lr3e6_steps200"
CAND = ROOT / "runs/local/artifacts/knowledge_compression_moe_residual_10k_stage609_stage602_entity_role_answer_residual_lr5e7_steps80"
DATASET = ROOT / "runs/local/artifacts/stage609_entity_role_answer_residual_dataset.json"
OUT = ROOT / "runs/local/artifacts/stage609_entity_role_answer_residual_summary.json"
DOC = ROOT / "docs/stage609_entity_role_answer_residual.md"


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
    base_no = load(BASE / "retrieval_eval_stage607_entity_field_role_tokens_full_corpus_operation_gated.json")
    base_hard = load(BASE / "retrieval_eval_stage607_entity_field_role_tokens_full_corpus_operation_gated_structured_hard_filter.json")
    cand_no = load(CAND / "retrieval_eval_stage607_entity_field_role_tokens_full_corpus_operation_gated.json")
    cand_hard = load(CAND / "retrieval_eval_stage607_entity_field_role_tokens_full_corpus_operation_gated_structured_hard_filter.json")
    manifest = load(CAND / "agentkernel_lite_encdec_manifest.json")
    dataset = load(DATASET)
    return {
        "artifact_kind": "stage609_entity_role_answer_residual_summary",
        "candidate": "stage609_stage602_entity_role_answer_residual_lr5e7_steps80",
        "bundle_dir": str(CAND.relative_to(ROOT)),
        "checkpoint": str((CAND / "checkpoints/step_00000080.pt").relative_to(ROOT)),
        "dataset_manifest": "runs/local/tmp/pocketpal_stage609_entity_role_answer_residual_seed461/agentkernel_lite_encdec_dataset_manifest.json",
        "dataset": {
            "answer_miss_source_ids": dataset["answer_miss_source_ids"],
            "near_miss_source_ids": dataset["near_miss_source_ids"],
            "repeat_failures": dataset["repeat_failures"],
            "repeat_near_misses": dataset["repeat_near_misses"],
            "train_examples_before": dataset["train_examples_before"],
            "train_examples_after": dataset["train_examples_after"],
        },
        "training": {
            "init_from": str((BASE / "checkpoints/step_00000200.pt").relative_to(ROOT)),
            "steps": 80,
            "cumulative_steps": 3880,
            "learning_rate": 5e-7,
            "retrieval_answer_contrastive_weight": 0.01,
            "retrieval_answer_contrastive_operation_ids": [10],
            "eval_loss_step_80": manifest["training_summary"]["eval_history"][-1]["eval_loss"],
        },
        "baseline_stage602_role_token": compact(base_no, base_hard),
        "candidate_stage609": compact(cand_no, cand_hard),
        "deltas_vs_schema_baseline": {
            "exact_top1": cand_no["top1_accuracy"] - base_no["top1_accuracy"],
            "answer_top1": cand_no["answer_top1_accuracy"] - base_no["answer_top1_accuracy"],
            "exact_bits_per_param": bits_per_param(cand_no, "exact") - bits_per_param(base_no, "exact"),
            "answer_bits_per_param": bits_per_param(cand_no, "answer") - bits_per_param(base_no, "answer"),
            "hard_filter_corrections": cand_hard["structured_key_hard_filter_stats"]["top1_corrected_by_hard_filter"]
            - base_hard["structured_key_hard_filter_stats"]["top1_corrected_by_hard_filter"],
        },
        "operation_deltas": {
            "entity_context": op_delta(base_no, cand_no, "entity_context"),
            "direct_fact": op_delta(base_no, cand_no, "direct_fact"),
            "rule_case_intersection_member": op_delta(base_no, cand_no, "rule_case_intersection_member"),
            "set_intersection_member": op_delta(base_no, cand_no, "set_intersection_member"),
        },
        "decision": "rejected_narrow_answer_residual_on_role_tokens",
        "finding": (
            "Narrowing Stage608 to role-token entity answer misses avoids the entity-context answer drop, but it still lowers "
            "global exact/answer, lowers direct_fact and set_intersection_member exact, and raises hard-filter corrections. "
            "The remaining entity-context KBPP gain needs a selector/schema change, not weaker answer-contrast tuning."
        ),
    }


def write_doc(summary: dict[str, Any]) -> None:
    base = summary["baseline_stage602_role_token"]
    cand = summary["candidate_stage609"]
    entity = summary["operation_deltas"]["entity_context"]
    doc = f"""# Stage609 Entity Role Answer Residual

Artifact: `runs/local/artifacts/stage609_entity_role_answer_residual_summary.json`

## Result

Stage609 trained a narrow residual continuation on the Stage607 role-token schema, using only entity-context answer misses and weak answer contrast.

Stage602 role-token baseline exact/answer: `{base['exact_top1']}` / `{base['answer_top1']}`.

Stage609 exact/answer: `{cand['exact_top1']}` / `{cand['answer_top1']}`.

Hard-filter corrections: `{base['hard_filter_corrections']}` -> `{cand['hard_filter_corrections']}`.

Entity-context exact/answer: `{entity['candidate_exact_top1']}` / `{entity['candidate_answer_top1']}`.

## Decision

`rejected_narrow_answer_residual_on_role_tokens`

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
