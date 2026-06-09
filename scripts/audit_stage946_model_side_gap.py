#!/usr/bin/env python3
"""Audit Stage944 model-side misses against the Stage919 typed-access ceiling."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def iter_jsonl(path: Path):
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def rank_bucket(rank: int | None) -> str:
    if rank is None:
        return "missing"
    if rank <= 1:
        return "rank1"
    if rank == 2:
        return "rank2"
    if rank <= 4:
        return "rank3_4"
    if rank <= 8:
        return "rank5_8"
    return "rank9_plus"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--stage944-predictions",
        type=Path,
        default=Path("runs/local/artifacts/stage944_loadable_stage943_policy_predictions.jsonl"),
    )
    parser.add_argument(
        "--stage919-summary",
        type=Path,
        default=Path("runs/local/artifacts/stage919_stage917_binding_comparison_head_summary.json"),
    )
    parser.add_argument(
        "--targets-jsonl",
        type=Path,
        default=Path("runs/local/artifacts/stage918_stage917_bridge_curriculum_targets.jsonl"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("runs/local/artifacts/stage946_model_side_gap_audit_summary.json"),
    )
    args = parser.parse_args()

    stage919 = load_json(args.stage919_summary)
    stage919_eval = stage919["eval"]
    typed_by_op = stage919_eval["by_operation"]

    predictions: dict[int, dict[str, Any]] = {}
    for row in iter_jsonl(args.stage944_predictions):
        if row["split"] == "eval":
            predictions[int(row["query_index"])] = row

    by_op: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "rows": 0,
            "stage944_answer": 0,
            "stage944_exact": 0,
            "base_answer": 0,
            "base_exact": 0,
            "answer_recoverable": 0,
            "exact_recoverable": 0,
            "answer_positive_rank_buckets": Counter(),
            "exact_positive_rank_buckets": Counter(),
            "answer_positive_rank_histogram": Counter(),
            "exact_positive_rank_histogram": Counter(),
            "missed_recoverable_answer": 0,
            "missed_recoverable_exact": 0,
        }
    )

    for target in iter_jsonl(args.targets_jsonl):
        if target["split"] != "eval":
            continue
        query_index = int(target["query_index"])
        pred = predictions[query_index]
        op = target["operation"]
        rec = by_op[op]
        rec["rows"] += 1
        rec["stage944_answer"] += int(pred.get("answer", 0))
        rec["stage944_exact"] += int(pred.get("exact", 0))

        candidates = target["candidates"]
        base_top = min(candidates, key=lambda c: c.get("rank", 10**9))
        rec["base_answer"] += int(base_top.get("is_answer_match", False) or base_top.get("is_exact", False))
        rec["base_exact"] += int(base_top.get("is_exact", False))

        answer_ranks = [int(c["rank"]) for c in candidates if c.get("is_answer_match")]
        exact_ranks = [int(c["rank"]) for c in candidates if c.get("is_exact")]

        # Relation rows on this target file encode correctness through exact flags.
        # Stage919 reports equal answer/exact relation counts, so use exact as
        # answer-recoverable proxy when answer flags are absent.
        if not answer_ranks and op == "relation":
            answer_ranks = exact_ranks[:]

        answer_rank = min(answer_ranks) if answer_ranks else None
        exact_rank = min(exact_ranks) if exact_ranks else None
        if answer_rank is not None:
            rec["answer_recoverable"] += 1
            rec["answer_positive_rank_histogram"][answer_rank] += 1
            rec["answer_positive_rank_buckets"][rank_bucket(answer_rank)] += 1
            if not pred.get("answer", 0):
                rec["missed_recoverable_answer"] += 1
        if exact_rank is not None:
            rec["exact_recoverable"] += 1
            rec["exact_positive_rank_histogram"][exact_rank] += 1
            rec["exact_positive_rank_buckets"][rank_bucket(exact_rank)] += 1
            if not pred.get("exact", 0):
                rec["missed_recoverable_exact"] += 1

    operation_gaps: dict[str, dict[str, Any]] = {}
    totals = Counter()
    for op in sorted(by_op):
        rec = by_op[op]
        typed = typed_by_op[op]
        row = {
            "rows": rec["rows"],
            "stage944_answer_exact": [rec["stage944_answer"], rec["stage944_exact"]],
            "stage919_typed_access_answer_exact": [typed["answer"], typed["exact"]],
            "gap_to_stage919_answer_exact": [
                typed["answer"] - rec["stage944_answer"],
                typed["exact"] - rec["stage944_exact"],
            ],
            "base_answer_exact": [rec["base_answer"], rec["base_exact"]],
            "recoverable_answer_exact": [rec["answer_recoverable"], rec["exact_recoverable"]],
            "gap_to_recoverable_answer_exact": [
                rec["answer_recoverable"] - rec["stage944_answer"],
                rec["exact_recoverable"] - rec["stage944_exact"],
            ],
            "missed_recoverable_answer_exact": [
                rec["missed_recoverable_answer"],
                rec["missed_recoverable_exact"],
            ],
            "answer_positive_rank_buckets": dict(sorted(rec["answer_positive_rank_buckets"].items())),
            "exact_positive_rank_buckets": dict(sorted(rec["exact_positive_rank_buckets"].items())),
            "answer_positive_rank_histogram": {
                str(k): v for k, v in sorted(rec["answer_positive_rank_histogram"].items())
            },
            "exact_positive_rank_histogram": {
                str(k): v for k, v in sorted(rec["exact_positive_rank_histogram"].items())
            },
        }
        operation_gaps[op] = row
        totals["rows"] += rec["rows"]
        totals["stage944_answer"] += rec["stage944_answer"]
        totals["stage944_exact"] += rec["stage944_exact"]
        totals["typed_answer"] += typed["answer"]
        totals["typed_exact"] += typed["exact"]
        totals["recoverable_answer"] += rec["answer_recoverable"]
        totals["recoverable_exact"] += rec["exact_recoverable"]

    ranked_stage919_gaps = sorted(
        (
            {
                "operation": op,
                "answer_gap": row["gap_to_stage919_answer_exact"][0],
                "exact_gap": row["gap_to_stage919_answer_exact"][1],
            }
            for op, row in operation_gaps.items()
        ),
        key=lambda r: (r["exact_gap"], r["answer_gap"]),
        reverse=True,
    )
    ranked_recoverable_gaps = sorted(
        (
            {
                "operation": op,
                "answer_gap": row["gap_to_recoverable_answer_exact"][0],
                "exact_gap": row["gap_to_recoverable_answer_exact"][1],
            }
            for op, row in operation_gaps.items()
        ),
        key=lambda r: (r["exact_gap"], r["answer_gap"]),
        reverse=True,
    )

    summary = {
        "artifact_kind": "stage946_model_side_gap_audit",
        "status": "diagnostic_next_steps_no_frontier_change",
        "inputs": {
            "stage944_predictions": str(args.stage944_predictions),
            "stage919_summary": str(args.stage919_summary),
            "targets_jsonl": str(args.targets_jsonl),
        },
        "frontiers": {
            "stage944_model_side_answer_exact": [totals["stage944_answer"], totals["stage944_exact"]],
            "stage944_implied_full_answer_exact": [482, 464],
            "stage919_typed_access_answer_exact": [totals["typed_answer"], totals["typed_exact"]],
            "stage919_implied_full_answer_exact": [541, 523],
            "gap_to_stage919_answer_exact": [
                totals["typed_answer"] - totals["stage944_answer"],
                totals["typed_exact"] - totals["stage944_exact"],
            ],
            "candidate_recoverable_answer_exact": [
                totals["recoverable_answer"],
                totals["recoverable_exact"],
            ],
            "gap_to_candidate_recoverable_answer_exact": [
                totals["recoverable_answer"] - totals["stage944_answer"],
                totals["recoverable_exact"] - totals["stage944_exact"],
            ],
        },
        "operation_gaps": operation_gaps,
        "ranked_gap_to_stage919": ranked_stage919_gaps,
        "ranked_gap_to_candidate_recoverable": ranked_recoverable_gaps,
        "interpretation": [
            "Stage944 remains the accepted model-side/loadable scorer frontier; Stage946 changes no scorer decisions.",
            "Atomic is saturated relative to Stage919 on this split.",
            "The largest typed-access gap is relation, followed by exception, then composition.",
            "Composition router sweeps saturated because most remaining composition positives require new proof-edge evidence, not more routing over current score margins.",
            "The next density-positive path should train model-owned source-target/value and claim/value comparison heads, then expose them through the Stage944 scorer under a no-regression gate.",
        ],
        "next_steps": [
            {
                "stage": "Stage947",
                "target": "relation_source_target_value_head",
                "reason": "Relation has the largest gap to Stage919: 32/32 rows, with many recoverable positives beyond rank 1.",
                "gate": "Improve relation over 52/52 without reducing atomic/composition/counterfactual/exception Stage944 rows.",
            },
            {
                "stage": "Stage948",
                "target": "exception_claim_value_head",
                "reason": "Exception is the second-largest gap to Stage919: 15/15 rows, and recoverable positives are concentrated at ranks 2-4.",
                "gate": "Improve exception over 54/54 under the same Stage944 no-regression policy.",
            },
            {
                "stage": "Stage949",
                "target": "composition_proof_edge_head",
                "reason": "Composition still trails Stage919 by 11/11 rows, but Stage945 showed current composition score-margin routers are saturated.",
                "gate": "Beat composition 42/26 using model-owned proof-edge evidence without suffix-similarity features at eval.",
            },
        ],
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary["frontiers"], indent=2))
    print("wrote", args.output)


if __name__ == "__main__":
    main()
