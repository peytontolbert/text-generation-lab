#!/usr/bin/env python3
"""Score deterministic schema entity/slot equality ceilings without pair anchors."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ENTITY = re.compile(r"\b(?:qent|dent|entity)_([A-Za-z0-9]+)\b")
SLOT = re.compile(r"\b(?:qslot|dslot|slot)_([A-Za-z0-9]+)\b")


def _iter_jsonl(path: Path):
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def _rows_by_split(path: Path) -> dict[str, list[dict[str, Any]]]:
    rows = {"train": [], "calibration": [], "eval": []}
    for row in _iter_jsonl(path):
        if str(row.get("operation", "")) in {"composition", "relation"}:
            rows.setdefault(str(row.get("split")), []).append(row)
    return rows


def _hit(candidate: dict[str, Any]) -> tuple[int, int]:
    return int(bool(candidate.get("is_exact") or candidate.get("is_answer_match"))), int(bool(candidate.get("is_exact")))


def _base_index(candidates: list[dict[str, Any]]) -> int:
    return max(range(len(candidates)), key=lambda i: (float(candidates[i].get("base_score", 0.0) or 0.0), -int(candidates[i].get("rank", 9999) or 9999), -i))


def _score(rows: list[dict[str, Any]], policy: dict[str, tuple[int, int]]) -> dict[str, Any]:
    answer = exact = base_answer = base_exact = 0
    by_op: dict[str, dict[str, int]] = {}
    for row in rows:
        op = str(row.get("operation", "unknown"))
        stats = by_op.setdefault(op, {"rows": 0, "answer": 0, "exact": 0, "base_answer": 0, "base_exact": 0, "selected_rows": 0})
        stats["rows"] += 1
        candidates = list(row.get("candidates", []) or [])
        q_ent = set(ENTITY.findall(str(row.get("query_text", "") or "")))
        q_slot = set(SLOT.findall(str(row.get("query_text", "") or "")))
        ent_min, slot_min = policy.get(op, (0, 0))
        pool = []
        for idx, candidate in enumerate(candidates):
            doc = str(candidate.get("doc_text", "") or "")
            ent_overlap = len(q_ent.intersection(ENTITY.findall(doc)))
            slot_overlap = len(q_slot.intersection(SLOT.findall(doc)))
            if ent_overlap >= ent_min and slot_overlap >= slot_min:
                pool.append(idx)
        if pool:
            pred = max(pool, key=lambda i: (float(candidates[i].get("base_score", 0.0) or 0.0), -int(candidates[i].get("rank", 9999) or 9999), -i))
            stats["selected_rows"] += 1
        else:
            pred = _base_index(candidates)
        base = _base_index(candidates)
        ans, ex = _hit(candidates[pred])
        bans, bex = _hit(candidates[base])
        answer += ans
        exact += ex
        base_answer += bans
        base_exact += bex
        stats["answer"] += ans
        stats["exact"] += ex
        stats["base_answer"] += bans
        stats["base_exact"] += bex
    return {"rows": len(rows), "answer": answer, "exact": exact, "base_answer": base_answer, "base_exact": base_exact, "policy": {k: list(v) for k, v in policy.items()}, "by_operation": by_op}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets-jsonl", type=Path, default=Path("runs/local/artifacts/stage1013_no_anchor_targets.jsonl"))
    parser.add_argument("--output-json", type=Path, default=Path("runs/local/artifacts/stage1018_schema_equality_ceiling_summary.json"))
    args = parser.parse_args()

    rows = _rows_by_split(args.targets_jsonl)
    ops = sorted({str(row.get("operation")) for row in rows["calibration"]})
    policy: dict[str, tuple[int, int]] = {}
    selected_calibration: dict[str, Any] = {}
    for op in ops:
        candidates = []
        for ent_min in range(0, 3):
            for slot_min in range(0, 5):
                score = _score([row for row in rows["calibration"] if str(row.get("operation")) == op], {op: (ent_min, slot_min)})
                candidates.append((score["answer"], score["exact"], score["by_operation"][op]["selected_rows"], -ent_min - slot_min, ent_min, slot_min, score))
        best = max(candidates)
        policy[op] = (int(best[4]), int(best[5]))
        selected_calibration[op] = best[6]
    cal = _score(rows["calibration"], policy)
    ev = _score(rows["eval"], policy)
    summary = {
        "artifact_kind": "stage1018_schema_equality_ceiling",
        "status": "completed_schema_equality_ceiling",
        "targets_jsonl": str(args.targets_jsonl),
        "selected_policy": {k: list(v) for k, v in policy.items()},
        "selected_calibration_by_operation": selected_calibration,
        "calibration": cal,
        "eval": ev,
        "stage1011_anchor_frontier_answer_exact": [158, 142],
        "stage1014_no_anchor_fulltoken_answer_exact": [82, 66],
        "stage1015_learned_schema_answer_exact": [65, 49],
        "decision": "Diagnostic only: uses deterministic suffix equality over schema entity/slot markers to measure no-pair-anchor recoverability.",
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
