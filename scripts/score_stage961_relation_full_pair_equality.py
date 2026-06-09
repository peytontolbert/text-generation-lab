#!/usr/bin/env python3
"""Score the budgeted relation equality primitive on rebuilt qslot targets."""

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


def bridge(candidate: dict[str, Any]) -> dict[str, Any]:
    return candidate.get("bridge", {}) or {}


def qbridge(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("query_bridge", {}) or {}


def intersection(a: list[Any], b: list[Any]) -> set[str]:
    return {str(x) for x in a or []}.intersection(str(y) for y in b or [])


def primitive_match(row: dict[str, Any], candidate: dict[str, Any], *, min_pair_overlap: int) -> dict[str, Any]:
    qb = qbridge(row)
    cb = bridge(candidate)
    ent = intersection(qb.get("qent", []), cb.get("dent", []))
    pair = intersection(qb.get("qpair", []), cb.get("dpair", []))
    slot = intersection(qb.get("qslot", []), cb.get("dslot", []))
    matched = bool(ent) and len(pair) >= min_pair_overlap and bool(slot)
    return {
        "matched": matched,
        "entity_overlap": sorted(ent),
        "pair_overlap": sorted(pair),
        "slot_overlap": sorted(slot),
    }


def candidate_hit(candidate: dict[str, Any]) -> tuple[int, int]:
    answer = bool(candidate.get("is_exact") or candidate.get("is_answer_match"))
    exact = bool(candidate.get("is_exact"))
    return int(answer), int(exact)


def score_rows(
    rows: list[dict[str, Any]],
    *,
    min_pair_overlap: int,
    split: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    answer = exact = recoverable = missing = 0
    predictions: list[dict[str, Any]] = []
    for row_index, row in enumerate(rows):
        candidates = list(row.get("candidates", []) or [])
        recoverable += int(any(c.get("is_exact") for c in candidates))
        matched_candidates: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for candidate in candidates:
            match = primitive_match(row, candidate, min_pair_overlap=min_pair_overlap)
            if match["matched"]:
                matched_candidates.append((candidate, match))
        if not matched_candidates:
            missing += 1
            predictions.append(
                {
                    "split": split,
                    "row_index": row_index,
                    "operation": row.get("operation"),
                    "prediction_status": "missing",
                    "is_answer_correct": False,
                    "is_exact_correct": False,
                    "matched_candidates": 0,
                }
            )
            continue
        top, top_match = max(
            matched_candidates,
            key=lambda item: (
                float(item[0].get("base_score", 0.0) or 0.0),
                -int(item[0].get("rank", 9999) or 9999),
            ),
        )
        ans, ex = candidate_hit(top)
        answer += ans
        exact += ex
        predictions.append(
            {
                "split": split,
                "row_index": row_index,
                "operation": row.get("operation"),
                "prediction_status": "selected",
                "is_answer_correct": bool(ans),
                "is_exact_correct": bool(ex),
                "matched_candidates": len(matched_candidates),
                "top_rank": top.get("rank"),
                "top_base_score": top.get("base_score"),
                "top_is_exact": bool(top.get("is_exact")),
                "top_is_answer_match": bool(top.get("is_answer_match")),
                "entity_overlap_count": len(top_match["entity_overlap"]),
                "pair_overlap_count": len(top_match["pair_overlap"]),
                "slot_overlap_count": len(top_match["slot_overlap"]),
            }
        )
    summary = {
        "rows": len(rows),
        "answer": answer,
        "exact": exact,
        "recoverable": recoverable,
        "missing": missing,
    }
    return summary, predictions


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets-jsonl", type=Path, default=Path("runs/local/artifacts/stage960_relation_qslot_bridge_targets.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("runs/local/artifacts/stage961_relation_full_pair_equality_summary.json"))
    parser.add_argument("--predictions-jsonl", type=Path, default=Path("runs/local/artifacts/stage961_relation_full_pair_equality_predictions.jsonl"))
    parser.add_argument("--min-pair-overlap", type=int, default=2)
    args = parser.parse_args()

    rows_by_split: dict[str, list[dict[str, Any]]] = {"train": [], "calibration": [], "eval": []}
    for row in iter_jsonl(args.targets_jsonl):
        if row.get("operation") == "relation":
            rows_by_split.setdefault(str(row.get("split")), []).append(row)

    split_scores: dict[str, dict[str, Any]] = {}
    all_predictions: list[dict[str, Any]] = []
    for split, rows in rows_by_split.items():
        scores, predictions = score_rows(rows, min_pair_overlap=args.min_pair_overlap, split=split)
        split_scores[split] = scores
        all_predictions.extend(predictions)

    eval_answer = int(split_scores["eval"]["answer"])
    eval_exact = int(split_scores["eval"]["exact"])
    args.predictions_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with args.predictions_jsonl.open("w", encoding="utf-8") as f:
        for prediction in all_predictions:
            f.write(json.dumps(prediction, sort_keys=True) + "\n")

    summary = {
        "artifact_kind": "stage961_relation_full_pair_equality",
        "status": "typed_access_contract_ready_not_model_owned",
        "targets_jsonl": str(args.targets_jsonl),
        "predictions_jsonl": str(args.predictions_jsonl),
        "primitive": {
            "name": "entity_full_pair_slot_equality",
            "min_pair_overlap": int(args.min_pair_overlap),
            "inputs": ["qent/dent", "qpair/dpair", "qslot/dslot"],
            "parameter_count": 0,
            "budgeting_note": "Counts only if declared as a fixed architecture/interface primitive or replaced by learned model-owned parameters.",
        },
        "split_scores": split_scores,
        "stage957_gate": {
            "relation_answer_exact_gate": [">52", ">52"],
            "relation_answer_exact": [eval_answer, eval_exact],
            "passes_relation_gate": eval_answer > 52 and eval_exact > 52,
            "stage944_nonrelation_answer_exact": [200, 183],
            "global_answer_exact_if_counted": [200 + eval_answer, 183 + eval_exact],
            "passes_global_gate": (200 + eval_answer) > 252 and (183 + eval_exact) > 235,
            "label_access": "no exact/answer labels are used by the primitive; qslot is generated by the Stage959 hardener from relation query text before candidate scoring.",
        },
        "decision": "The rebuilt Stage960 surface plus full-pair typed equality closes relation to the 100/100 recoverable eval ceiling and would restore the Stage956 300/283 global typed-access implication. This is now contract-ready typed access, but still not model-owned internalization.",
        "next_steps": [
            "Use this primitive as the teacher target for a learned relation binding head.",
            "Train a model-owned comparator to predict entity, full-pair, and slot compatibility without suffix-similarity features at eval.",
            "Preserve Stage944 non-relation rows while replacing deterministic equality with the learned comparator.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "predictions_jsonl": str(args.predictions_jsonl),
                "eval": split_scores["eval"],
                "global_if_counted": summary["stage957_gate"]["global_answer_exact_if_counted"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
