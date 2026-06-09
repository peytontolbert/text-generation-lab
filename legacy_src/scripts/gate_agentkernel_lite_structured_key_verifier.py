#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _failures(result: dict[str, Any], args: argparse.Namespace) -> list[str]:
    failures: list[str] = []
    evaluated = int(result.get("evaluated_pairs") or 0)
    stats = dict(result.get("structured_key_hard_filter_stats", {}) or {})
    exact = float(result.get("top1_accuracy") or 0.0)
    answer = float(result.get("answer_top1_accuracy") or 0.0)
    required_exact = float(args.min_exact_top1)
    required_answer = float(args.min_answer_top1)
    if evaluated <= 0:
        failures.append("no evaluated pairs")
    if exact < required_exact:
        failures.append(f"exact top1 {exact:.12g} < required {required_exact:.12g}")
    if answer < required_answer:
        failures.append(f"answer top1 {answer:.12g} < required {required_answer:.12g}")
    if not bool(result.get("operation_gated")):
        failures.append("operation_gated is false")
    if not bool(result.get("structured_key_hard_filter")):
        failures.append("structured_key_hard_filter is false")
    if int(stats.get("queries_with_exact_key_candidate") or 0) != evaluated:
        failures.append(
            "exact-key coverage mismatch: "
            f"{int(stats.get('queries_with_exact_key_candidate') or 0)} != {evaluated}"
        )
    if int(stats.get("queries_without_exact_key_candidate") or 0) != 0:
        failures.append(f"queries without exact-key candidate: {stats.get('queries_without_exact_key_candidate')}")
    if int(stats.get("queries_with_multiple_exact_key_candidates") or 0) != 0:
        failures.append(
            f"queries with multiple exact-key candidates: {stats.get('queries_with_multiple_exact_key_candidates')}"
        )
    if int(stats.get("exact_key_candidate_total") or 0) != evaluated:
        failures.append(
            f"exact-key candidate total {int(stats.get('exact_key_candidate_total') or 0)} != {evaluated}"
        )
    if int(stats.get("exact_key_candidate_max") or 0) != 1:
        failures.append(f"max exact-key candidates is {stats.get('exact_key_candidate_max')}, expected 1")
    if int(stats.get("correct_in_exact_key_candidates") or 0) != evaluated:
        failures.append(
            "correct candidate coverage mismatch: "
            f"{int(stats.get('correct_in_exact_key_candidates') or 0)} != {evaluated}"
        )
    if int(stats.get("correct_missing_from_exact_key_candidates") or 0) != 0:
        failures.append(
            "correct candidates missing from exact-key set: "
            f"{stats.get('correct_missing_from_exact_key_candidates')}"
        )
    if int(stats.get("top1_damaged_by_hard_filter") or 0) != 0:
        failures.append(f"hard filter damaged {stats.get('top1_damaged_by_hard_filter')} top1 decisions")
    return failures


def gate(args: argparse.Namespace) -> dict[str, Any]:
    result_path = Path(args.eval_json).resolve()
    result = _load_json(result_path)
    failures = _failures(result, args)
    stats = dict(result.get("structured_key_hard_filter_stats", {}) or {})
    report = {
        "artifact_kind": "agentkernel_lite_structured_key_verifier_gate",
        "eval_json": str(result_path),
        "passed": not failures,
        "failures": failures,
        "evaluated_pairs": int(result.get("evaluated_pairs") or 0),
        "exact_top1": result.get("top1_accuracy"),
        "answer_top1": result.get("answer_top1_accuracy"),
        "operation_gated": bool(result.get("operation_gated")),
        "structured_key_hard_filter": bool(result.get("structured_key_hard_filter")),
        "stats": stats,
    }
    if str(args.output_json).strip():
        Path(args.output_json).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval-json", required=True)
    parser.add_argument("--output-json", default="")
    parser.add_argument("--min-exact-top1", type=float, default=1.0)
    parser.add_argument("--min-answer-top1", type=float, default=1.0)
    args = parser.parse_args()
    report = gate(args)
    print(json.dumps(report, indent=2, sort_keys=True))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
