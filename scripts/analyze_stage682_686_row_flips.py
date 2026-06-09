#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

FAST_DETAILS = {
    "stage676": ROOT
    / "runs/local/artifacts/knowledge_compression_moe_residual_10k_stage676_minedneg_256_from675_cpu_lr5e5_steps800/retrieval_eval_stage676_fast_details.jsonl",
    "stage681": ROOT
    / "runs/local/artifacts/knowledge_compression_moe_residual_10k_stage681_margin_targeted_continue_256_from680_cpu_lr5e6_steps300/retrieval_eval_stage681_fast_details.jsonl",
    "stage682": ROOT
    / "runs/local/artifacts/knowledge_compression_moe_residual_10k_stage682_margin_targeted_256_from681_cpu_lr5e6_steps300/retrieval_eval_stage682_fast_details.jsonl",
    "stage683": ROOT
    / "runs/local/artifacts/knowledge_compression_moe_residual_10k_stage683_margin_targeted_256_from682_cpu_lr5e6_steps300/retrieval_eval_stage683_fast_details.jsonl",
    "stage684": ROOT
    / "runs/local/artifacts/knowledge_compression_moe_residual_10k_stage684_frozen_gain_margin_256_from682_cpu_lr2e6_steps300/retrieval_eval_stage684_fast_details.jsonl",
    "stage685": ROOT
    / "runs/local/artifacts/knowledge_compression_moe_residual_10k_stage685_frozen_gain_margin_256_from682_cpu_lr1e6_steps150/retrieval_eval_stage685_fast_details.jsonl",
    "stage686": ROOT
    / "runs/local/artifacts/knowledge_compression_moe_residual_10k_stage686_repair_only_margin_256_from682_cpu_lr2e6_steps300/retrieval_eval_stage686_fast_details.jsonl",
}

TOPK_DETAILS = {
    "stage682": ROOT
    / "runs/local/artifacts/knowledge_compression_moe_residual_10k_stage682_margin_targeted_256_from681_cpu_lr5e6_steps300/retrieval_eval_stage682_topk_margin_details.jsonl"
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def main() -> None:
    fast = {stage: {row["unit_id"]: row for row in read_jsonl(path)} for stage, path in FAST_DETAILS.items()}
    topk = {stage: {row["unit_id"]: row for row in read_jsonl(path)} for stage, path in TOPK_DETAILS.items()}
    unit_ids = sorted(fast["stage682"])

    correct_sets = {
        stage: {unit_id for unit_id, row in rows.items() if bool(row.get("answer_top1"))}
        for stage, rows in fast.items()
    }
    exact_sets = {
        stage: {unit_id for unit_id, row in rows.items() if bool(row.get("top1"))}
        for stage, rows in fast.items()
    }

    patterns = Counter()
    rows_out: list[dict[str, Any]] = []
    for unit_id in unit_ids:
        answer_bits = "".join("1" if unit_id in correct_sets[stage] else "0" for stage in FAST_DETAILS)
        exact_bits = "".join("1" if unit_id in exact_sets[stage] else "0" for stage in FAST_DETAILS)
        row682 = fast["stage682"][unit_id]
        margin682 = topk["stage682"].get(unit_id, {}).get("margin_to_best_wrong")
        best_wrong682 = topk["stage682"].get(unit_id, {}).get("best_wrong_source_id")
        patterns[answer_bits] += 1
        rows_out.append(
            {
                "unit_id": unit_id,
                "expected_content": row682.get("expected_content"),
                "answer_pattern_676_681_682_683_684_685_686": answer_bits,
                "exact_pattern_676_681_682_683_684_685_686": exact_bits,
                "stage682_margin_to_best_wrong": margin682,
                "stage682_best_wrong_source_id": best_wrong682,
                "predicted": {
                    stage: fast[stage][unit_id].get("predicted_source_id")
                    for stage in FAST_DETAILS
                },
            }
        )

    stage682_only_wins = correct_sets["stage682"] - (
        correct_sets["stage676"]
        | correct_sets["stage681"]
        | correct_sets["stage683"]
        | correct_sets["stage684"]
        | correct_sets["stage685"]
        | correct_sets["stage686"]
    )
    stage682_wins_lost_by_all_after = correct_sets["stage682"] - (
        correct_sets["stage683"]
        | correct_sets["stage684"]
        | correct_sets["stage685"]
        | correct_sets["stage686"]
    )
    stable_misses = set(unit_ids)
    for stage_set in correct_sets.values():
        stable_misses -= stage_set

    pairwise = {}
    for a in FAST_DETAILS:
        for b in FAST_DETAILS:
            if a >= b:
                continue
            pairwise[f"{a}_to_{b}"] = {
                "gained": len(correct_sets[b] - correct_sets[a]),
                "lost": len(correct_sets[a] - correct_sets[b]),
                "net": len(correct_sets[b]) - len(correct_sets[a]),
            }

    margin_bins = defaultdict(int)
    for unit_id in stable_misses:
        margin = topk["stage682"].get(unit_id, {}).get("margin_to_best_wrong")
        if margin is None:
            margin_bins["missing"] += 1
        elif margin >= -0.01:
            margin_bins["stable_miss_margin_ge_neg_0.01"] += 1
        elif margin >= -0.04:
            margin_bins["stable_miss_margin_ge_neg_0.04"] += 1
        elif margin >= -0.08:
            margin_bins["stable_miss_margin_ge_neg_0.08"] += 1
        else:
            margin_bins["stable_miss_margin_lt_neg_0.08"] += 1

    summary = {
        "artifact_kind": "stage682_686_row_flip_analysis",
        "stage_order": list(FAST_DETAILS),
        "answer_correct": {stage: len(ids) for stage, ids in correct_sets.items()},
        "exact_correct": {stage: len(ids) for stage, ids in exact_sets.items()},
        "pairwise_answer_flips": pairwise,
        "answer_pattern_counts": dict(patterns.most_common()),
        "stage682_only_wins": len(stage682_only_wins),
        "stage682_wins_lost_by_all_after": len(stage682_wins_lost_by_all_after),
        "stable_misses_all_stages": len(stable_misses),
        "stable_miss_margin_bins": dict(sorted(margin_bins.items())),
        "interpretation": (
            "The 256 frontier is dominated by row exchange: Stage682 has the best net score, "
            "but later weighted-hard-negative variants lose Stage682 wins while gaining a few other rows. "
            "This indicates a local ranking-margin conflict, not a lack of residual examples."
        ),
        "next_recommendation": (
            "Do not run another weighted hard-negative replay. Try softer preservation: "
            "distill Stage682 query/doc embeddings or logits while applying a small repair loss to stable low-margin misses."
        ),
    }

    out_json = ROOT / "runs/local/artifacts/stage682_686_row_flip_analysis.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    out_jsonl = ROOT / "runs/local/artifacts/stage682_686_row_flip_rows.jsonl"
    with out_jsonl.open("w", encoding="utf-8") as handle:
        for row in rows_out:
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
