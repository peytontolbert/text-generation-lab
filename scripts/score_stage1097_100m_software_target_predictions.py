#!/usr/bin/env python3
"""Score 100M-owned software target predictions from the Stage1096 package."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {name}: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _iter_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def _load_predictions(path: Path) -> dict[str, dict[str, Any]]:
    return {str(row["task_id"]): row for row in _iter_jsonl(path)}


def _candidate_from_prediction(prediction: dict[str, Any]) -> str:
    direct = str(prediction.get("direct_code_output", "") or "")
    if direct.strip():
        return direct
    signature = str(prediction.get("signature_output", "") or "")
    body = str(prediction.get("template_body_output", "") or "")
    if signature.strip() and body.strip():
        return f"{signature.rstrip()}\n{body}"
    return str(prediction.get("candidate_code", "") or "")


def _task_from_target(target: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": target["task_id"],
        "split": target["source_split"],
        "category": "stage1096_100m_software_target",
        "function_name": target["function_name"],
        "public_tests": target.get("public_tests", []),
        "hidden_tests": target.get("hidden_tests", []),
        "verified_decision_bits": target.get("verified_decision_bits", 8),
    }


def _score(score_module, targets: list[dict[str, Any]], predictions: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    score_rows: list[dict[str, Any]] = []
    for target in targets:
        prediction = predictions.get(str(target["task_id"]), {})
        candidate = _candidate_from_prediction(prediction)
        score_rows.append(score_module._score_task(_task_from_target(target), candidate))
    summary = {
        "rows": len(score_rows),
        "hidden_pass": sum(int(row["hidden_tests_pass"]) for row in score_rows),
        "public_pass": sum(int(row["public_tests_pass"]) for row in score_rows),
        "syntax_valid": sum(int(row["syntax_valid"]) for row in score_rows),
        "function_symbol_preserved": sum(int(row["function_symbol_preserved"]) for row in score_rows),
        "verified_decisions": sum(int(row["verified_decisions"]) for row in score_rows),
        "verified_decision_bits": sum(int(row["verified_decision_bits"]) for row in score_rows),
    }
    return summary, score_rows


def _oracle_predictions(targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "task_id": target["task_id"],
            "operator_output": target["operator_label"],
            "signature_output": target["signature_target"],
            "template_body_output": target["template_body_target"],
            "direct_code_output": target["direct_code_target"],
        }
        for target in targets
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("runs/local/artifacts/stage1096_100m_software_operator_training_package/manifest.json"))
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--split", choices=["eval", "hidden"], default="eval")
    parser.add_argument("--predictions-jsonl", type=Path)
    parser.add_argument("--write-oracle-predictions", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=Path("runs/local/artifacts/stage1097_100m_software_target_prediction_scores"))
    parser.add_argument("--summary-json", type=Path)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    target_path = Path(manifest[f"{args.split}_targets_path"])
    targets = _iter_jsonl(target_path)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if args.write_oracle_predictions:
        prediction_path = args.output_dir / f"{args.split}_oracle_predictions.jsonl"
        _write_jsonl(prediction_path, _oracle_predictions(targets))
    elif args.predictions_jsonl is not None:
        prediction_path = args.predictions_jsonl
    else:
        raise SystemExit("provide --predictions-jsonl or --write-oracle-predictions")

    score_module = _load_module("stage1086_score", args.repo_root / "scripts/score_stage1086_software_kbpp_predictions.py")
    predictions = _load_predictions(prediction_path)
    summary_stats, score_rows = _score(score_module, targets, predictions)
    score_path = args.output_dir / f"{args.split}_scores.jsonl"
    _write_jsonl(score_path, score_rows)
    summary = {
        "artifact_kind": "stage1097_100m_software_target_prediction_score",
        "status": "completed_prediction_score",
        "manifest": str(args.manifest),
        "split": args.split,
        "targets_jsonl": str(target_path),
        "predictions_jsonl": str(prediction_path),
        "scores_jsonl": str(score_path),
        **summary_stats,
        "decision": "Scores Stage1096 100M-owned software target predictions through the same hidden-test verifier.",
    }
    summary_path = args.summary_json or (args.output_dir / f"{args.split}_score_summary.json")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
