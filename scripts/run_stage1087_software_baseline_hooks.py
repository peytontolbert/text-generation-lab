#!/usr/bin/env python3
"""Run baseline prediction hooks for the Stage1086 software-KBPP pilot."""

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


def _iter_jsonl(path: Path):
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def _proof_key(row: dict[str, Any]) -> tuple[str, str]:
    proof = row.get("proof_units", {}) or {}
    return str(proof.get("relevant_symbol", row.get("function_name", ""))), str(proof.get("contract", ""))


def _write_predictions(path: Path, rows: list[dict[str, Any]], predictions: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps({"task_id": row["task_id"], "candidate_code": predictions.get(str(row["task_id"]), "")}, sort_keys=True) + "\n")


def _score_rows(score_module, rows: list[dict[str, Any]], predictions: dict[str, str]) -> dict[str, Any]:
    scores = [score_module._score_task(row, predictions.get(str(row["task_id"]), "")) for row in rows]
    return {
        "rows": len(scores),
        "hidden_pass": sum(int(score["hidden_tests_pass"]) for score in scores),
        "public_pass": sum(int(score["public_tests_pass"]) for score in scores),
        "syntax_valid": sum(int(score["syntax_valid"]) for score in scores),
        "function_symbol_preserved": sum(int(score["function_symbol_preserved"]) for score in scores),
        "verified_decisions": sum(int(score["verified_decisions"]) for score in scores),
        "verified_decision_bits": sum(int(score["verified_decision_bits"]) for score in scores),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("runs/local/artifacts/stage1086_software_kbpp_pilot/manifest.json"))
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--output-dir", type=Path, default=Path("runs/local/artifacts/stage1087_software_baseline_hooks"))
    parser.add_argument("--summary-json", type=Path, default=Path("runs/local/artifacts/stage1087_software_baseline_hooks_summary.json"))
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    train_rows = list(_iter_jsonl(Path(manifest["train_path"])))
    eval_rows = list(_iter_jsonl(Path(manifest["eval_path"])))
    hidden_rows = list(_iter_jsonl(Path(manifest["hidden_path"])))
    score_module = _load_module("stage1086_score", args.repo_root / "scripts/score_stage1086_software_kbpp_predictions.py")

    proof_memory = {_proof_key(row): str(row["reference_code"]) for row in train_rows}
    modes = ["copy_buggy", "reference_oracle", "proof_memory_by_symbol_contract"]
    splits = {"eval": eval_rows, "hidden": hidden_rows}
    results: dict[str, Any] = {}
    for mode in modes:
        results[mode] = {}
        for split, rows in splits.items():
            predictions: dict[str, str] = {}
            for row in rows:
                if mode == "copy_buggy":
                    candidate = str(row["buggy_code"])
                elif mode == "reference_oracle":
                    candidate = str(row["reference_code"])
                elif mode == "proof_memory_by_symbol_contract":
                    candidate = proof_memory.get(_proof_key(row), "")
                else:
                    raise ValueError(mode)
                predictions[str(row["task_id"])] = candidate
            pred_path = args.output_dir / f"{split}_{mode}_predictions.jsonl"
            _write_predictions(pred_path, rows, predictions)
            score = _score_rows(score_module, rows, predictions)
            score["predictions_jsonl"] = str(pred_path)
            results[mode][split] = score

    summary = {
        "artifact_kind": "stage1087_software_baseline_hooks",
        "status": "completed_software_baseline_hooks",
        "manifest": str(args.manifest),
        "modes": modes,
        "results": results,
        "decision": (
            "Baseline hooks for the Stage1086 software pilot. copy_buggy is a negative control, reference_oracle is a verifier ceiling, "
            "and proof_memory_by_symbol_contract is a diagnostic proof-expansion baseline using train proof keys. It is not a model claim."
        ),
    }
    args.summary_json.parent.mkdir(parents=True, exist_ok=True)
    args.summary_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
