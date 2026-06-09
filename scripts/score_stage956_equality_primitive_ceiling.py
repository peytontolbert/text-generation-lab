#!/usr/bin/env python3
"""Score deterministic typed equality primitive on the Stage952 patched relation surface."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def iter_jsonl(path: Path):
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def bridge(candidate: dict[str, Any]) -> dict[str, Any]:
    return candidate.get("bridge", {}) or {}


def qbridge(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("query_bridge", {}) or {}


def intersects(a: list[Any], b: list[Any]) -> bool:
    return bool({str(x) for x in a}.intersection(str(y) for y in b))


def exact_match(row: dict[str, Any], candidate: dict[str, Any], require_slot: bool = True) -> bool:
    qb = qbridge(row)
    cb = bridge(candidate)
    ent = intersects(qb.get("qent", []), cb.get("dent", []))
    pair = intersects(qb.get("qpair", []), cb.get("dpair", []))
    slot = intersects(qb.get("qslot", []), cb.get("dslot", []))
    return ent and pair and (slot or not require_slot)


def hit(candidate: dict[str, Any]) -> tuple[int, int]:
    return int(bool(candidate.get("is_exact") or candidate.get("is_answer_match"))), int(bool(candidate.get("is_exact")))


def score_rows(rows: list[dict[str, Any]], policy: str) -> dict[str, Any]:
    answer = exact = recoverable = missing = 0
    for row in rows:
        candidates = list(row.get("candidates", []) or [])
        if any(c.get("is_exact") for c in candidates):
            recoverable += 1
        if policy == "base":
            pool = candidates
        elif policy == "entity_pair_equality":
            pool = [c for c in candidates if exact_match(row, c, require_slot=False)]
        elif policy == "entity_pair_slot_equality":
            pool = [c for c in candidates if exact_match(row, c, require_slot=True)]
        else:
            raise ValueError(policy)
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
    parser.add_argument("--targets-jsonl", type=Path, default=Path("runs/local/artifacts/stage952_relation_query_slot_patched_targets.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("runs/local/artifacts/stage956_equality_primitive_ceiling_summary.json"))
    args = parser.parse_args()

    rows_by_split: dict[str, list[dict[str, Any]]] = {"train": [], "calibration": [], "eval": []}
    for row in iter_jsonl(args.targets_jsonl):
        if row.get("operation") == "relation":
            rows_by_split.setdefault(str(row.get("split")), []).append(row)

    split_scores = {}
    for split, rows in rows_by_split.items():
        split_scores[split] = {
            "base": score_rows(rows, "base"),
            "entity_pair_equality": score_rows(rows, "entity_pair_equality"),
            "entity_pair_slot_equality": score_rows(rows, "entity_pair_slot_equality"),
        }

    eval_exact = split_scores["eval"]["entity_pair_slot_equality"]["exact"]
    eval_answer = split_scores["eval"]["entity_pair_slot_equality"]["answer"]
    summary = {
        "artifact_kind": "stage956_equality_primitive_ceiling",
        "status": "diagnostic_equality_primitive_ceiling_no_model_owned_claim",
        "targets_jsonl": str(args.targets_jsonl),
        "split_scores": split_scores,
        "frontier_implication_if_counted_primitive_accepted": {
            "stage944_nonrelation_answer_exact": [200, 183],
            "relation_answer_exact": [eval_answer, eval_exact],
            "global_answer_exact": [200 + eval_answer, 183 + eval_exact],
            "gain_over_stage944_answer_exact": [eval_answer - 52, eval_exact - 52],
        },
        "accounting": {
            "learned_parameter_count": 0,
            "primitive_inputs": ["qent/dent", "qpair/dpair", "qslot/dslot"],
            "feature_caveat": "This uses deterministic set intersection over patched bridge tokens. It is a ceiling/accounting diagnostic, not model-owned KBPP.",
            "acceptance_requirement": "To count toward 100M model-owned KBPP, the qslot aliases must be generated from relation text without copied eval positives, and the comparison primitive must be part of the model/interface budget.",
        },
        "decision": "Diagnostic only. Deterministic typed equality on the patched relation surface closes relation to the recoverable 100/100 ceiling and would lift the preserved global score to 300/283, but it is external equality unless explicitly budgeted as a model primitive.",
        "next_steps": [
            {
                "stage": "Stage957",
                "target": "budgeted_equality_primitive_spec",
                "goal": "Define how a counted equality/comparison primitive is represented in the 100M budget and how qslot aliases are generated from relation text.",
            },
            {
                "stage": "Stage958",
                "target": "larger_qslot_matching_curriculum",
                "goal": "Train learned comparison on many qslot/dslot examples before reattempting model-owned scoring.",
            },
        ],
    }
    args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(args.output), "eval": split_scores["eval"], "global_if_counted": summary["frontier_implication_if_counted_primitive_accepted"]["global_answer_exact"]}, indent=2))


if __name__ == "__main__":
    main()
