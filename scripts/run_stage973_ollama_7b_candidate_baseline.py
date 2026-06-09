#!/usr/bin/env python3
"""Run a bounded Ollama 7B-class candidate-selection baseline on Stage960 targets."""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.request
from pathlib import Path
from typing import Any


def iter_jsonl(path: Path):
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def candidate_hit(candidate: dict[str, Any]) -> tuple[int, int]:
    return int(bool(candidate.get("is_exact") or candidate.get("is_answer_match"))), int(bool(candidate.get("is_exact")))


def truncate(text: str, limit: int) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: max(0, limit - 3)] + "..."


def select_balanced(rows: list[dict[str, Any]], *, max_rows: int) -> list[dict[str, Any]]:
    by_op: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_op.setdefault(str(row.get("operation", "unknown")), []).append(row)
    operations = sorted(by_op)
    selected: list[dict[str, Any]] = []
    cursors = {op: 0 for op in operations}
    while len(selected) < max_rows:
        progressed = False
        for op in operations:
            cursor = cursors[op]
            if cursor < len(by_op[op]) and len(selected) < max_rows:
                selected.append(by_op[op][cursor])
                cursors[op] += 1
                progressed = True
        if not progressed:
            break
    return selected


def build_prompt(row: dict[str, Any], *, top_k: int, text_limit: int) -> tuple[str, list[dict[str, Any]]]:
    candidates = sorted(list(row.get("candidates", []) or []), key=lambda c: int(c.get("rank", 999999) or 999999))[:top_k]
    lines = [
        "/no_think",
        "You are scoring a synthetic knowledge retrieval task.",
        "Pick the one candidate that best answers the query.",
        "Return only this format with the chosen numeric id: candidate_index=<id>",
        "Do not explain.",
        "",
        f"operation: {row.get('operation')}",
        f"query: {truncate(str(row.get('query_text', '')), text_limit)}",
        "",
        "candidates:",
    ]
    for idx, candidate in enumerate(candidates):
        lines.append(f"[{idx}] {truncate(str(candidate.get('doc_text', '')), text_limit)}")
    return "\n".join(lines), candidates


def parse_choice(text: str) -> int | None:
    text = str(text).strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, dict) and "candidate_index" in obj:
            return int(obj["candidate_index"])
    except Exception:
        pass
    match = re.search(r"candidate_index\"?\s*[:=]\s*(\d+)", text)
    if match:
        return int(match.group(1))
    match = re.search(r"\[(\d+)\]", text)
    if match:
        return int(match.group(1))
    match = re.search(r"\b(\d+)\b", text)
    return int(match.group(1)) if match else None


def ollama_generate(*, model: str, prompt: str, host: str, timeout: float, num_predict: int, think: bool | None = None) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0,
            "num_predict": int(num_predict),
        },
    }
    if think is not None:
        payload["think"] = bool(think)
    req = urllib.request.Request(
        f"{host.rstrip('/')}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return str(data.get("response", ""))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets-jsonl", type=Path, default=Path("runs/local/artifacts/stage960_relation_qslot_bridge_targets.jsonl"))
    parser.add_argument("--output-json", type=Path, default=Path("runs/local/artifacts/stage973_ollama_7b_candidate_baseline_smoke_summary.json"))
    parser.add_argument("--predictions-jsonl", type=Path, default=Path("runs/local/artifacts/stage973_ollama_7b_candidate_baseline_smoke_predictions.jsonl"))
    parser.add_argument("--model", default="deepseek-r1:7b")
    parser.add_argument("--host", default="http://127.0.0.1:11434")
    parser.add_argument("--split", default="eval")
    parser.add_argument("--max-rows", type=int, default=25)
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--text-limit", type=int, default=700)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--num-predict", type=int, default=64)
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
    answer = exact = invalid = topk_answer_ceiling = topk_exact_ceiling = 0
    by_operation: dict[str, dict[str, int]] = {}
    predictions = []
    start = time.time()
    for row_idx, row in enumerate(selected):
        prompt, candidates = build_prompt(row, top_k=int(args.top_k), text_limit=int(args.text_limit))
        op = str(row.get("operation", "unknown"))
        stats = by_operation.setdefault(
            op,
            {"rows": 0, "answer": 0, "exact": 0, "invalid": 0, "topk_answer_ceiling": 0, "topk_exact_ceiling": 0},
        )
        stats["rows"] += 1
        row_topk_answer = int(any(candidate_hit(candidate)[0] for candidate in candidates))
        row_topk_exact = int(any(candidate_hit(candidate)[1] for candidate in candidates))
        topk_answer_ceiling += row_topk_answer
        topk_exact_ceiling += row_topk_exact
        stats["topk_answer_ceiling"] += row_topk_answer
        stats["topk_exact_ceiling"] += row_topk_exact
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
            invalid += 1
            stats["invalid"] += 1
            chosen = None
            ans = ex = 0
        else:
            chosen = candidates[choice]
            ans, ex = candidate_hit(chosen)
        answer += ans
        exact += ex
        stats["answer"] += ans
        stats["exact"] += ex
        predictions.append(
            {
                "row_number": row_idx,
                "operation": op,
                "choice": choice,
                "answer_hit": ans,
                "exact_hit": ex,
                "topk_answer_available": row_topk_answer,
                "topk_exact_available": row_topk_exact,
                "response": response,
            }
        )

    args.predictions_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with args.predictions_jsonl.open("w", encoding="utf-8") as f:
        for pred in predictions:
            f.write(json.dumps(pred, sort_keys=True) + "\n")

    summary = {
        "artifact_kind": "stage973_ollama_7b_candidate_baseline_smoke",
        "status": "completed_ollama_7b_candidate_baseline_smoke",
        "model": str(args.model),
        "split": str(args.split),
        "targets_jsonl": str(args.targets_jsonl),
        "rows": len(selected),
        "top_k": int(args.top_k),
        "require_topk_answer": bool(args.require_topk_answer),
        "num_predict": int(args.num_predict),
        "think": None if int(args.think) < 0 else bool(args.think),
        "answer": answer,
        "exact": exact,
        "invalid": invalid,
        "topk_answer_ceiling": topk_answer_ceiling,
        "topk_exact_ceiling": topk_exact_ceiling,
        "by_operation": by_operation,
        "elapsed_seconds": time.time() - start,
        "predictions_jsonl": str(args.predictions_jsonl),
        "decision": "This is a bounded top-k prompt baseline smoke for a local Ollama 7B-class model. It is not the full Stage968 same-candidate-set baseline because high-candidate relation rows exceed practical prompt context; top-k ceiling is reported separately.",
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
