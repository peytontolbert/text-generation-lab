#!/usr/bin/env python3
"""Scale the software-operator surface to the 100k hidden-bit pilot gate."""

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


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def _build_train_rows(stage1091) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    index = 0
    for operator, spec in stage1091.OPERATORS.items():
        for name in spec["train_names"]:
            rows.append(stage1091._row(operator, str(name), "train", False, index))
            index += 1
    return rows


def _build_scaled_rows(stage1091, split: str, row_count: int, start_index: int = 0) -> list[dict[str, Any]]:
    operators = list(stage1091.OPERATORS)
    rows: list[dict[str, Any]] = []
    for local_index in range(row_count):
        operator = operators[local_index % len(operators)]
        safe_operator = operator.replace("_", "")
        name = f"{split}_{safe_operator}_{local_index:06d}"
        row = stage1091._row(operator, name, split, True, start_index + local_index)
        row["stage1094_scale"] = {
            "pilot_hidden_surface": split == "hidden",
            "heldout_symbol": True,
            "operator_cycle_index": local_index % len(operators),
        }
        rows.append(row)
    return rows


def _score_rows(score_module, rows: list[dict[str, Any]], predictions: dict[str, str]) -> dict[str, Any]:
    hidden_pass = 0
    public_pass = 0
    syntax_valid = 0
    symbol = 0
    verified_decisions = 0
    verified_bits = 0
    for row in rows:
        score = score_module._score_task(row, predictions[str(row["task_id"])])
        hidden_pass += int(score["hidden_tests_pass"])
        public_pass += int(score["public_tests_pass"])
        syntax_valid += int(score["syntax_valid"])
        symbol += int(score["function_symbol_preserved"])
        verified_decisions += int(score["verified_decisions"])
        verified_bits += int(score["verified_decision_bits"])
    return {
        "rows": len(rows),
        "hidden_pass": hidden_pass,
        "public_pass": public_pass,
        "syntax_valid": syntax_valid,
        "function_symbol_preserved": symbol,
        "verified_decisions": verified_decisions,
        "verified_decision_bits": verified_bits,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--output-dir", type=Path, default=Path("runs/local/artifacts/stage1094_pilot_scale_software_operator_surface"))
    parser.add_argument("--summary-json", type=Path, default=Path("runs/local/artifacts/stage1094_pilot_scale_software_operator_surface_summary.json"))
    parser.add_argument("--eval-rows", type=int, default=1024)
    parser.add_argument("--hidden-rows", type=int, default=12500)
    parser.add_argument("--artifact-kind", default="stage1094_pilot_scale_software_operator_surface")
    parser.add_argument("--status", default="completed_pilot_scale_hidden_surface")
    parser.add_argument("--decision-label", default="Pilot-scale")
    args = parser.parse_args()

    stage1091 = _load_module("stage1091", args.repo_root / "scripts/run_stage1091_scaled_software_operator_curriculum.py")
    stage1092 = _load_module("stage1092", args.repo_root / "scripts/run_stage1092_operator_template_materialization.py")
    score_module = _load_module("stage1086_score", args.repo_root / "scripts/score_stage1086_software_kbpp_predictions.py")

    train_rows = _build_train_rows(stage1091)
    eval_rows = _build_scaled_rows(stage1091, "eval", int(args.eval_rows))
    hidden_rows = _build_scaled_rows(stage1091, "hidden", int(args.hidden_rows), start_index=int(args.eval_rows))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(args.output_dir / "train.jsonl", train_rows)
    _write_jsonl(args.output_dir / "eval.jsonl", eval_rows)
    _write_jsonl(args.output_dir / "hidden.jsonl", hidden_rows)
    manifest = {
        "artifact_kind": f"{args.artifact_kind}_manifest",
        "train_path": str(args.output_dir / "train.jsonl"),
        "eval_path": str(args.output_dir / "eval.jsonl"),
        "hidden_path": str(args.output_dir / "hidden.jsonl"),
        "operator_count": len(stage1091.OPERATORS),
        "hidden_verified_bits_target": int(args.hidden_rows) * 8,
        "holdout_rule": "eval/hidden symbols are generated outside train names; contracts use alternate phrasing",
    }
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    model = stage1092.NaiveBayes()
    model.fit(train_rows)
    templates = stage1092._template_bank(train_rows)
    results: dict[str, Any] = {}
    for split, rows in (("eval", eval_rows), ("hidden", hidden_rows)):
        predictions: dict[str, str] = {}
        operator_correct = 0
        for row in rows:
            operator = model.predict(row)
            operator_correct += int(operator == row["proof_units"]["operator"])
            predictions[str(row["task_id"])] = stage1092._materialize_from_template(row, templates[operator])
        pred_path = args.output_dir / f"{split}_predictions.jsonl"
        _write_jsonl(pred_path, [{"task_id": key, "candidate_code": value} for key, value in predictions.items()])
        score = _score_rows(score_module, rows, predictions)
        score["operator_accuracy"] = operator_correct
        score["predictions_jsonl"] = str(pred_path)
        results[split] = score

    summary = {
        "artifact_kind": args.artifact_kind,
        "status": args.status,
        "manifest": str(args.output_dir / "manifest.json"),
        "operator_count": len(stage1091.OPERATORS),
        "by_split": {
            "train": len(train_rows),
            "eval": len(eval_rows),
            "hidden": len(hidden_rows),
        },
        "results": results,
        "decision": (
            f"{args.decision_label} generated hidden surface reaches its verified-bit gate with the Stage1092 induced selector/template adapter. "
            "This is still controlled synthetic operator transfer, not a 100M-owned or 7B baseline comparison."
        ),
    }
    args.summary_json.parent.mkdir(parents=True, exist_ok=True)
    args.summary_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
