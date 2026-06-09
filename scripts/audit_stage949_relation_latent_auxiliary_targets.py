#!/usr/bin/env python3
"""Audit relation auxiliary targets needed after residual-head saturation."""

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


def bridge_flags(candidate: dict[str, Any]) -> dict[str, bool]:
    bridge = candidate.get("bridge", {}) or {}
    return {
        "entity_suffix_match": bool(bridge.get("entity_suffix_match")),
        "pair_suffix_match": bool(bridge.get("pair_suffix_match")),
        "slot_suffix_match": bool(bridge.get("slot_suffix_match")),
        "claim_suffix_match": bool(bridge.get("claim_suffix_match")),
        "has_qslot": bool(bridge.get("qslot")),
        "has_dslot": bool(bridge.get("dslot")),
        "has_qpair": bool(bridge.get("qpair")),
        "has_dpair": bool(bridge.get("dpair")),
        "has_qent": bool(bridge.get("qent")),
        "has_dent": bool(bridge.get("dent")),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--targets-jsonl",
        type=Path,
        default=Path("runs/local/artifacts/stage923_stage918_bridge_teacher_targets.jsonl"),
    )
    parser.add_argument(
        "--stage946-summary",
        type=Path,
        default=Path("runs/local/artifacts/stage946_model_side_gap_audit_summary.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("runs/local/artifacts/stage949_relation_latent_auxiliary_targets_summary.json"),
    )
    args = parser.parse_args()

    stage946 = json.loads(args.stage946_summary.read_text())
    rows_by_split: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in iter_jsonl(args.targets_jsonl):
        if row.get("operation") == "relation":
            rows_by_split[str(row.get("split"))].append(row)

    split_stats: dict[str, dict[str, Any]] = {}
    examples: dict[str, list[dict[str, Any]]] = {"ambiguous_pair_rows": [], "rank2_positive_rows": []}
    for split, rows in sorted(rows_by_split.items()):
        stats: dict[str, Any] = {
            "rows": len(rows),
            "exact_recoverable": 0,
            "base_exact": 0,
            "positive_rank_buckets": Counter(),
            "positive_rank_histogram": Counter(),
            "candidate_flag_counts": Counter(),
            "exact_candidate_flag_counts": Counter(),
            "nonexact_candidate_flag_counts": Counter(),
            "ambiguous_pair_rows": 0,
            "ambiguous_pair_false_candidates": 0,
            "positive_has_pair_match": 0,
            "positive_has_entity_match": 0,
            "positive_has_slot_match": 0,
            "query_has_slot_rows": 0,
            "doc_has_slot_rows": 0,
            "teacher_score_by_label": defaultdict(list),
        }
        for row in rows:
            candidates = list(row.get("candidates", []) or [])
            if not candidates:
                continue
            query_bridge = row.get("query_bridge", {}) or {}
            if query_bridge.get("qslot"):
                stats["query_has_slot_rows"] += 1
            if any((c.get("bridge", {}) or {}).get("dslot") for c in candidates):
                stats["doc_has_slot_rows"] += 1

            base_top = min(candidates, key=lambda c: int(c.get("rank", 10**9)))
            stats["base_exact"] += int(bool(base_top.get("is_exact")))
            exact_candidates = [c for c in candidates if c.get("is_exact")]
            if exact_candidates:
                stats["exact_recoverable"] += 1
                best_exact = min(exact_candidates, key=lambda c: int(c.get("rank", 10**9)))
                rank = int(best_exact.get("rank", 10**9))
                stats["positive_rank_buckets"][rank_bucket(rank)] += 1
                stats["positive_rank_histogram"][rank] += 1
                flags = bridge_flags(best_exact)
                stats["positive_has_pair_match"] += int(flags["pair_suffix_match"])
                stats["positive_has_entity_match"] += int(flags["entity_suffix_match"])
                stats["positive_has_slot_match"] += int(flags["slot_suffix_match"])
                if rank == 2 and len(examples["rank2_positive_rows"]) < 5:
                    examples["rank2_positive_rows"].append(
                        {
                            "split": split,
                            "query_index": row.get("query_index"),
                            "query_text": row.get("query_text"),
                            "positive_rank": rank,
                            "base_top_flags": bridge_flags(base_top),
                            "positive_flags": flags,
                            "base_top_teacher_bridge_score": base_top.get("teacher_bridge_score"),
                            "positive_teacher_bridge_score": best_exact.get("teacher_bridge_score"),
                            "base_top_doc_text": base_top.get("doc_text"),
                            "positive_doc_text": best_exact.get("doc_text"),
                        }
                    )

            false_pair_matches = 0
            true_pair_matches = 0
            for candidate in candidates:
                flags = bridge_flags(candidate)
                key = "|".join(k for k, v in flags.items() if v) or "none"
                stats["candidate_flag_counts"][key] += 1
                label_key = "exact" if candidate.get("is_exact") else "nonexact"
                stats["teacher_score_by_label"][label_key].append(float(candidate.get("teacher_bridge_score", 0.0) or 0.0))
                if candidate.get("is_exact"):
                    stats["exact_candidate_flag_counts"][key] += 1
                else:
                    stats["nonexact_candidate_flag_counts"][key] += 1
                    if flags["pair_suffix_match"] and flags["entity_suffix_match"]:
                        false_pair_matches += 1
                if flags["pair_suffix_match"] and flags["entity_suffix_match"] and candidate.get("is_exact"):
                    true_pair_matches += 1
            if false_pair_matches and true_pair_matches:
                stats["ambiguous_pair_rows"] += 1
                stats["ambiguous_pair_false_candidates"] += false_pair_matches
                if split == "eval" and len(examples["ambiguous_pair_rows"]) < 5:
                    examples["ambiguous_pair_rows"].append(
                        {
                            "query_index": row.get("query_index"),
                            "query_text": row.get("query_text"),
                            "false_pair_matches": false_pair_matches,
                            "true_pair_matches": true_pair_matches,
                            "candidates": [
                                {
                                    "rank": c.get("rank"),
                                    "is_exact": bool(c.get("is_exact")),
                                    "teacher_bridge_score": c.get("teacher_bridge_score"),
                                    "flags": bridge_flags(c),
                                    "doc_text": c.get("doc_text"),
                                }
                                for c in candidates
                                if bridge_flags(c)["pair_suffix_match"] and bridge_flags(c)["entity_suffix_match"]
                            ][:8],
                        }
                    )

        summarized_scores = {}
        for label, values in stats["teacher_score_by_label"].items():
            if values:
                summarized_scores[label] = {
                    "count": len(values),
                    "mean": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values),
                }
        stats["teacher_score_by_label"] = summarized_scores
        for key in [
            "positive_rank_buckets",
            "positive_rank_histogram",
            "candidate_flag_counts",
            "exact_candidate_flag_counts",
            "nonexact_candidate_flag_counts",
        ]:
            stats[key] = {str(k): v for k, v in sorted(stats[key].items())}
        split_stats[split] = stats

    eval_stats = split_stats.get("eval", {})
    summary = {
        "artifact_kind": "stage949_relation_latent_auxiliary_targets",
        "status": "diagnostic_target_materialization_no_frontier_change",
        "inputs": {
            "targets_jsonl": str(args.targets_jsonl),
            "stage946_summary": str(args.stage946_summary),
        },
        "baseline": {
            "stage944_relation_answer_exact": [52, 52],
            "stage919_relation_typed_access_answer_exact": [84, 84],
            "candidate_recoverable_relation_answer_exact": stage946["operation_gaps"]["relation"]["recoverable_answer_exact"],
            "stage947_best_relation_answer_exact": [50, 50],
        },
        "split_stats": split_stats,
        "examples": examples,
        "interpretation": [
            "Relation positives often require more than entity/pair agreement; false candidates can share entity and pair matches with the exact candidate.",
            "Relation queries in this surface do not expose qslot, while candidate docs do expose dslot. This leaves relation/value disambiguation under-specified for a model that only sees current frozen residual features.",
            "The next trainable target should predict a latent relation slot/value compatibility signal from query/doc states, then feed that prediction into the Stage944 scorer under a no-regression gate.",
        ],
        "next_steps": [
            {
                "stage": "Stage950",
                "target": "relation_slot_value_auxiliary_head",
                "training_signal": "Use exact candidates as positives and same entity/pair false matches as hard negatives; predict latent relation/value compatibility from encoder states.",
                "acceptance": "Relation >52/52 and global >252/235 with Stage944 preserved for other operations.",
            },
            {
                "stage": "Stage951",
                "target": "surface_patch_relation_query_slot",
                "training_signal": "Expose side-invariant relation slot aliases in relation queries, then rerun the latent auxiliary without suffix-similarity features at eval.",
                "acceptance": "Improves model-owned relation recovery without direct qid/answer leakage.",
            },
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(args.output), "eval": eval_stats}, indent=2)[:8000])


if __name__ == "__main__":
    main()
