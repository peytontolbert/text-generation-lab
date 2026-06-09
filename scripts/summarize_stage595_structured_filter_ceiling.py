#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE525 = ROOT / "runs/local/artifacts/knowledge_compression_moe_residual_10k_stage525_stage502_rule_replay_lr1e4_steps300"
STAGE594 = ROOT / "runs/local/artifacts/knowledge_compression_moe_residual_10k_stage594_stage525_residual_answer_equiv_lr1e5_steps80"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def compact_eval(no_filter: dict[str, Any], hard_filter: dict[str, Any]) -> dict[str, Any]:
    stats = hard_filter.get("structured_key_hard_filter_stats", {})
    hard_density = hard_filter["verified_density"]
    no_density = no_filter["verified_density"]
    return {
        "no_filter_exact_top1": no_filter["top1_accuracy"],
        "no_filter_answer_top1": no_filter["answer_top1_accuracy"],
        "hard_filter_exact_top1": hard_filter["top1_accuracy"],
        "hard_filter_answer_top1": hard_filter["answer_top1_accuracy"],
        "exact_top1_lift": float(hard_filter["top1_accuracy"]) - float(no_filter["top1_accuracy"]),
        "answer_top1_lift": float(hard_filter["answer_top1_accuracy"]) - float(no_filter["answer_top1_accuracy"]),
        "no_filter_exact_bits_per_param": no_density["exact_verified_bits"] / no_density["parameter_count"],
        "no_filter_answer_bits_per_param": no_density["answer_verified_bits"] / no_density["parameter_count"],
        "hard_filter_exact_bits_per_param": hard_density["exact_verified_bits"] / hard_density["parameter_count"],
        "hard_filter_answer_bits_per_param": hard_density["answer_verified_bits"] / hard_density["parameter_count"],
        "hard_filter_corrections": stats.get("top1_corrected_by_hard_filter"),
        "hard_filter_damage": stats.get("top1_damaged_by_hard_filter"),
        "exact_key_candidate_total": stats.get("exact_key_candidate_total"),
        "exact_key_candidate_max": stats.get("exact_key_candidate_max"),
        "queries_with_exact_key_candidate": stats.get("queries_with_exact_key_candidate"),
        "queries_with_multiple_exact_key_candidates": stats.get("queries_with_multiple_exact_key_candidates"),
        "queries_without_exact_key_candidate": stats.get("queries_without_exact_key_candidate"),
        "correct_missing_from_exact_key_candidates": stats.get("correct_missing_from_exact_key_candidates"),
    }


def build_summary() -> dict[str, Any]:
    stage525_no = load(STAGE525 / "retrieval_eval_full_corpus_operation_gated_answer_equiv_refresh.json")
    stage525_hard = load(STAGE525 / "retrieval_eval_full_corpus_operation_gated_structured_hard_filter_refresh.json")
    stage594_no = load(STAGE594 / "retrieval_eval_full_corpus_operation_gated.json")
    stage594_hard = load(STAGE594 / "retrieval_eval_full_corpus_operation_gated_structured_hard_filter.json")
    summary = {
        "artifact_kind": "stage595_structured_filter_ceiling",
        "dataset_manifest": "runs/local/tmp/pocketpal_stage521_stage497_rule_replay_seed461/agentkernel_lite_encdec_dataset_manifest.json",
        "scope": "strict full-corpus operation-gated retrieval with structured-key rerank plus hard filter",
        "stage525": compact_eval(stage525_no, stage525_hard),
        "stage594": compact_eval(stage594_no, stage594_hard),
        "decision": "deterministic_access_ceiling_confirmed_not_pure_neural_frontier",
        "finding": (
            "Exact structured-key hard filtering raises both 16k Stage525 and Stage594 to perfect strict full-corpus exact/answer "
            "retrieval with zero damage. Because every query has exactly one exact-key candidate and the correct document is always "
            "inside that candidate set, this is a verifier/access-layer ceiling rather than pure neural KBPP. The result says the "
            "current schema is too key-separable for measuring further intelligence density; the next dataset must introduce "
            "controlled key collisions or hidden compositions where exact keys narrow the candidate set but do not solve it."
        ),
        "next_schema_requirement": {
            "name": "collision_conditioned_kbpp",
            "goal": "Preserve deterministic operation/domain filtering while forcing neural resolution inside key-equivalent candidate sets.",
            "success_gate": "Hard filter candidate set should have mean size > 1 and exact_key_candidate_max > 1 for targeted ops, while oracle answer remains unique.",
            "target_ops": [
                "entity_context",
                "direct_fact",
                "rule_case_intersection_count",
                "rule_case_intersection_member",
                "set_intersection_member",
                "two_hop_owner_region",
            ],
        },
    }
    return summary


def write_doc(summary: dict[str, Any]) -> None:
    s525 = summary["stage525"]
    s594 = summary["stage594"]
    doc = f"""# Stage595 Structured Filter Ceiling

Artifact: `runs/local/artifacts/stage595_structured_filter_ceiling.json`

## Result

Strict full-corpus operation-gated retrieval with `--structured-key-rerank 1 --structured-key-hard-filter 1` makes both 16k models exact/answer perfect.

| run | no-filter exact/answer | hard-filter exact/answer | corrections | damage | hard-filter bits/param |
|---|---:|---:|---:|---:|---:|
| Stage525 | `{s525['no_filter_exact_top1']}` / `{s525['no_filter_answer_top1']}` | `{s525['hard_filter_exact_top1']}` / `{s525['hard_filter_answer_top1']}` | `{s525['hard_filter_corrections']}` | `{s525['hard_filter_damage']}` | `{s525['hard_filter_exact_bits_per_param']}` |
| Stage594 | `{s594['no_filter_exact_top1']}` / `{s594['no_filter_answer_top1']}` | `{s594['hard_filter_exact_top1']}` / `{s594['hard_filter_answer_top1']}` | `{s594['hard_filter_corrections']}` | `{s594['hard_filter_damage']}` | `{s594['hard_filter_exact_bits_per_param']}` |

Both hard-filter runs have exactly one exact-key candidate for every query, zero missing correct candidates, and zero multiple-candidate queries.

## Decision

`deterministic_access_ceiling_confirmed_not_pure_neural_frontier`

## Finding

{summary['finding']}

## Next Schema Requirement

The next KBPP benchmark should create key-collision-conditioned examples: exact operation/domain keys should narrow retrieval but leave more than one candidate, forcing the tiny model to resolve value, relation, or composition information inside the filtered set.
"""
    (ROOT / "docs/stage595_structured_filter_ceiling.md").write_text(doc, encoding="utf-8")


def main() -> None:
    summary = build_summary()
    output = ROOT / "runs/local/artifacts/stage595_structured_filter_ceiling.json"
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_doc(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
