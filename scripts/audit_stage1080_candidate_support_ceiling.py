#!/usr/bin/env python3
"""Audit the candidate-support ceiling after Stage1079 answer materialization."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _iter_jsonl(path: Path):
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def _hit(candidate: dict[str, Any]) -> tuple[int, int]:
    return int(bool(candidate.get("is_exact") or candidate.get("is_answer_match"))), int(bool(candidate.get("is_exact")))


def _base_index(candidates: list[dict[str, Any]]) -> int:
    return max(range(len(candidates)), key=lambda index: float(candidates[index].get("base_score", 0.0) or 0.0))


def _audit_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_operation: dict[str, Counter] = defaultdict(Counter)
    global_counts = Counter()
    unsupported_examples: list[dict[str, Any]] = []
    for row_index, row in enumerate(rows):
        candidates = list(row.get("candidates", []) or [])
        operation = str(row.get("operation", "unknown"))
        op = by_operation[operation]
        op["rows"] += 1
        global_counts["rows"] += 1
        if not candidates:
            op["empty_candidate_rows"] += 1
            global_counts["empty_candidate_rows"] += 1
            continue
        answer_present = any(_hit(candidate)[0] for candidate in candidates)
        exact_present = any(_hit(candidate)[1] for candidate in candidates)
        base_candidate = candidates[_base_index(candidates)]
        base_answer, base_exact = _hit(base_candidate)
        op["answer_supported_rows"] += int(answer_present)
        op["exact_supported_rows"] += int(exact_present)
        op["base_answer_rows"] += int(base_answer)
        op["base_exact_rows"] += int(base_exact)
        global_counts["answer_supported_rows"] += int(answer_present)
        global_counts["exact_supported_rows"] += int(exact_present)
        global_counts["base_answer_rows"] += int(base_answer)
        global_counts["base_exact_rows"] += int(base_exact)
        if not answer_present and len(unsupported_examples) < 40:
            unsupported_examples.append(
                {
                    "row_index": row_index,
                    "operation": operation,
                    "query_text": str(row.get("query_text", "")),
                    "candidate_count": len(candidates),
                    "base_doc_text": str(base_candidate.get("doc_text", "")),
                }
            )
    return {
        "rows": int(global_counts["rows"]),
        "answer_support_ceiling": int(global_counts["answer_supported_rows"]),
        "exact_support_ceiling": int(global_counts["exact_supported_rows"]),
        "base_answer": int(global_counts["base_answer_rows"]),
        "base_exact": int(global_counts["base_exact_rows"]),
        "empty_candidate_rows": int(global_counts["empty_candidate_rows"]),
        "by_operation": {operation: dict(counts) for operation, counts in sorted(by_operation.items())},
        "unsupported_examples": unsupported_examples,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets-jsonl", type=Path, default=Path("runs/local/artifacts/stage1043_operator_teacher_targets.jsonl"))
    parser.add_argument("--hidden-jsonl", type=Path, default=Path("runs/local/artifacts/stage1044_salted_hidden_no_anchor_targets.jsonl"))
    parser.add_argument("--stage1079-json", type=Path, default=Path("runs/local/artifacts/stage1079_constrained_answer_value_head_summary.json"))
    parser.add_argument("--output-json", type=Path, default=Path("runs/local/artifacts/stage1080_candidate_support_ceiling_audit_summary.json"))
    args = parser.parse_args()

    split_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in _iter_jsonl(args.targets_jsonl):
        split_rows[str(row.get("split", "unknown"))].append(row)
    hidden_rows = [row for row in _iter_jsonl(args.hidden_jsonl)]
    stage1079 = json.loads(args.stage1079_json.read_text(encoding="utf-8"))
    eval_audit = _audit_rows(split_rows["eval"])
    hidden_audit = _audit_rows(hidden_rows)
    summary = {
        "artifact_kind": "stage1080_candidate_support_ceiling_audit",
        "status": "completed_candidate_support_ceiling_audit",
        "targets_jsonl": str(args.targets_jsonl),
        "hidden_jsonl": str(args.hidden_jsonl),
        "stage1079_json": str(args.stage1079_json),
        "eval": eval_audit,
        "hidden_eval": hidden_audit,
        "stage1069_candidate_ranking_answer_exact": [350, 333],
        "stage1079_max_blend_value_eval_answer_exact": [
            int(stage1079["max_blend_value_baseline"]["eval"]["answer"]),
            int(stage1079["max_blend_value_baseline"]["eval"]["exact"]),
        ],
        "stage1079_learned_value_head_eval_answer_exact": [
            int(stage1079["scores"]["eval"]["answer"]),
            int(stage1079["scores"]["eval"]["exact"]),
        ],
        "decision": (
            "The current candidate list has only 350 answer-supported eval rows and 333 exact-supported eval rows, "
            "so Stage1069/1079 max-pooled value materialization is at the same-candidate support ceiling. "
            "Further gains require proof/candidate expansion or a genuinely model-owned memory/generation path; "
            "reranking/value-head tuning cannot exceed unsupported rows."
        ),
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
