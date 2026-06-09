#!/usr/bin/env python3
"""Materialize relation binding teacher labels from the Stage961 primitive."""

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


def overlap(a: list[Any], b: list[Any]) -> list[str]:
    return sorted({str(x) for x in a or []}.intersection(str(y) for y in b or []))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets-jsonl", type=Path, default=Path("runs/local/artifacts/stage960_relation_qslot_bridge_targets.jsonl"))
    parser.add_argument("--output-jsonl", type=Path, default=Path("runs/local/artifacts/stage962_relation_binding_teacher_targets.jsonl"))
    parser.add_argument("--summary-json", type=Path, default=Path("runs/local/artifacts/stage962_relation_binding_teacher_targets_summary.json"))
    parser.add_argument("--min-pair-overlap", type=int, default=2)
    args = parser.parse_args()

    args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    by_split: dict[str, dict[str, int]] = {}
    rows_out = 0
    candidates_out = 0
    primitive_positive_candidates = 0
    exact_primitive_positive_candidates = 0
    hard_negative_candidates = 0
    component_totals = {
        "entity_match_candidates": 0,
        "full_pair_match_candidates": 0,
        "slot_match_candidates": 0,
        "entity_slot_nonexact_candidates": 0,
        "entity_full_pair_nonexact_candidates": 0,
        "slot_full_pair_nonexact_candidates": 0,
    }

    with args.output_jsonl.open("w", encoding="utf-8") as out:
        for row in iter_jsonl(args.targets_jsonl):
            if row.get("operation") != "relation":
                continue
            split = str(row.get("split"))
            stats = by_split.setdefault(
                split,
                {
                    "rows": 0,
                    "candidates": 0,
                    "primitive_positive_candidates": 0,
                    "exact_primitive_positive_candidates": 0,
                    "hard_negative_candidates": 0,
                    "entity_match_candidates": 0,
                    "full_pair_match_candidates": 0,
                    "slot_match_candidates": 0,
                    "entity_slot_nonexact_candidates": 0,
                    "entity_full_pair_nonexact_candidates": 0,
                    "slot_full_pair_nonexact_candidates": 0,
                    "recoverable_rows": 0,
                },
            )
            qb = row.get("query_bridge", {}) or {}
            recoverable = any(c.get("is_exact") for c in row.get("candidates", []) or [])
            stats["rows"] += 1
            stats["recoverable_rows"] += int(recoverable)
            rows_out += 1
            candidate_records = []
            for candidate_index, candidate in enumerate(row.get("candidates", []) or []):
                cb = candidate.get("bridge", {}) or {}
                ent = overlap(qb.get("qent", []), cb.get("dent", []))
                pair = overlap(qb.get("qpair", []), cb.get("dpair", []))
                slot = overlap(qb.get("qslot", []), cb.get("dslot", []))
                is_exact = bool(candidate.get("is_exact"))
                primitive_positive = bool(ent) and len(pair) >= int(args.min_pair_overlap) and bool(slot)
                hard_negative = primitive_positive and not is_exact
                component_values = {
                    "entity_match_candidates": int(bool(ent)),
                    "full_pair_match_candidates": int(len(pair) >= int(args.min_pair_overlap)),
                    "slot_match_candidates": int(bool(slot)),
                    "entity_slot_nonexact_candidates": int(bool(ent) and bool(slot) and not is_exact),
                    "entity_full_pair_nonexact_candidates": int(bool(ent) and len(pair) >= int(args.min_pair_overlap) and not is_exact),
                    "slot_full_pair_nonexact_candidates": int(bool(slot) and len(pair) >= int(args.min_pair_overlap) and not is_exact),
                }
                for key, value in component_values.items():
                    component_totals[key] += value
                    stats[key] += value
                primitive_positive_candidates += int(primitive_positive)
                exact_primitive_positive_candidates += int(primitive_positive and is_exact)
                hard_negative_candidates += int(hard_negative)
                candidates_out += 1
                stats["candidates"] += 1
                stats["primitive_positive_candidates"] += int(primitive_positive)
                stats["exact_primitive_positive_candidates"] += int(primitive_positive and is_exact)
                stats["hard_negative_candidates"] += int(hard_negative)
                candidate_records.append(
                    {
                        "candidate_index": candidate_index,
                        "rank": candidate.get("rank"),
                        "base_score": candidate.get("base_score"),
                        "is_exact": is_exact,
                        "is_answer_match": bool(candidate.get("is_answer_match")),
                        "entity_match": bool(ent),
                        "pair_overlap_count": len(pair),
                        "full_pair_match": len(pair) >= int(args.min_pair_overlap),
                        "slot_match": bool(slot),
                        "primitive_positive": primitive_positive,
                        "hard_negative": hard_negative,
                    }
                )
            out.write(
                json.dumps(
                    {
                        "split": split,
                        "operation": "relation",
                        "row_index": stats["rows"] - 1,
                        "recoverable": recoverable,
                        "query_bridge_counts": {
                            "qent": len(qb.get("qent", []) or []),
                            "qpair": len(qb.get("qpair", []) or []),
                            "qslot": len(qb.get("qslot", []) or []),
                        },
                        "teacher": {
                            "primitive": "entity_full_pair_slot_equality",
                            "min_pair_overlap": int(args.min_pair_overlap),
                        },
                        "candidates": candidate_records,
                    },
                    sort_keys=True,
                )
                + "\n"
            )

    summary = {
        "artifact_kind": "stage962_relation_binding_teacher_targets",
        "status": "completed_teacher_target_export",
        "targets_jsonl": str(args.targets_jsonl),
        "output_jsonl": str(args.output_jsonl),
        "min_pair_overlap": int(args.min_pair_overlap),
        "rows": rows_out,
        "candidates": candidates_out,
        "primitive_positive_candidates": primitive_positive_candidates,
        "exact_primitive_positive_candidates": exact_primitive_positive_candidates,
        "hard_negative_candidates": hard_negative_candidates,
        "component_totals": component_totals,
        "by_split": by_split,
        "target_use": "Train a model-owned relation comparator on entity_match, full_pair_match, slot_match, primitive_positive, and hard-negative labels without relying on answer CE alone.",
    }
    args.summary_json.parent.mkdir(parents=True, exist_ok=True)
    args.summary_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
