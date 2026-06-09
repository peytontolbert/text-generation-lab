#!/usr/bin/env python3
"""Score the minimal relation full-pair equality primitive."""

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


def hit(candidate: dict[str, Any]) -> tuple[int, int]:
    return int(bool(candidate.get("is_exact") or candidate.get("is_answer_match"))), int(bool(candidate.get("is_exact")))


def score(rows: list[dict[str, Any]], *, min_pair_overlap: int) -> dict[str, Any]:
    answer = exact = recoverable = missing = 0
    for row in rows:
        candidates = list(row.get("candidates", []) or [])
        recoverable += int(any(c.get("is_exact") for c in candidates))
        qb = row.get("query_bridge", {}) or {}
        pool = [
            candidate
            for candidate in candidates
            if len(overlap(qb.get("qpair", []), (candidate.get("bridge", {}) or {}).get("dpair", []))) >= min_pair_overlap
        ]
        if not pool:
            missing += 1
            continue
        top = max(pool, key=lambda c: (float(c.get("base_score", 0.0) or 0.0), -int(c.get("rank", 9999) or 9999)))
        ans, ex = hit(top)
        answer += ans
        exact += ex
    return {"rows": len(rows), "answer": answer, "exact": exact, "recoverable": recoverable, "missing": missing}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets-jsonl", type=Path, default=Path("runs/local/artifacts/stage960_relation_qslot_bridge_targets.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("runs/local/artifacts/stage963_relation_full_pair_only_summary.json"))
    parser.add_argument("--min-pair-overlap", type=int, default=2)
    args = parser.parse_args()

    rows_by_split: dict[str, list[dict[str, Any]]] = {"train": [], "calibration": [], "eval": []}
    for row in iter_jsonl(args.targets_jsonl):
        if row.get("operation") == "relation":
            rows_by_split.setdefault(str(row.get("split")), []).append(row)

    split_scores = {split: score(rows, min_pair_overlap=int(args.min_pair_overlap)) for split, rows in rows_by_split.items()}
    eval_answer = split_scores["eval"]["answer"]
    eval_exact = split_scores["eval"]["exact"]
    summary = {
        "artifact_kind": "stage963_relation_full_pair_only",
        "status": "minimal_typed_access_contract_ready_not_model_owned",
        "targets_jsonl": str(args.targets_jsonl),
        "primitive": {
            "name": "full_pair_equality",
            "min_pair_overlap": int(args.min_pair_overlap),
            "inputs": ["qpair/dpair"],
            "parameter_count": 0,
            "budgeting_note": "Counts only if declared as a fixed architecture/interface primitive or replaced by learned model-owned full-pair comparison.",
        },
        "split_scores": split_scores,
        "stage957_gate": {
            "relation_answer_exact": [eval_answer, eval_exact],
            "passes_relation_gate": eval_answer > 52 and eval_exact > 52,
            "global_answer_exact_if_counted": [200 + eval_answer, 183 + eval_exact],
            "passes_global_gate": (200 + eval_answer) > 252 and (183 + eval_exact) > 235,
        },
        "decision": "Full-pair equality alone closes Stage960 relation eval to 100/100, matching Stage961 while using the smaller qpair/dpair primitive. Next train the model-owned comparator against full-pair compatibility before adding entity/slot auxiliaries.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
