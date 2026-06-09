#!/usr/bin/env python3
"""Materialize operation-conditioned pair-arity teacher labels."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def iter_jsonl(path: Path):
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def overlap(a: list[Any], b: list[Any]) -> set[str]:
    return {str(x) for x in a or []}.intersection(str(y) for y in b or [])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets-jsonl", type=Path, default=Path("runs/local/artifacts/stage960_relation_qslot_bridge_targets.jsonl"))
    parser.add_argument("--policy-json", type=Path, default=Path("runs/local/artifacts/stage964_operation_pair_arity_policy_summary.json"))
    parser.add_argument("--output-jsonl", type=Path, default=Path("runs/local/artifacts/stage965_operation_pair_arity_teacher.jsonl"))
    parser.add_argument("--summary-json", type=Path, default=Path("runs/local/artifacts/stage965_operation_pair_arity_teacher_summary.json"))
    args = parser.parse_args()

    policy = json.loads(args.policy_json.read_text(encoding="utf-8"))
    selected_arities = {
        str(op): int(score["min_pair_overlap"])
        for op, score in policy.get("selected_by_operation", {}).items()
    }

    by_split_op: dict[str, dict[str, dict[str, int]]] = {}
    totals = {
        "rows": 0,
        "candidates": 0,
        "arity_positive_candidates": 0,
        "exact_arity_positive_candidates": 0,
        "arity_hard_negative_candidates": 0,
        "fallback_policy_rows": 0,
        "active_pair_policy_rows": 0,
    }

    args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with args.output_jsonl.open("w", encoding="utf-8") as out:
        for row in iter_jsonl(args.targets_jsonl):
            split = str(row.get("split"))
            op = str(row.get("operation"))
            arity = int(selected_arities.get(op, 0))
            stats = by_split_op.setdefault(split, {}).setdefault(
                op,
                {
                    "rows": 0,
                    "candidates": 0,
                    "arity_positive_candidates": 0,
                    "exact_arity_positive_candidates": 0,
                    "arity_hard_negative_candidates": 0,
                    "fallback_policy_rows": 0,
                    "active_pair_policy_rows": 0,
                    "recoverable_rows": 0,
                },
            )
            candidates = list(row.get("candidates", []) or [])
            qb = row.get("query_bridge", {}) or {}
            recoverable = any(candidate.get("is_exact") for candidate in candidates)
            row_arity_positive = False
            candidate_records = []
            for candidate_index, candidate in enumerate(candidates):
                cb = candidate.get("bridge", {}) or {}
                pair_overlap = overlap(qb.get("qpair", []), cb.get("dpair", []))
                arity_positive = arity > 0 and len(pair_overlap) >= arity
                is_exact = bool(candidate.get("is_exact"))
                hard_negative = arity_positive and not is_exact
                row_arity_positive = row_arity_positive or arity_positive
                candidate_records.append(
                    {
                        "candidate_index": candidate_index,
                        "rank": candidate.get("rank"),
                        "base_score": candidate.get("base_score"),
                        "is_exact": is_exact,
                        "is_answer_match": bool(candidate.get("is_answer_match")),
                        "pair_overlap_count": len(pair_overlap),
                        "selected_min_pair_overlap": arity,
                        "arity_positive": arity_positive,
                        "arity_hard_negative": hard_negative,
                    }
                )
                stats["candidates"] += 1
                totals["candidates"] += 1
                stats["arity_positive_candidates"] += int(arity_positive)
                totals["arity_positive_candidates"] += int(arity_positive)
                stats["exact_arity_positive_candidates"] += int(arity_positive and is_exact)
                totals["exact_arity_positive_candidates"] += int(arity_positive and is_exact)
                stats["arity_hard_negative_candidates"] += int(hard_negative)
                totals["arity_hard_negative_candidates"] += int(hard_negative)

            active_pair_policy = arity > 0
            fallback_policy = arity <= 0 or not row_arity_positive
            stats["rows"] += 1
            totals["rows"] += 1
            stats["recoverable_rows"] += int(recoverable)
            stats["active_pair_policy_rows"] += int(active_pair_policy)
            totals["active_pair_policy_rows"] += int(active_pair_policy)
            stats["fallback_policy_rows"] += int(fallback_policy)
            totals["fallback_policy_rows"] += int(fallback_policy)
            out.write(
                json.dumps(
                    {
                        "split": split,
                        "operation": op,
                        "recoverable": recoverable,
                        "selected_min_pair_overlap": arity,
                        "active_pair_policy": active_pair_policy,
                        "fallback_policy": fallback_policy,
                        "teacher": {
                            "primitive": "operation_conditioned_pair_arity",
                            "fallback_to_base": True,
                        },
                        "candidates": candidate_records,
                    },
                    sort_keys=True,
                )
                + "\n"
            )

    summary = {
        "artifact_kind": "stage965_operation_pair_arity_teacher",
        "status": "completed_teacher_target_export",
        "targets_jsonl": str(args.targets_jsonl),
        "policy_json": str(args.policy_json),
        "output_jsonl": str(args.output_jsonl),
        "selected_arities": selected_arities,
        "totals": totals,
        "by_split_operation": by_split_op,
        "target_use": "Train a counted operation-conditioned pair-arity comparator/router to reproduce Stage964 without external typed scoring.",
    }
    args.summary_json.parent.mkdir(parents=True, exist_ok=True)
    args.summary_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
