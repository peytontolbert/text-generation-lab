#!/usr/bin/env python3
"""Materialize constrained answers from Stage981 candidate predictions."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ANSWER_RE = re.compile(r"\banswer=([^\s]+)")


def _iter_jsonl(path: Path):
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def _candidate_hit(candidate: dict[str, Any]) -> tuple[int, int]:
    return int(bool(candidate.get("is_exact") or candidate.get("is_answer_match"))), int(bool(candidate.get("is_exact")))


def _extract_answer(doc_text: str) -> str | None:
    match = ANSWER_RE.search(str(doc_text))
    return match.group(1) if match else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets-jsonl", type=Path, default=Path("runs/local/artifacts/stage975_pair_overlap_teacher_targets.jsonl"))
    parser.add_argument("--predictions-jsonl", type=Path, default=Path("runs/local/artifacts/stage981_100m_pair_interface_hybrid_predictions.jsonl"))
    parser.add_argument("--split", default="eval")
    parser.add_argument("--output-json", type=Path, default=Path("runs/local/artifacts/stage993_constrained_answer_materialization_summary.json"))
    parser.add_argument("--outputs-jsonl", type=Path, default=Path("runs/local/artifacts/stage993_constrained_answer_materialization_outputs.jsonl"))
    args = parser.parse_args()

    rows = [row for row in _iter_jsonl(args.targets_jsonl) if str(row.get("split")) == str(args.split)]
    predictions = [pred for pred in _iter_jsonl(args.predictions_jsonl) if str(pred.get("split")) == str(args.split)]
    pred_by_row = {int(pred["row_index"]): pred for pred in predictions}
    answer = exact = parse_ok = missing_prediction = 0
    by_operation: dict[str, dict[str, int]] = {}
    outputs = []
    for row_index, row in enumerate(rows):
        op = str(row.get("operation", "unknown"))
        stats = by_operation.setdefault(op, {"rows": 0, "answer": 0, "exact": 0, "parse_ok": 0, "missing_prediction": 0})
        stats["rows"] += 1
        pred = pred_by_row.get(row_index)
        if pred is None:
            missing_prediction += 1
            stats["missing_prediction"] += 1
            continue
        candidates = list(row.get("candidates", []) or [])
        candidate_index = int(pred["predicted_candidate_index"])
        candidate = candidates[candidate_index]
        ans, ex = _candidate_hit(candidate)
        emitted = _extract_answer(str(candidate.get("doc_text", "") or ""))
        parsed = emitted is not None
        answer += ans
        exact += ex
        parse_ok += int(parsed)
        stats["answer"] += ans
        stats["exact"] += ex
        stats["parse_ok"] += int(parsed)
        outputs.append(
            {
                "row_index": row_index,
                "operation": op,
                "candidate_index": candidate_index,
                "emitted_answer": emitted,
                "parse_ok": parsed,
                "answer_hit": ans,
                "exact_hit": ex,
                "policy": pred.get("policy"),
            }
        )
    summary = {
        "artifact_kind": "stage993_constrained_answer_materialization",
        "status": "completed_constrained_answer_materialization",
        "split": str(args.split),
        "targets_jsonl": str(args.targets_jsonl),
        "predictions_jsonl": str(args.predictions_jsonl),
        "rows": len(rows),
        "answer": answer,
        "exact": exact,
        "parse_ok": parse_ok,
        "missing_prediction": missing_prediction,
        "by_operation": by_operation,
        "outputs_jsonl": str(args.outputs_jsonl),
        "decision": "Constrained answer materialization extracts answer=<value> from the selected candidate. This validates typed answer emission from the Stage981 candidate policy, not free-form generation.",
    }
    args.outputs_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with args.outputs_jsonl.open("w", encoding="utf-8") as handle:
        for output in outputs:
            handle.write(json.dumps(output, sort_keys=True) + "\n")
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
