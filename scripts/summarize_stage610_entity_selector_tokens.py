#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "runs/local/artifacts/knowledge_compression_moe_residual_10k_stage602_stage601_entity_field_balanced_replay_lr3e6_steps200"
CAND = ROOT / "runs/local/artifacts/knowledge_compression_moe_residual_10k_stage610_stage602_entity_selector_tokens_lr1e6_steps150"
DATASET = ROOT / "runs/local/artifacts/stage610_entity_selector_tokens_dataset.json"
OUT = ROOT / "runs/local/artifacts/stage610_entity_selector_tokens_summary.json"
DOC = ROOT / "docs/stage610_entity_selector_tokens.md"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def bits_per_param(result: dict[str, Any], kind: str) -> float:
    density = result["verified_density"]
    return density[f"{kind}_verified_bits"] / density["parameter_count"]


def compact(result: dict[str, Any], hard: dict[str, Any]) -> dict[str, Any]:
    stats = hard["structured_key_hard_filter_stats"]
    return {
        "exact_top1": result["top1_accuracy"],
        "answer_top1": result["answer_top1_accuracy"],
        "mrr": result["mean_reciprocal_rank"],
        "exact_bits_per_param": bits_per_param(result, "exact"),
        "answer_bits_per_param": bits_per_param(result, "answer"),
        "entity_context_exact_top1": result["by_operation"]["entity_context"]["top1_accuracy"],
        "entity_context_answer_top1": result["by_operation"]["entity_context"]["answer_top1_accuracy"],
        "hard_filter_exact_top1": hard["top1_accuracy"],
        "hard_filter_answer_top1": hard["answer_top1_accuracy"],
        "hard_filter_corrections": stats["top1_corrected_by_hard_filter"],
        "hard_filter_damage": stats["top1_damaged_by_hard_filter"],
        "hard_filter_masked_neural_top1": stats["neural_top1_masked_by_hard_filter"],
    }


def delta(left: dict[str, Any], right: dict[str, Any], keys: list[str]) -> dict[str, float]:
    return {key: right[key] - left[key] for key in keys}


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


def build_summary() -> dict[str, Any]:
    role_no = load(BASE / "retrieval_eval_stage607_entity_field_role_tokens_full_corpus_operation_gated.json")
    role_hard = load(BASE / "retrieval_eval_stage607_entity_field_role_tokens_full_corpus_operation_gated_structured_hard_filter.json")
    schema_no = load(BASE / "retrieval_eval_stage610_entity_selector_tokens_full_corpus_operation_gated.json")
    schema_hard = load(BASE / "retrieval_eval_stage610_entity_selector_tokens_full_corpus_operation_gated_structured_hard_filter.json")
    trained_no = load(CAND / "retrieval_eval_stage610_entity_selector_tokens_full_corpus_operation_gated.json")
    trained_hard = load(CAND / "retrieval_eval_stage610_entity_selector_tokens_full_corpus_operation_gated_structured_hard_filter.json")
    manifest = load(CAND / "agentkernel_lite_encdec_manifest.json")
    dataset = load(DATASET)
    role = compact(role_no, role_hard)
    schema = compact(schema_no, schema_hard)
    trained = compact(trained_no, trained_hard)
    metric_keys = [
        "exact_top1",
        "answer_top1",
        "exact_bits_per_param",
        "answer_bits_per_param",
        "entity_context_exact_top1",
        "entity_context_answer_top1",
        "hard_filter_exact_top1",
        "hard_filter_answer_top1",
        "hard_filter_corrections",
    ]
    return {
        "artifact_kind": "stage610_entity_selector_tokens_summary",
        "dataset_manifest": "runs/local/tmp/pocketpal_stage610_entity_selector_tokens_seed461/agentkernel_lite_encdec_dataset_manifest.json",
        "dataset": {
            "changed_train_examples": dataset["changed_counts"]["train"],
            "changed_eval_examples": dataset["changed_counts"]["eval"],
            "selector_field_counts_eval": dataset["selector_field_counts"]["eval"],
        },
        "trained_candidate": {
            "bundle_dir": str(CAND.relative_to(ROOT)),
            "checkpoint": str((CAND / "checkpoints/step_00000150.pt").relative_to(ROOT)),
            "steps": 150,
            "cumulative_steps": 3950,
            "learning_rate": 1e-6,
            "eval_loss_step_150": manifest["training_summary"]["eval_history"][-1]["eval_loss"],
        },
        "baseline_stage602_role_token": role,
        "stage602_schema_only_stage610": schema,
        "stage610_trained": trained,
        "schema_only_delta_vs_role_token": delta(role, schema, metric_keys),
        "trained_delta_vs_schema_only": delta(schema, trained, metric_keys),
        "operation_deltas_schema_only_vs_role_token": {
            "entity_context": op_delta(role_no, schema_no, "entity_context"),
            "direct_fact": op_delta(role_no, schema_no, "direct_fact"),
            "rule_case_intersection_member": op_delta(role_no, schema_no, "rule_case_intersection_member"),
            "set_intersection_member": op_delta(role_no, schema_no, "set_intersection_member"),
        },
        "operation_deltas_trained_vs_schema_only": {
            "entity_context": op_delta(schema_no, trained_no, "entity_context"),
            "direct_fact": op_delta(schema_no, trained_no, "direct_fact"),
            "rule_case_intersection_member": op_delta(schema_no, trained_no, "rule_case_intersection_member"),
            "set_intersection_member": op_delta(schema_no, trained_no, "set_intersection_member"),
        },
        "decision": "accepted_schema_selector_gain_training_rejected",
        "finding": (
            "Repeating entity+field selector markers is a strong schema-only KBPP lever: Stage602 on the Stage610 surface "
            "substantially improves global and entity_context exact/answer versus the Stage607 role-token surface and improves "
            "hard-filter corrections. A 150-step continuation does not improve the schema-only result, so the gain is from "
            "selector encoding rather than additional training."
        ),
    }


def write_doc(summary: dict[str, Any]) -> None:
    role = summary["baseline_stage602_role_token"]
    schema = summary["stage602_schema_only_stage610"]
    trained = summary["stage610_trained"]
    doc = f"""# Stage610 Entity Selector Tokens

Artifact: `runs/local/artifacts/stage610_entity_selector_tokens_summary.json`

## Result

Stage610 adds repeated entity+field selector markers to `entity_context` rows while preserving candidate keys.

Stage602 on Stage607 role-token exact/answer: `{role['exact_top1']}` / `{role['answer_top1']}`.

Stage602 schema-only on Stage610 exact/answer: `{schema['exact_top1']}` / `{schema['answer_top1']}`.

Stage610 trained exact/answer: `{trained['exact_top1']}` / `{trained['answer_top1']}`.

Entity-context schema-only exact/answer: `{schema['entity_context_exact_top1']}` / `{schema['entity_context_answer_top1']}`.

Hard-filter schema-only exact/answer: `{schema['hard_filter_exact_top1']}` / `{schema['hard_filter_answer_top1']}`.

Hard-filter corrections: `{role['hard_filter_corrections']}` -> `{schema['hard_filter_corrections']}`.

## Decision

`accepted_schema_selector_gain_training_rejected`

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
