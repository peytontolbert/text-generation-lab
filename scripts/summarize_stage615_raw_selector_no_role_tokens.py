#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "runs/local/artifacts/knowledge_compression_moe_residual_10k_stage602_stage601_entity_field_balanced_replay_lr3e6_steps200"
DATASET = ROOT / "runs/local/artifacts/stage615_raw_selector_no_role_tokens_dataset.json"
OUT = ROOT / "runs/local/artifacts/stage615_raw_selector_no_role_tokens_summary.json"
DOC = ROOT / "docs/stage615_raw_selector_no_role_tokens.md"


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


def load_surface(name: str) -> dict[str, Any]:
    no = load(BASE / f"retrieval_eval_{name}_full_corpus_operation_gated.json")
    hard = load(BASE / f"retrieval_eval_{name}_full_corpus_operation_gated_structured_hard_filter.json")
    return compact(no, hard)


def build_summary() -> dict[str, Any]:
    original = load_surface("stage601_entity_field_context")
    role = load_surface("stage607_entity_field_role_tokens")
    raw_role = load_surface("stage614_raw_selector_pair")
    raw_no_role = load_surface("stage615_raw_selector_no_role_tokens")
    dataset = load(DATASET)
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
        "artifact_kind": "stage615_raw_selector_no_role_tokens_summary",
        "dataset_manifest": "runs/local/tmp/pocketpal_stage615_raw_selector_no_role_tokens_seed461/agentkernel_lite_encdec_dataset_manifest.json",
        "dataset": {
            "changed_train_examples": dataset["changed_counts"]["train"],
            "changed_eval_examples": dataset["changed_counts"]["eval"],
            "selector_field_counts_eval": dataset["selector_field_counts"]["eval"],
        },
        "stage602_original_field_surface": original,
        "stage602_role_token_surface": role,
        "stage614_raw_selector_with_role_tokens": raw_role,
        "stage615_raw_selector_no_role_tokens": raw_no_role,
        "stage615_delta_vs_original_field_surface": delta(original, raw_no_role, keys),
        "stage615_delta_vs_role_token_surface": delta(role, raw_no_role, keys),
        "stage615_delta_vs_stage614": delta(raw_role, raw_no_role, keys),
        "decision": "accepted_minimal_raw_selector_best",
        "finding": (
            "FIELD_ROLE tokens are not needed once the raw entity|field selector is present. Stage615 improves over Stage614, "
            "improves over the original Stage602 field surface, and cuts retrieval token cost. The minimal selector pair is now "
            "the strongest entity-context KBPP lever."
        ),
    }


def write_doc(summary: dict[str, Any]) -> None:
    original = summary["stage602_original_field_surface"]
    role = summary["stage602_role_token_surface"]
    raw_role = summary["stage614_raw_selector_with_role_tokens"]
    raw_no_role = summary["stage615_raw_selector_no_role_tokens"]
    DOC.write_text(
        f"""# Stage615 Raw Selector No Role Tokens

Artifact: `runs/local/artifacts/stage615_raw_selector_no_role_tokens_summary.json`

## Result

Stage615 uses the Stage602 field-level balanced dataset, adds raw `entity|field`, and removes Stage607 `FIELD_ROLE_*` tokens.

Original Stage602 field surface exact/answer: `{original['exact_top1']}` / `{original['answer_top1']}`.

Stage607 role-token surface exact/answer: `{role['exact_top1']}` / `{role['answer_top1']}`.

Stage614 raw selector with role tokens exact/answer: `{raw_role['exact_top1']}` / `{raw_role['answer_top1']}`.

Stage615 raw selector without role tokens exact/answer: `{raw_no_role['exact_top1']}` / `{raw_no_role['answer_top1']}`.

Entity-context exact/answer: `{raw_no_role['entity_context_exact_top1']}` / `{raw_no_role['entity_context_answer_top1']}`.

Average train retrieval tokens per pair: `{raw_no_role['avg_train_retrieval_tokens_per_pair']}`.

Hard-filter corrections: `{raw_no_role['hard_filter_corrections']}`.

## Decision

`accepted_minimal_raw_selector_best`

## Finding

{summary['finding']}
""",
        encoding="utf-8",
    )


def main() -> None:
    summary = build_summary()
    OUT.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_doc(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
