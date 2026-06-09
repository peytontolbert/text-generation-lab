#!/usr/bin/env python3
"""Score predictions for the Stage1086 software-KBPP pilot."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
from pathlib import Path
from typing import Any


def _iter_jsonl(path: Path):
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def _load_predictions(path: Path) -> dict[str, str]:
    predictions: dict[str, str] = {}
    for row in _iter_jsonl(path):
        predictions[str(row["task_id"])] = str(row.get("candidate_code", "") or "")
    return predictions


def _run_tests(code: str, tests: list[str], function_name: str) -> dict[str, Any]:
    namespace: dict[str, Any] = {}
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            exec(compile(code, "<candidate>", "exec"), namespace)
    except Exception as exc:  # noqa: BLE001 - verifier must report all candidate failures.
        return {"syntax_valid": 0, "function_symbol_preserved": 0, "tests_pass": 0, "error": f"compile_or_import_error:{type(exc).__name__}:{exc}"}
    if function_name not in namespace or not callable(namespace[function_name]):
        return {"syntax_valid": 1, "function_symbol_preserved": 0, "tests_pass": 0, "error": "missing_function_symbol"}
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            for test in tests:
                exec(compile(str(test), "<test>", "exec"), namespace)
    except Exception as exc:  # noqa: BLE001
        return {"syntax_valid": 1, "function_symbol_preserved": 1, "tests_pass": 0, "error": f"test_error:{type(exc).__name__}:{exc}"}
    return {"syntax_valid": 1, "function_symbol_preserved": 1, "tests_pass": 1, "error": ""}


def _score_task(task: dict[str, Any], candidate_code: str) -> dict[str, Any]:
    function_name = str(task["function_name"])
    public = _run_tests(candidate_code, list(task.get("public_tests", [])), function_name)
    hidden = _run_tests(candidate_code, list(task.get("hidden_tests", [])), function_name)
    syntax_valid = int(public["syntax_valid"] and hidden["syntax_valid"])
    symbol = int(public["function_symbol_preserved"] and hidden["function_symbol_preserved"])
    public_pass = int(public["tests_pass"])
    hidden_pass = int(hidden["tests_pass"])
    verified_decisions = syntax_valid + symbol + public_pass + hidden_pass
    return {
        "task_id": task["task_id"],
        "split": task["split"],
        "category": task["category"],
        "syntax_valid": syntax_valid,
        "function_symbol_preserved": symbol,
        "public_tests_pass": public_pass,
        "hidden_tests_pass": hidden_pass,
        "verified_decisions": verified_decisions,
        "verified_decision_bits": int(task.get("verified_decision_bits", 0)) if hidden_pass else 0,
        "public_error": public.get("error", ""),
        "hidden_error": hidden.get("error", ""),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks-jsonl", type=Path, required=True)
    parser.add_argument("--predictions-jsonl", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, default=Path("runs/local/artifacts/stage1086_software_kbpp_prediction_score_summary.json"))
    parser.add_argument("--output-jsonl", type=Path, default=Path("runs/local/artifacts/stage1086_software_kbpp_prediction_scores.jsonl"))
    args = parser.parse_args()

    tasks = list(_iter_jsonl(args.tasks_jsonl))
    predictions = _load_predictions(args.predictions_jsonl)
    scores = [_score_task(task, predictions.get(str(task["task_id"]), "")) for task in tasks]
    by_category: dict[str, dict[str, int]] = {}
    for score in scores:
        stats = by_category.setdefault(str(score["category"]), {"rows": 0, "hidden_pass": 0, "verified_decisions": 0, "verified_decision_bits": 0})
        stats["rows"] += 1
        stats["hidden_pass"] += int(score["hidden_tests_pass"])
        stats["verified_decisions"] += int(score["verified_decisions"])
        stats["verified_decision_bits"] += int(score["verified_decision_bits"])
    summary = {
        "artifact_kind": "stage1086_software_kbpp_prediction_score",
        "tasks_jsonl": str(args.tasks_jsonl),
        "predictions_jsonl": str(args.predictions_jsonl),
        "rows": len(scores),
        "hidden_pass": sum(int(score["hidden_tests_pass"]) for score in scores),
        "public_pass": sum(int(score["public_tests_pass"]) for score in scores),
        "syntax_valid": sum(int(score["syntax_valid"]) for score in scores),
        "function_symbol_preserved": sum(int(score["function_symbol_preserved"]) for score in scores),
        "verified_decisions": sum(int(score["verified_decisions"]) for score in scores),
        "verified_decision_bits": sum(int(score["verified_decision_bits"]) for score in scores),
        "by_category": by_category,
        "decision": "Verifier score for Stage1086 software-KBPP predictions. Hidden-test pass is the primary behavioral score.",
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with args.output_jsonl.open("w", encoding="utf-8") as handle:
        for score in scores:
            handle.write(json.dumps(score, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
