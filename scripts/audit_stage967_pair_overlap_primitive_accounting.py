#!/usr/bin/env python3
"""Audit and account for the qpair/dpair shared-anchor primitive."""

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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--teacher-jsonl", type=Path, default=Path("runs/local/artifacts/stage965_operation_pair_arity_teacher.jsonl"))
    parser.add_argument("--stage966-json", type=Path, default=Path("runs/local/artifacts/stage966_pair_arity_router_summary.json"))
    parser.add_argument("--output-json", type=Path, default=Path("runs/local/artifacts/stage967_pair_overlap_primitive_accounting_summary.json"))
    args = parser.parse_args()

    by_split_op: dict[str, dict[str, dict[str, Any]]] = {}
    pair_overlap_histogram: dict[str, int] = {}
    for row in iter_jsonl(args.teacher_jsonl):
        split = str(row.get("split"))
        op = str(row.get("operation"))
        stats = by_split_op.setdefault(split, {}).setdefault(
            op,
            {
                "rows": 0,
                "candidates": 0,
                "exact_candidates": 0,
                "arity_positive_candidates": 0,
                "exact_arity_positive_candidates": 0,
                "nonexact_arity_positive_candidates": 0,
                "pair_overlap_histogram": {},
            },
        )
        stats["rows"] += 1
        for candidate in row.get("candidates", []) or []:
            pair_overlap = int(candidate.get("pair_overlap_count", 0) or 0)
            is_exact = bool(candidate.get("is_exact"))
            arity_positive = bool(candidate.get("arity_positive"))
            stats["candidates"] += 1
            stats["exact_candidates"] += int(is_exact)
            stats["arity_positive_candidates"] += int(arity_positive)
            stats["exact_arity_positive_candidates"] += int(is_exact and arity_positive)
            stats["nonexact_arity_positive_candidates"] += int((not is_exact) and arity_positive)
            key = str(pair_overlap)
            stats["pair_overlap_histogram"][key] = int(stats["pair_overlap_histogram"].get(key, 0)) + 1
            pair_overlap_histogram[key] = int(pair_overlap_histogram.get(key, 0)) + 1

    stage966 = json.loads(args.stage966_json.read_text(encoding="utf-8"))
    stage966_eval = stage966["eval_with_calibration_selected"]
    summary = {
        "artifact_kind": "stage967_pair_overlap_primitive_accounting",
        "status": "completed_primitive_accounting_audit",
        "teacher_jsonl": str(args.teacher_jsonl),
        "stage966_json": str(args.stage966_json),
        "primitive_definition": {
            "name": "qpair_dpair_shared_anchor_overlap_count",
            "important_naming_note": "qpair/dpair codes are shared-anchor codes for original query/doc tokens present on both sides, not learned tuple-pair embeddings.",
            "construction": [
                "Harden query text and doc text independently into side-specific qent/qslot/qclaim and dent/dslot/dclaim aliases.",
                "For each original token present in both the query alias map and doc alias map, emit qpair_<stable_suffix> on the query and dpair_<same_suffix> on the doc.",
                "At scoring time, pair_overlap_count is the set intersection size of qpair suffixes and dpair suffixes.",
            ],
            "label_access": "The primitive uses query/doc surface maps and the fixed pair-code salt; it does not inspect is_exact, answer-match labels, or candidate ranks.",
            "learned_parameter_count": 0,
            "router_parameter_count": int(stage966.get("parameter_count", 0)),
        },
        "stage966_counted_router_result": {
            "target_answer_exact": [int(stage966_eval["answer"]), int(stage966_eval["exact"])],
            "implied_full_answer_exact": stage966.get("implied_full_answer_exact"),
            "router_parameters": int(stage966.get("parameter_count", 0)),
            "remaining_external_primitive": "pair_overlap_count",
        },
        "pair_overlap_histogram": pair_overlap_histogram,
        "by_split_operation": by_split_op,
        "budget_interpretation": {
            "if_declared_fixed_interface": "Stage966 can be counted as a 97-parameter learned router plus a fixed set-intersection primitive over bridge tokens.",
            "if_model_owned_required": "The next proof must learn qpair/dpair shared-anchor equality or expose an equivalent equality circuit inside the model/interface budget.",
            "why_this_matters": "Stage964/966 gains are from reusable semantic anchor comparison, not from storing more facts in dense weights.",
        },
        "decision": "The remaining high-value primitive is shared-anchor overlap counting. The route to model-owned KBPP is now narrowed to learning or explicitly budgeting this equality/count circuit, then retaining the 97-parameter arity router.",
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
