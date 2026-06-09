#!/usr/bin/env python3
"""Audit the declared budget for the Stage981 pair-overlap/count interface."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _iter_jsonl(path: Path):
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def _overlap(a: list[Any], b: list[Any]) -> set[str]:
    return {str(x) for x in a or []}.intersection(str(y) for y in b or [])


def _empty_split_stats() -> dict[str, Any]:
    return {
        "rows": 0,
        "candidate_rows": 0,
        "candidates": 0,
        "qpair_tokens": 0,
        "dpair_tokens": 0,
        "pair_token_cross_comparisons": 0,
        "pair_overlap_sum": 0,
        "pair_overlap_positive_candidates": 0,
        "arity_positive_candidates": 0,
        "exact_arity_positive_candidates": 0,
        "nonexact_arity_positive_candidates": 0,
    }


def _add_candidate_stats(stats: dict[str, Any], row: dict[str, Any], candidate: dict[str, Any], selected_arity: int) -> None:
    qpair = list((row.get("query_bridge", {}) or {}).get("qpair", []) or [])
    dpair = list((candidate.get("bridge", {}) or {}).get("dpair", []) or [])
    overlap = _overlap(qpair, dpair)
    stats["candidates"] += 1
    stats["qpair_tokens"] += len(qpair)
    stats["dpair_tokens"] += len(dpair)
    stats["pair_token_cross_comparisons"] += len(qpair) * len(dpair)
    stats["pair_overlap_sum"] += len(overlap)
    stats["pair_overlap_positive_candidates"] += int(bool(overlap))
    arity_positive = selected_arity > 0 and len(overlap) >= selected_arity
    stats["arity_positive_candidates"] += int(arity_positive)
    stats["exact_arity_positive_candidates"] += int(arity_positive and bool(candidate.get("is_exact")))
    stats["nonexact_arity_positive_candidates"] += int(arity_positive and not bool(candidate.get("is_exact")))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets-jsonl", type=Path, default=Path("runs/local/artifacts/stage975_pair_overlap_teacher_targets.jsonl"))
    parser.add_argument("--stage981-summary", type=Path, default=Path("runs/local/artifacts/stage981_100m_pair_interface_hybrid_summary.json"))
    parser.add_argument("--output-json", type=Path, default=Path("runs/local/artifacts/stage982_pair_comparator_budget_audit_summary.json"))
    args = parser.parse_args()

    stage981 = json.loads(args.stage981_summary.read_text(encoding="utf-8"))
    policy = dict(stage981["policy_by_operation"])
    selected_arities = {str(k): int(v) for k, v in stage981["selected_arities"].items()}
    split_stats: dict[str, dict[str, Any]] = {}
    op_stats: dict[str, dict[str, Any]] = {}
    total = _empty_split_stats()
    for row in _iter_jsonl(args.targets_jsonl):
        split = str(row.get("split", "unknown"))
        operation = str(row.get("operation", "unknown"))
        split_bucket = split_stats.setdefault(split, _empty_split_stats())
        op_bucket = op_stats.setdefault(operation, _empty_split_stats())
        split_bucket["rows"] += 1
        op_bucket["rows"] += 1
        total["rows"] += 1
        if policy.get(operation) != "stage968_counted_pair_overlap":
            continue
        split_bucket["candidate_rows"] += 1
        op_bucket["candidate_rows"] += 1
        total["candidate_rows"] += 1
        selected_arity = int(selected_arities.get(operation, 0))
        for candidate in list(row.get("candidates", []) or []):
            _add_candidate_stats(split_bucket, row, candidate, selected_arity)
            _add_candidate_stats(op_bucket, row, candidate, selected_arity)
            _add_candidate_stats(total, row, candidate, selected_arity)

    parameter_count = int(stage981.get("parameter_count", 0))
    router_parameter_count = int(stage981.get("router_parameter_count", 0))
    counted_parameter_denominator = parameter_count + router_parameter_count
    eval_score = stage981["split_scores"]["eval"]
    summary = {
        "artifact_kind": "stage982_pair_comparator_budget_audit",
        "status": "completed_pair_comparator_budget_audit",
        "stage981_summary": str(args.stage981_summary),
        "targets_jsonl": str(args.targets_jsonl),
        "policy_by_operation": policy,
        "selected_arities": selected_arities,
        "model_parameter_count": parameter_count,
        "router_parameter_count": router_parameter_count,
        "fixed_pair_comparator_trainable_parameters": 0,
        "counted_parameter_denominator_if_fixed_comparator_allowed": counted_parameter_denominator,
        "eval_answer_exact": [int(eval_score["answer"]), int(eval_score["exact"])],
        "implied_full_answer_exact": stage981["implied_full_answer_exact"],
        "split_comparator_stats": split_stats,
        "operation_comparator_stats": op_stats,
        "total_comparator_stats": total,
        "budget_contract": {
            "allowed_claim": "100M plus declared fixed pair-overlap/count interface and 97-param router reaches Stage981.",
            "not_allowed_claim": "Bridge-free model-owned KBPP or free-form generation parity.",
            "next_gate_if_fixed_primitive_disallowed": "Replace pair-token set intersection with an encoder-owned or learned equality/count comparator and reproduce the Stage981 policy.",
        },
        "decision": "The only trainable interface parameters beyond the 100M bundle are the 97 router parameters. The pair-overlap/count comparator is a fixed declared primitive with zero trainable parameters but nonzero compute/interface access. Count it explicitly as a primitive; do not treat Stage981 as bridge-free model-owned KBPP.",
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
