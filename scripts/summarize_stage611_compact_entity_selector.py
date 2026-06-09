#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "runs/local/artifacts/knowledge_compression_moe_residual_10k_stage602_stage601_entity_field_balanced_replay_lr3e6_steps200"
DATASET = ROOT / "runs/local/artifacts/stage611_compact_entity_selector_dataset.json"
OUT = ROOT / "runs/local/artifacts/stage611_compact_entity_selector_summary.json"
DOC = ROOT / "docs/stage611_compact_entity_selector.md"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def bits_per_param(result: dict[str, Any], kind: str) -> float:
    density = result["verified_density"]
    return density[f"{kind}_verified_bits"] / density["parameter_count"]


def avg_train_tokens(result: dict[str, Any]) -> float:
    return result["verified_density"]["token_stats"]["avg_train_retrieval_tokens_per_pair"]


def compact(result: dict[str, Any], hard: dict[str, Any]) -> dict[str, Any]:
    stats = hard["structured_key_hard_filter_stats"]
    return {
        "exact_top1": result["top1_accuracy"],
        "answer_top1": result["answer_top1_accuracy"],
        "mrr": result["mean_reciprocal_rank"],
        "exact_bits_per_param": bits_per_param(result, "exact"),
        "answer_bits_per_param": bits_per_param(result, "answer"),
        "avg_train_retrieval_tokens_per_pair": avg_train_tokens(result),
        "entity_context_exact_top1": result["by_operation"]["entity_context"]["top1_accuracy"],
        "entity_context_answer_top1": result["by_operation"]["entity_context"]["answer_top1_accuracy"],
        "entity_context_mrr": result["by_operation"]["entity_context"]["mean_reciprocal_rank"],
        "hard_filter_exact_top1": hard["top1_accuracy"],
        "hard_filter_answer_top1": hard["answer_top1_accuracy"],
        "hard_filter_corrections": stats["top1_corrected_by_hard_filter"],
        "hard_filter_damage": stats["top1_damaged_by_hard_filter"],
        "hard_filter_masked_neural_top1": stats["neural_top1_masked_by_hard_filter"],
    }


def delta(left: dict[str, Any], right: dict[str, Any], keys: list[str]) -> dict[str, float]:
    return {key: right[key] - left[key] for key in keys}


def build_summary() -> dict[str, Any]:
    role_no = load(BASE / "retrieval_eval_stage607_entity_field_role_tokens_full_corpus_operation_gated.json")
    role_hard = load(BASE / "retrieval_eval_stage607_entity_field_role_tokens_full_corpus_operation_gated_structured_hard_filter.json")
    full_no = load(BASE / "retrieval_eval_stage610_entity_selector_tokens_full_corpus_operation_gated.json")
    full_hard = load(BASE / "retrieval_eval_stage610_entity_selector_tokens_full_corpus_operation_gated_structured_hard_filter.json")
    compact_no = load(BASE / "retrieval_eval_stage611_compact_entity_selector_full_corpus_operation_gated.json")
    compact_hard = load(BASE / "retrieval_eval_stage611_compact_entity_selector_full_corpus_operation_gated_structured_hard_filter.json")
    dataset = load(DATASET)
    role = compact(role_no, role_hard)
    full = compact(full_no, full_hard)
    short = compact(compact_no, compact_hard)
    keys = [
        "exact_top1",
        "answer_top1",
        "exact_bits_per_param",
        "answer_bits_per_param",
        "avg_train_retrieval_tokens_per_pair",
        "entity_context_exact_top1",
        "entity_context_answer_top1",
        "hard_filter_corrections",
        "hard_filter_masked_neural_top1",
    ]
    return {
        "artifact_kind": "stage611_compact_entity_selector_summary",
        "dataset_manifest": "runs/local/tmp/pocketpal_stage611_compact_entity_selector_seed461/agentkernel_lite_encdec_dataset_manifest.json",
        "dataset": {
            "changed_train_examples": dataset["changed_counts"]["train"],
            "changed_eval_examples": dataset["changed_counts"]["eval"],
            "selector_field_counts_eval": dataset["selector_field_counts"]["eval"],
        },
        "stage602_role_token_baseline": role,
        "stage610_full_selector_schema_only": full,
        "stage611_compact_selector_schema_only": short,
        "stage611_delta_vs_role_token": delta(role, short, keys),
        "stage611_delta_vs_stage610_full_selector": delta(full, short, keys),
        "decision": "accepted_compact_selector_schema_best",
        "finding": (
            "A compact entity-field pair selector outperforms the longer Stage610 selector and uses fewer retrieval tokens. "
            "This means selector identity weighting, not verbose repeated domain/entity/field spelling, carries the entity-context gain."
        ),
    }


def write_doc(summary: dict[str, Any]) -> None:
    role = summary["stage602_role_token_baseline"]
    full = summary["stage610_full_selector_schema_only"]
    short = summary["stage611_compact_selector_schema_only"]
    doc = f"""# Stage611 Compact Entity Selector

Artifact: `runs/local/artifacts/stage611_compact_entity_selector_summary.json`

## Result

Stage611 compresses Stage610's entity selector to one `selector_pair=entity|field` marker.

Stage602 on Stage607 role-token exact/answer: `{role['exact_top1']}` / `{role['answer_top1']}`.

Stage610 full-selector exact/answer: `{full['exact_top1']}` / `{full['answer_top1']}`.

Stage611 compact-selector exact/answer: `{short['exact_top1']}` / `{short['answer_top1']}`.

Entity-context exact/answer: `{short['entity_context_exact_top1']}` / `{short['entity_context_answer_top1']}`.

Average train retrieval tokens per pair: Stage610 `{full['avg_train_retrieval_tokens_per_pair']}` -> Stage611 `{short['avg_train_retrieval_tokens_per_pair']}`.

Hard-filter corrections: Stage610 `{full['hard_filter_corrections']}` -> Stage611 `{short['hard_filter_corrections']}`.

## Decision

`accepted_compact_selector_schema_best`

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
