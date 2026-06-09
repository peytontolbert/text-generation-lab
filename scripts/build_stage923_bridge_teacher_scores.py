#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _iter_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _bridge_score(operation: str, bridge: dict[str, Any]) -> float:
    pair = 1.0 if bridge.get("pair_suffix_match") else 0.0
    entity = 1.0 if bridge.get("entity_suffix_match") else 0.0
    slot = 1.0 if bridge.get("slot_suffix_match") else 0.0
    claim = 1.0 if bridge.get("claim_suffix_match") else 0.0
    proof = 1.0 if bridge.get("proof_edge_match") else 0.0
    if operation == "composition":
        return 1.5 * slot + 1.0 * pair + 0.5 * entity
    if operation == "relation":
        return 1.5 * pair + 0.75 * entity
    if operation in {"atomic_fact", "counterfactual_false_claim"}:
        return 1.0 * slot + 1.0 * entity + 0.5 * pair + 0.5 * claim
    if operation == "exception":
        return 1.0 * pair + 0.75 * entity + 0.5 * claim
    return pair + entity + slot + claim + proof


def build(args: argparse.Namespace) -> dict[str, Any]:
    rows = _iter_jsonl(Path(args.input_jsonl))
    out_rows = []
    by_operation: dict[str, dict[str, float]] = {}
    for row in rows:
        operation = str(row.get("operation", "") or "unknown")
        out = dict(row)
        candidates = []
        for candidate in list(row.get("candidates", []) or []):
            cand = dict(candidate)
            score = _bridge_score(operation, dict(cand.get("bridge", {}) or {}))
            cand["teacher_bridge_score"] = float(score)
            candidates.append(cand)
            stats = by_operation.setdefault(operation, {"candidates": 0, "positive_teacher_score_candidates": 0, "teacher_score_sum": 0.0})
            stats["candidates"] += 1
            stats["positive_teacher_score_candidates"] += int(score > 0.0)
            stats["teacher_score_sum"] += float(score)
        out["candidates"] = candidates
        out_rows.append(out)

    output = Path(args.output_jsonl)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for row in out_rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    summary = {
        "artifact_kind": "stage923_bridge_teacher_scores",
        "input_jsonl": str(Path(args.input_jsonl).resolve()),
        "output_jsonl": str(output),
        "decision": "Infrastructure target: adds operation-aware teacher_bridge_score for encoder fine-tuning on Stage918.",
        "by_operation": by_operation,
        "teacher_score_rule": {
            "composition": "1.5*slot + 1.0*pair + 0.5*entity",
            "relation": "1.5*pair + 0.75*entity",
            "atomic_counterfactual": "1.0*slot + 1.0*entity + 0.5*pair + 0.5*claim",
            "exception": "1.0*pair + 0.75*entity + 0.5*claim"
        }
    }
    summary_path = Path(args.summary_json)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-jsonl", default="runs/local/artifacts/stage918_stage917_bridge_curriculum_targets.jsonl")
    parser.add_argument("--output-jsonl", default="runs/local/artifacts/stage923_stage918_bridge_teacher_targets.jsonl")
    parser.add_argument("--summary-json", default="runs/local/artifacts/stage923_bridge_teacher_scores_summary.json")
    build(parser.parse_args())


if __name__ == "__main__":
    main()
