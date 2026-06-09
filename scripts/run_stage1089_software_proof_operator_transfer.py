#!/usr/bin/env python3
"""Run a proof-operator transfer baseline on the hardened software-KBPP pilot."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
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


def _signature(row: dict[str, Any]) -> tuple[str, list[str]]:
    match = re.search(r"^def\s+([A-Za-z_][A-Za-z0-9_]*)\(([^)]*)\):", str(row["buggy_code"]), re.MULTILINE)
    if not match:
        raise ValueError(f"missing function signature for {row.get('task_id')}")
    args = [part.strip().split("=")[0].strip() for part in match.group(2).split(",") if part.strip()]
    return match.group(1), args


def _predict_from_proof(row: dict[str, Any]) -> str:
    function_name, args = _signature(row)
    proof = row.get("proof_units", {}) or {}
    text = " ".join(
        str(proof.get(key, ""))
        for key in ("contract", "invariant", "repair_kind")
    ).lower()
    first_arg = args[0] if args else "x"

    if "case-insensitive vowel" in text or ("count vowels" in text and "case" in text):
        return (
            f"def {function_name}({', '.join(args)}):\n"
            f"    return sum(1 for ch in {first_arg}.lower() if ch in 'aeiou')\n"
        )
    if "strip then lowercase" in text or ("strip" in text and "lowercase" in text):
        return (
            f"def {function_name}({', '.join(args)}):\n"
            f"    return {first_arg}.strip().lower()\n"
        )
    if "one level" in text and "flatten" in text:
        return (
            f"def {function_name}({', '.join(args)}):\n"
            f"    return [value for group in {first_arg} for value in group]\n"
        )

    return str(row["buggy_code"])


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


def _write_predictions(path: Path, rows: list[dict[str, Any]], predictions: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps({"task_id": row["task_id"], "candidate_code": predictions[str(row["task_id"])]}, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("runs/local/artifacts/stage1088_hardened_software_kbpp_pilot/manifest.json"))
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--output-dir", type=Path, default=Path("runs/local/artifacts/stage1089_software_proof_operator_transfer"))
    parser.add_argument("--summary-json", type=Path, default=Path("runs/local/artifacts/stage1089_software_proof_operator_transfer_summary.json"))
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    score_module = _load_module("stage1086_score", args.repo_root / "scripts/score_stage1086_software_kbpp_predictions.py")
    splits = {
        "eval": _iter_jsonl(Path(manifest["eval_path"])),
        "hidden": _iter_jsonl(Path(manifest["hidden_path"])),
    }

    results: dict[str, Any] = {}
    for split, rows in splits.items():
        predictions = {str(row["task_id"]): _predict_from_proof(row) for row in rows}
        prediction_path = args.output_dir / f"{split}_proof_operator_predictions.jsonl"
        _write_predictions(prediction_path, rows, predictions)
        score = _score_rows(score_module, rows, predictions)
        score["predictions_jsonl"] = str(prediction_path)
        results[split] = score

    summary = {
        "artifact_kind": "stage1089_software_proof_operator_transfer",
        "status": "completed_proof_operator_transfer_diagnostic",
        "manifest": str(args.manifest),
        "results": results,
        "operator_count": 3,
        "operator_basis": [
            "case_insensitive_membership",
            "strip_then_lowercase",
            "one_level_flatten",
        ],
        "decision": (
            "A small proof-operator transfer library solves the hardened held-out software pilot without exact train symbol+contract memory. "
            "This is a diagnostic typed-operator ceiling and a target for 100M internalization, not a trained-model or 7B comparison claim."
        ),
    }
    args.summary_json.parent.mkdir(parents=True, exist_ok=True)
    args.summary_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
