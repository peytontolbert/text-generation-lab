#!/usr/bin/env python3
"""Resumable Ollama candidate-selection baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from run_stage973_ollama_7b_candidate_baseline import (
    build_prompt,
    candidate_hit,
    iter_jsonl,
    ollama_generate,
    parse_choice,
    select_balanced,
)


def _load_done(path: Path) -> dict[int, dict]:
    if not path.exists():
        return {}
    done: dict[int, dict] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            done[int(item["row_number"])] = item
    return done


def _summarize(predictions: list[dict]) -> dict:
    answer = exact = invalid = topk_answer_ceiling = topk_exact_ceiling = 0
    by_operation: dict[str, dict[str, int]] = {}
    for pred in predictions:
        op = str(pred.get("operation", "unknown"))
        stats = by_operation.setdefault(op, {"rows": 0, "answer": 0, "exact": 0, "invalid": 0, "topk_answer_ceiling": 0, "topk_exact_ceiling": 0})
        stats["rows"] += 1
        answer += int(pred.get("answer_hit", 0))
        exact += int(pred.get("exact_hit", 0))
        invalid += int(pred.get("invalid", 0))
        topk_answer_ceiling += int(pred.get("topk_answer_available", 0))
        topk_exact_ceiling += int(pred.get("topk_exact_available", 0))
        stats["answer"] += int(pred.get("answer_hit", 0))
        stats["exact"] += int(pred.get("exact_hit", 0))
        stats["invalid"] += int(pred.get("invalid", 0))
        stats["topk_answer_ceiling"] += int(pred.get("topk_answer_available", 0))
        stats["topk_exact_ceiling"] += int(pred.get("topk_exact_available", 0))
    return {
        "rows": len(predictions),
        "answer": answer,
        "exact": exact,
        "invalid": invalid,
        "topk_answer_ceiling": topk_answer_ceiling,
        "topk_exact_ceiling": topk_exact_ceiling,
        "by_operation": by_operation,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets-jsonl", type=Path, default=Path("runs/local/artifacts/stage975_pair_overlap_teacher_targets.jsonl"))
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--predictions-jsonl", type=Path, required=True)
    parser.add_argument("--model", default="qwen3.5:9b")
    parser.add_argument("--host", default="http://127.0.0.1:11434")
    parser.add_argument("--split", default="eval")
    parser.add_argument("--max-rows", type=int, default=640)
    parser.add_argument("--start-row", type=int, default=0)
    parser.add_argument("--limit-new", type=int, default=0)
    parser.add_argument("--top-k", type=int, default=999)
    parser.add_argument("--text-limit", type=int, default=500)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--num-predict", type=int, default=32)
    parser.add_argument("--think", type=int, choices=(-1, 0, 1), default=-1)
    parser.add_argument("--require-topk-answer", type=int, choices=(0, 1), default=0)
    args = parser.parse_args()

    rows = [row for row in iter_jsonl(args.targets_jsonl) if str(row.get("split")) == str(args.split)]
    if int(args.require_topk_answer):
        filtered = []
        for row in rows:
            candidates = sorted(list(row.get("candidates", []) or []), key=lambda c: int(c.get("rank", 999999) or 999999))[: int(args.top_k)]
            if any(candidate_hit(candidate)[0] for candidate in candidates):
                filtered.append(row)
        rows = filtered
    selected = select_balanced(rows, max_rows=int(args.max_rows))
    done = _load_done(args.predictions_jsonl)
    args.predictions_jsonl.parent.mkdir(parents=True, exist_ok=True)
    new_count = 0
    with args.predictions_jsonl.open("a", encoding="utf-8") as handle:
        for row_number, row in enumerate(selected):
            if row_number < int(args.start_row) or row_number in done:
                continue
            if int(args.limit_new) > 0 and new_count >= int(args.limit_new):
                break
            prompt, candidates = build_prompt(row, top_k=int(args.top_k), text_limit=int(args.text_limit))
            row_topk_answer = int(any(candidate_hit(candidate)[0] for candidate in candidates))
            row_topk_exact = int(any(candidate_hit(candidate)[1] for candidate in candidates))
            try:
                response = ollama_generate(
                    model=str(args.model),
                    prompt=prompt,
                    host=str(args.host),
                    timeout=float(args.timeout),
                    num_predict=int(args.num_predict),
                    think=None if int(args.think) < 0 else bool(args.think),
                )
                choice = parse_choice(response)
            except Exception as exc:
                response = f"ERROR: {exc}"
                choice = None
            if choice is None or choice < 0 or choice >= len(candidates):
                ans = ex = 0
                invalid = 1
            else:
                ans, ex = candidate_hit(candidates[choice])
                invalid = 0
            item = {
                "row_number": row_number,
                "operation": str(row.get("operation", "unknown")),
                "choice": choice,
                "answer_hit": ans,
                "exact_hit": ex,
                "invalid": invalid,
                "topk_answer_available": row_topk_answer,
                "topk_exact_available": row_topk_exact,
                "response": response,
            }
            handle.write(json.dumps(item, sort_keys=True) + "\n")
            handle.flush()
            done[row_number] = item
            new_count += 1

    predictions = [done[index] for index in sorted(done)]
    scores = _summarize(predictions)
    summary = {
        "artifact_kind": "stage987_ollama_candidate_baseline_resumable",
        "status": "completed_resumable_chunk",
        "model": str(args.model),
        "split": str(args.split),
        "targets_jsonl": str(args.targets_jsonl),
        "selected_rows": len(selected),
        "completed_rows": len(predictions),
        "top_k": int(args.top_k),
        "require_topk_answer": bool(args.require_topk_answer),
        "num_predict": int(args.num_predict),
        "think": None if int(args.think) < 0 else bool(args.think),
        "scores": scores,
        "predictions_jsonl": str(args.predictions_jsonl),
        "decision": "Resumable baseline harness. A full baseline is complete only when completed_rows equals selected_rows.",
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
