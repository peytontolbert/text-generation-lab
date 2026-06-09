#!/usr/bin/env python3
"""Materialize relation qslot/value auxiliary targets after Stage949."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def iter_jsonl(path: Path):
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def candidate_dslots(candidate: dict[str, Any]) -> list[str]:
    bridge = candidate.get("bridge", {}) or {}
    return [str(x) for x in bridge.get("dslot", []) if str(x)]


def entity_pair_match(candidate: dict[str, Any]) -> bool:
    bridge = candidate.get("bridge", {}) or {}
    return bool(bridge.get("entity_suffix_match")) and bool(bridge.get("pair_suffix_match"))


def is_correct(candidate: dict[str, Any]) -> bool:
    return bool(candidate.get("is_exact") or candidate.get("is_answer_match"))


def top_by_base(candidates: list[dict[str, Any]]) -> int | None:
    if not candidates:
        return None
    return min(range(len(candidates)), key=lambda i: (-float(candidates[i].get("base_score", 0.0) or 0.0), i))


def score_policy(rows: list[dict[str, Any]], policy: str) -> dict[str, Any]:
    exact = answer = recoverable = 0
    selected_missing = 0
    for row in rows:
        candidates = row["candidates"]
        exact_indices = [i for i, c in enumerate(candidates) if c.get("is_exact")]
        if exact_indices:
            recoverable += 1
        selected: int | None
        if policy == "base":
            selected = top_by_base(candidates)
        elif policy == "entity_pair_base":
            pool = [i for i, c in enumerate(candidates) if entity_pair_match(c)]
            selected = top_by_base([candidates[i] for i in pool])
            selected = pool[selected] if selected is not None and pool else None
        elif policy == "qslot_value_oracle":
            positive_slots = set(row["positive_dslot_targets"])
            pool = [
                i
                for i, c in enumerate(candidates)
                if entity_pair_match(c) and positive_slots.intersection(candidate_dslots(c))
            ]
            selected = top_by_base([candidates[i] for i in pool])
            selected = pool[selected] if selected is not None and pool else None
        else:
            raise ValueError(policy)
        if selected is None:
            selected_missing += 1
            continue
        answer += int(is_correct(candidates[selected]))
        exact += int(bool(candidates[selected].get("is_exact")))
    return {
        "rows": len(rows),
        "answer": answer,
        "exact": exact,
        "recoverable_exact": recoverable,
        "selected_missing": selected_missing,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--targets-jsonl",
        type=Path,
        default=Path("runs/local/artifacts/stage923_stage918_bridge_teacher_targets.jsonl"),
    )
    parser.add_argument(
        "--output-targets-jsonl",
        type=Path,
        default=Path("runs/local/artifacts/stage950_relation_qslot_value_auxiliary_targets.jsonl"),
    )
    parser.add_argument(
        "--output-summary",
        type=Path,
        default=Path("runs/local/artifacts/stage950_relation_qslot_value_targets_summary.json"),
    )
    args = parser.parse_args()

    rows_by_split: dict[str, list[dict[str, Any]]] = defaultdict(list)
    compact_records: list[dict[str, Any]] = []
    for row in iter_jsonl(args.targets_jsonl):
        if row.get("operation") != "relation":
            continue
        candidates = list(row.get("candidates", []) or [])
        exact_indices = [i for i, c in enumerate(candidates) if c.get("is_exact")]
        positive_slots = sorted({slot for i in exact_indices for slot in candidate_dslots(candidates[i])})
        hard_negatives = [
            i
            for i, c in enumerate(candidates)
            if not c.get("is_exact")
            and entity_pair_match(c)
            and not set(candidate_dslots(c)).intersection(positive_slots)
        ]
        same_slot_negatives = [
            i
            for i, c in enumerate(candidates)
            if not c.get("is_exact")
            and bool(set(candidate_dslots(c)).intersection(positive_slots))
        ]
        compact = {
            "split": row.get("split"),
            "query_index": row.get("query_index"),
            "query_text": row.get("query_text"),
            "query_bridge": row.get("query_bridge", {}),
            "positive_candidate_indices": exact_indices,
            "positive_dslot_targets": positive_slots,
            "entity_pair_hard_negative_indices": hard_negatives,
            "same_slot_negative_indices": same_slot_negatives,
            "candidates": [
                {
                    "candidate_index": i,
                    "rank": c.get("rank"),
                    "base_score": c.get("base_score"),
                    "partition_probability": c.get("partition_probability"),
                    "teacher_bridge_score": c.get("teacher_bridge_score"),
                    "is_exact": bool(c.get("is_exact")),
                    "is_answer_match": bool(c.get("is_answer_match")),
                    "entity_pair_match": entity_pair_match(c),
                    "dslot": candidate_dslots(c),
                    "doc_index": c.get("doc_index"),
                    "doc_text": c.get("doc_text"),
                }
                for i, c in enumerate(candidates)
            ],
        }
        compact_records.append(compact)
        rows_by_split[str(row.get("split"))].append({**row, "positive_dslot_targets": positive_slots})

    args.output_targets_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with args.output_targets_jsonl.open("w") as f:
        for record in compact_records:
            f.write(json.dumps(record, sort_keys=True) + "\n")

    split_stats: dict[str, dict[str, Any]] = {}
    for split, rows in sorted(rows_by_split.items()):
        positive_slot_rows = sum(1 for r in rows if r["positive_dslot_targets"])
        ambiguous_rows = 0
        hard_negative_count = 0
        same_slot_negative_count = 0
        positive_slot_cardinality = Counter()
        for r in rows:
            candidates = r["candidates"]
            positive_slots = set(r["positive_dslot_targets"])
            positive_slot_cardinality[len(positive_slots)] += 1
            hard = [
                c
                for c in candidates
                if not c.get("is_exact")
                and entity_pair_match(c)
                and not set(candidate_dslots(c)).intersection(positive_slots)
            ]
            same = [
                c
                for c in candidates
                if not c.get("is_exact")
                and set(candidate_dslots(c)).intersection(positive_slots)
            ]
            hard_negative_count += len(hard)
            same_slot_negative_count += len(same)
            if hard and positive_slots:
                ambiguous_rows += 1
        split_stats[split] = {
            "rows": len(rows),
            "positive_slot_rows": positive_slot_rows,
            "positive_slot_cardinality": {str(k): v for k, v in sorted(positive_slot_cardinality.items())},
            "ambiguous_entity_pair_rows": ambiguous_rows,
            "entity_pair_hard_negative_count": hard_negative_count,
            "same_slot_negative_count": same_slot_negative_count,
            "policies": {
                "base": score_policy(rows, "base"),
                "entity_pair_base": score_policy(rows, "entity_pair_base"),
                "qslot_value_oracle": score_policy(rows, "qslot_value_oracle"),
            },
        }

    eval_stats = split_stats.get("eval", {})
    summary = {
        "artifact_kind": "stage950_relation_qslot_value_targets",
        "status": "diagnostic_target_materialization_no_frontier_change",
        "inputs": {"targets_jsonl": str(args.targets_jsonl)},
        "outputs": {"targets_jsonl": str(args.output_targets_jsonl)},
        "baseline": {
            "stage944_relation_answer_exact": [52, 52],
            "stage947_best_relation_answer_exact": [50, 50],
            "stage919_relation_typed_access_answer_exact": [84, 84],
        },
        "split_stats": split_stats,
        "decision": (
            "Materialized relation qslot/value auxiliary targets. The qslot/value oracle is diagnostic only because it uses "
            "the positive relation slot target; accepted progress requires predicting this compatibility inside the model."
        ),
        "interpretation": [
            "Entity+pair matching alone is ambiguous for relation; it does not select the correct target value when multiple relation slots share the same source/pair bridge.",
            "Positive dslot targets provide the missing relation/value axis and define hard negatives for the next auxiliary head.",
            "A model-owned Stage951 head should predict qslot/value compatibility from query/doc states and be gated into Stage944 only if relation exceeds 52/52 without regressions.",
        ],
        "next_steps": [
            {
                "stage": "Stage951",
                "target": "relation_qslot_value_auxiliary_head",
                "train": "Use positive_dslot_targets as latent supervision and entity_pair_hard_negative_indices as hard negatives.",
                "eval": "Use predicted compatibility only; do not feed positive_dslot_targets or suffix equality at eval.",
                "acceptance": "Relation >52/52 and global >252/235 under Stage944 no-regression.",
            }
        ],
    }
    args.output_summary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output_summary": str(args.output_summary), "eval": eval_stats}, indent=2)[:8000])


if __name__ == "__main__":
    main()
