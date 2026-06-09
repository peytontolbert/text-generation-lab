#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "runs/local/artifacts/knowledge_compression_moe_residual_10k_stage602_stage601_entity_field_balanced_replay_lr3e6_steps200"
DATASET = ROOT / "runs/local/artifacts/stage612_bare_selector_pair_dataset.json"
OUT = ROOT / "runs/local/artifacts/stage612_bare_selector_pair_summary.json"
DOC = ROOT / "docs/stage612_bare_selector_pair.md"


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
    stage611_no = load(BASE / "retrieval_eval_stage611_compact_entity_selector_full_corpus_operation_gated.json")
    stage611_hard = load(BASE / "retrieval_eval_stage611_compact_entity_selector_full_corpus_operation_gated_structured_hard_filter.json")
    bare_no = load(BASE / "retrieval_eval_stage612_bare_selector_pair_full_corpus_operation_gated.json")
    bare_hard = load(BASE / "retrieval_eval_stage612_bare_selector_pair_full_corpus_operation_gated_structured_hard_filter.json")
    dataset = load(DATASET)
    role = compact(role_no, role_hard)
    stage611 = compact(stage611_no, stage611_hard)
    bare = compact(bare_no, bare_hard)
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
        "artifact_kind": "stage612_bare_selector_pair_summary",
        "dataset_manifest": "runs/local/tmp/pocketpal_stage612_bare_selector_pair_seed461/agentkernel_lite_encdec_dataset_manifest.json",
        "dataset": {
            "changed_train_examples": dataset["changed_counts"]["train"],
            "changed_eval_examples": dataset["changed_counts"]["eval"],
            "selector_field_counts_eval": dataset["selector_field_counts"]["eval"],
        },
        "stage602_role_token_baseline": role,
        "stage611_compact_selector_schema_only": stage611,
        "stage612_bare_selector_pair_schema_only": bare,
        "stage612_delta_vs_role_token": delta(role, bare, keys),
        "stage612_delta_vs_stage611": delta(stage611, bare, keys),
        "decision": "accepted_bare_selector_pair_schema_best",
        "finding": (
            "The explicit ENTITY_SELECTOR label is unnecessary and harmful. A bare selector_pair=entity|field marker is "
            "shorter and substantially stronger, lifting entity_context exact/answer while reducing hard-filter corrections."
        ),
    }


def write_doc(summary: dict[str, Any]) -> None:
    role = summary["stage602_role_token_baseline"]
    stage611 = summary["stage611_compact_selector_schema_only"]
    bare = summary["stage612_bare_selector_pair_schema_only"]
    doc = f"""# Stage612 Bare Selector Pair

Artifact: `runs/local/artifacts/stage612_bare_selector_pair_summary.json`

## Result

Stage612 removes the explicit `ENTITY_SELECTOR` label and keeps only `selector_pair=entity|field`.

Stage607 role-token exact/answer: `{role['exact_top1']}` / `{role['answer_top1']}`.

Stage611 compact selector exact/answer: `{stage611['exact_top1']}` / `{stage611['answer_top1']}`.

Stage612 bare selector exact/answer: `{bare['exact_top1']}` / `{bare['answer_top1']}`.

Entity-context exact/answer: `{bare['entity_context_exact_top1']}` / `{bare['entity_context_answer_top1']}`.

Average train retrieval tokens per pair: Stage611 `{stage611['avg_train_retrieval_tokens_per_pair']}` -> Stage612 `{bare['avg_train_retrieval_tokens_per_pair']}`.

Hard-filter corrections: Stage611 `{stage611['hard_filter_corrections']}` -> Stage612 `{bare['hard_filter_corrections']}`.

## Decision

`accepted_bare_selector_pair_schema_best`

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
