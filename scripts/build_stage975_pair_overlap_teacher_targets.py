#!/usr/bin/env python3
"""Add Stage968 pair-overlap teacher scores to Stage960 candidate targets."""

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


def suffix_overlap(a: list[Any], b: list[Any]) -> int:
    return len({str(x) for x in a or []}.intersection(str(y) for y in b or []))


def selected_arities(path: Path) -> dict[str, int]:
    policy = json.loads(path.read_text(encoding="utf-8"))
    return {str(op): int(score["min_pair_overlap"]) for op, score in policy.get("selected_by_operation", {}).items()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets-jsonl", type=Path, default=Path("runs/local/artifacts/stage960_relation_qslot_bridge_targets.jsonl"))
    parser.add_argument("--policy-json", type=Path, default=Path("runs/local/artifacts/stage964_operation_pair_arity_policy_summary.json"))
    parser.add_argument("--output-jsonl", type=Path, default=Path("runs/local/artifacts/stage975_pair_overlap_teacher_targets.jsonl"))
    parser.add_argument("--output-summary", type=Path, default=Path("runs/local/artifacts/stage975_pair_overlap_teacher_targets_summary.json"))
    args = parser.parse_args()

    arities = selected_arities(args.policy_json)
    rows = candidates = active_rows = positive_teacher_candidates = 0
    by_split_operation: dict[str, dict[str, dict[str, int]]] = {}
    args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with args.output_jsonl.open("w", encoding="utf-8") as out:
        for row in iter_jsonl(args.targets_jsonl):
            rows += 1
            split = str(row.get("split", "unknown"))
            op = str(row.get("operation", "unknown"))
            arity = int(arities.get(op, 0))
            qpair = (row.get("query_bridge", {}) or {}).get("qpair", [])
            row_active = arity > 0
            active_rows += int(row_active)
            stats = by_split_operation.setdefault(split, {}).setdefault(
                op,
                {"rows": 0, "candidates": 0, "active_rows": 0, "positive_teacher_candidates": 0},
            )
            stats["rows"] += 1
            stats["active_rows"] += int(row_active)
            new_candidates = []
            for candidate in list(row.get("candidates", []) or []):
                candidates += 1
                stats["candidates"] += 1
                bridge = candidate.get("bridge", {}) or {}
                overlap = suffix_overlap(qpair, bridge.get("dpair", []))
                if arity > 0:
                    score = min(float(overlap) / float(arity), 1.0)
                else:
                    score = 0.0
                positive_teacher_candidates += int(score >= 1.0)
                stats["positive_teacher_candidates"] += int(score >= 1.0)
                cand = dict(candidate)
                cand["pair_overlap_count"] = int(overlap)
                cand["selected_min_pair_overlap"] = int(arity)
                cand["teacher_bridge_score"] = float(score)
                new_candidates.append(cand)
            out_row = dict(row)
            out_row["stage975_teacher"] = {
                "primitive": "stage968_pair_overlap_distillation",
                "selected_min_pair_overlap": int(arity),
                "teacher_bridge_score": "min(pair_overlap_count / selected_min_pair_overlap, 1) for active pair-policy operations else 0",
            }
            out_row["candidates"] = new_candidates
            out.write(json.dumps(out_row, sort_keys=True) + "\n")

    summary = {
        "artifact_kind": "stage975_pair_overlap_teacher_targets",
        "status": "completed_pair_overlap_teacher_target_export",
        "source_targets_jsonl": str(args.targets_jsonl),
        "output_jsonl": str(args.output_jsonl),
        "selected_arities": arities,
        "rows": rows,
        "candidates": candidates,
        "active_rows": active_rows,
        "positive_teacher_candidates": positive_teacher_candidates,
        "by_split_operation": by_split_operation,
        "decision": "Exports teacher_bridge_score from Stage968's pair-overlap primitive for 100M model-owned distillation. The score is derived from qpair/dpair overlap and selected operation arity, not from answer labels.",
    }
    args.output_summary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
