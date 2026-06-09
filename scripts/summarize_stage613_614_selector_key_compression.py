#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "runs/local/artifacts/knowledge_compression_moe_residual_10k_stage602_stage601_entity_field_balanced_replay_lr3e6_steps200"
DATASET_613 = ROOT / "runs/local/artifacts/stage613_short_selector_pair_dataset.json"
DATASET_614 = ROOT / "runs/local/artifacts/stage614_raw_selector_pair_dataset.json"
OUT_613 = ROOT / "runs/local/artifacts/stage613_short_selector_pair_summary.json"
OUT_614 = ROOT / "runs/local/artifacts/stage614_raw_selector_pair_summary.json"
DOC_613 = ROOT / "docs/stage613_short_selector_pair.md"
DOC_614 = ROOT / "docs/stage614_raw_selector_pair.md"


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


def make_summary(
    *,
    artifact_kind: str,
    dataset_manifest: str,
    dataset: dict[str, Any],
    candidate: dict[str, Any],
    previous_name: str,
    previous: dict[str, Any],
    role: dict[str, Any],
    decision: str,
    finding: str,
) -> dict[str, Any]:
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
        "artifact_kind": artifact_kind,
        "dataset_manifest": dataset_manifest,
        "dataset": {
            "changed_train_examples": dataset["changed_counts"]["train"],
            "changed_eval_examples": dataset["changed_counts"]["eval"],
            "selector_field_counts_eval": dataset["selector_field_counts"]["eval"],
        },
        "stage602_role_token_baseline": role,
        previous_name: previous,
        "candidate_schema_only": candidate,
        "candidate_delta_vs_role_token": delta(role, candidate, keys),
        "candidate_delta_vs_previous": delta(previous, candidate, keys),
        "decision": decision,
        "finding": finding,
    }


def write_doc(path: Path, title: str, summary: dict[str, Any], previous_label: str) -> None:
    role = summary["stage602_role_token_baseline"]
    previous = summary[previous_label]
    candidate = summary["candidate_schema_only"]
    path.write_text(
        f"""# {title}

Artifact: `runs/local/artifacts/{path.stem}_summary.json`

## Result

Stage607 role-token exact/answer: `{role['exact_top1']}` / `{role['answer_top1']}`.

Previous selector exact/answer: `{previous['exact_top1']}` / `{previous['answer_top1']}`.

Candidate exact/answer: `{candidate['exact_top1']}` / `{candidate['answer_top1']}`.

Entity-context exact/answer: `{candidate['entity_context_exact_top1']}` / `{candidate['entity_context_answer_top1']}`.

Average train retrieval tokens per pair: `{candidate['avg_train_retrieval_tokens_per_pair']}`.

Hard-filter corrections: `{candidate['hard_filter_corrections']}`.

## Decision

`{summary['decision']}`

## Finding

{summary['finding']}
""",
        encoding="utf-8",
    )


def main() -> None:
    role = load_surface("stage607_entity_field_role_tokens")
    stage612 = load_surface("stage612_bare_selector_pair")
    stage613 = load_surface("stage613_short_selector_pair")
    stage614 = load_surface("stage614_raw_selector_pair")
    dataset_613 = load(DATASET_613)
    dataset_614 = load(DATASET_614)

    summary_613 = make_summary(
        artifact_kind="stage613_short_selector_pair_summary",
        dataset_manifest="runs/local/tmp/pocketpal_stage613_short_selector_pair_seed461/agentkernel_lite_encdec_dataset_manifest.json",
        dataset=dataset_613,
        candidate=stage613,
        previous_name="stage612_bare_selector_pair_schema_only",
        previous=stage612,
        role=role,
        decision="accepted_short_selector_pair_schema_best",
        finding=(
            "Shortening selector_pair to sp preserves and slightly improves the Stage612 gain while reducing token cost. "
            "The model does not need a semantic selector key name; it benefits from a compact pair anchor."
        ),
    )
    summary_614 = make_summary(
        artifact_kind="stage614_raw_selector_pair_summary",
        dataset_manifest="runs/local/tmp/pocketpal_stage614_raw_selector_pair_seed461/agentkernel_lite_encdec_dataset_manifest.json",
        dataset=dataset_614,
        candidate=stage614,
        previous_name="stage613_short_selector_pair_schema_only",
        previous=stage613,
        role=role,
        decision="accepted_raw_selector_pair_schema_best",
        finding=(
            "Removing the selector key entirely and inserting the raw entity|field pair gives the best selector surface so far. "
            "The useful bit is the pair identity itself, and every extra key-name token has been overhead."
        ),
    )
    OUT_613.write_text(json.dumps(summary_613, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    OUT_614.write_text(json.dumps(summary_614, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_doc(DOC_613, "Stage613 Short Selector Pair", summary_613, "stage612_bare_selector_pair_schema_only")
    write_doc(DOC_614, "Stage614 Raw Selector Pair", summary_614, "stage613_short_selector_pair_schema_only")
    print(json.dumps({"stage613": summary_613, "stage614": summary_614}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
