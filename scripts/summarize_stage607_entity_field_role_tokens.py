#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "runs/local/artifacts/knowledge_compression_moe_residual_10k_stage602_stage601_entity_field_balanced_replay_lr3e6_steps200"
CAND = ROOT / "runs/local/artifacts/knowledge_compression_moe_residual_10k_stage607_stage602_entity_field_role_tokens_lr2e6_steps200"
OUT = ROOT / "runs/local/artifacts/stage607_entity_field_role_tokens_summary.json"
DOC = ROOT / "docs/stage607_entity_field_role_tokens.md"


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
    original_surface = load(BASE / "retrieval_eval_stage601_entity_field_context_full_corpus_operation_gated.json")
    original_hard = load(BASE / "retrieval_eval_stage601_entity_field_context_full_corpus_operation_gated_structured_hard_filter.json")
    manifest = load(CAND / "agentkernel_lite_encdec_manifest.json")
    dataset = load(ROOT / "runs/local/artifacts/stage607_entity_field_role_tokens_dataset.json")
    return {
        "artifact_kind": "stage607_entity_field_role_tokens_summary",
        "candidate": "stage607_stage602_entity_field_role_tokens_lr2e6_steps200",
        "bundle_dir": str(CAND.relative_to(ROOT)),
        "checkpoint": str((CAND / "checkpoints/step_00000200.pt").relative_to(ROOT)),
        "dataset_manifest": "runs/local/tmp/pocketpal_stage607_entity_field_role_tokens_seed461/agentkernel_lite_encdec_dataset_manifest.json",
        "dataset": {
            "changed_train_examples": dataset["changed_counts"]["train"],
            "changed_eval_examples": dataset["changed_counts"]["eval"],
            "field_role_counts_eval": dataset["field_role_counts"]["eval"],
        },
        "training": {
            "init_from": str((BASE / "checkpoints/step_00000200.pt").relative_to(ROOT)),
            "steps": 200,
            "cumulative_steps": 4000,
            "learning_rate": 2e-6,
            "retrieval_value_anchor_weight": 0.01,
            "retrieval_value_anchor_operation_ids": [10],
            "eval_loss_step_200": manifest["training_summary"]["eval_history"][-1]["eval_loss"],
        },
        "stage602_original_stage601_surface": compact(original_surface, original_hard),
        "stage602_role_token_baseline": compact(base_no, base_hard),
        "candidate_stage607": compact(cand_no, cand_hard),
        "schema_delta_vs_stage601_surface": {
            "exact_top1": base_no["top1_accuracy"] - original_surface["top1_accuracy"],
            "answer_top1": base_no["answer_top1_accuracy"] - original_surface["answer_top1_accuracy"],
            "hard_filter_exact_top1": base_hard["top1_accuracy"] - original_hard["top1_accuracy"],
            "hard_filter_answer_top1": base_hard["answer_top1_accuracy"] - original_hard["answer_top1_accuracy"],
            "hard_filter_corrections": base_hard["structured_key_hard_filter_stats"]["top1_corrected_by_hard_filter"]
            - original_hard["structured_key_hard_filter_stats"]["top1_corrected_by_hard_filter"],
        },
        "training_delta_vs_schema_baseline": {
            "exact_top1": cand_no["top1_accuracy"] - base_no["top1_accuracy"],
            "answer_top1": cand_no["answer_top1_accuracy"] - base_no["answer_top1_accuracy"],
            "hard_filter_corrections": cand_hard["structured_key_hard_filter_stats"]["top1_corrected_by_hard_filter"]
            - base_hard["structured_key_hard_filter_stats"]["top1_corrected_by_hard_filter"],
        },
        "operation_deltas_training": {
            "entity_context": op_delta(base_no, cand_no, "entity_context"),
            "direct_fact": op_delta(base_no, cand_no, "direct_fact"),
            "rule_case_intersection_count": op_delta(base_no, cand_no, "rule_case_intersection_count"),
            "rule_case_intersection_member": op_delta(base_no, cand_no, "rule_case_intersection_member"),
        },
        "decision": "accepted_as_schema_answer_gain_training_not_frontier",
        "finding": (
            "Explicit field-role tokens validate the Stage606 diagnosis: the schema alone raises answer accuracy and hard-filter "
            "ceiling on entity_context, but it lowers exact-card identity. Training on the role-token surface recovers a little "
            "entity exactness but gives back answer accuracy and does not improve the hard-filter result. Treat role tokens as "
            "a schema lever for answer reliability, not yet a pure-neural exact frontier."
        ),
    }


def write_doc(summary: dict[str, Any]) -> None:
    orig = summary["stage602_original_stage601_surface"]
    base = summary["stage602_role_token_baseline"]
    cand = summary["candidate_stage607"]
    entity = summary["operation_deltas_training"]["entity_context"]
    doc = f"""# Stage607 Entity Field Role Tokens

Artifact: `runs/local/artifacts/stage607_entity_field_role_tokens_summary.json`

## Result

Stage607 adds explicit `FIELD_ROLE_*` tokens to `entity_context` field rows.

Stage602 on the original Stage601 surface: exact/answer `{orig['exact_top1']}` / `{orig['answer_top1']}`.

Stage602 on the Stage607 role-token surface: exact/answer `{base['exact_top1']}` / `{base['answer_top1']}`.

Stage607 trained checkpoint: exact/answer `{cand['exact_top1']}` / `{cand['answer_top1']}`.

Hard-filter exact/answer on the role-token surface: `{cand['hard_filter_exact_top1']}` / `{cand['hard_filter_answer_top1']}`.

Entity-context trained exact/answer: `{entity['candidate_exact_top1']}` / `{entity['candidate_answer_top1']}`.

## Decision

`accepted_as_schema_answer_gain_training_not_frontier`

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
