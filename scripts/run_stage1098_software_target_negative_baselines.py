#!/usr/bin/env python3
"""Run negative baselines for the Stage1096 100M software target package."""

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


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def _buggy_from_prompt(prompt: str) -> str:
    matches = list(re.finditer(r"^def\s+[A-Za-z_][A-Za-z0-9_]*\([^)]*\):", prompt, re.MULTILINE))
    if not matches:
        return ""
    return prompt[matches[-1].start():].strip() + "\n"


def _signature_only(target: dict[str, Any]) -> str:
    return f"{target['signature_target']}\n    pass\n"


def _score_split(score_script, manifest: Path, split: str, predictions_path: Path, output_dir: Path, mode: str) -> dict[str, Any]:
    summary_path = output_dir / f"{split}_{mode}_score_summary.json"
    # Use the scorer module directly to avoid shelling out for each baseline.
    score_module = _load_module("stage1097_score", score_script)
    old_argv_safe = {
        "manifest": str(manifest),
        "split": split,
        "predictions_jsonl": str(predictions_path),
    }
    stage1086 = _load_module("stage1086_score", Path("scripts/score_stage1086_software_kbpp_predictions.py"))
    package = json.loads(manifest.read_text(encoding="utf-8"))
    targets = _iter_jsonl(Path(package[f"{split}_targets_path"]))
    predictions = score_module._load_predictions(predictions_path)
    summary, score_rows = score_module._score(stage1086, targets, predictions)
    scores_path = output_dir / f"{split}_{mode}_scores.jsonl"
    _write_jsonl(scores_path, score_rows)
    result = {
        "mode": mode,
        "split": split,
        "predictions_jsonl": str(predictions_path),
        "scores_jsonl": str(scores_path),
        **summary,
        "scorer_inputs": old_argv_safe,
    }
    summary_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("runs/local/artifacts/stage1096_100m_software_operator_training_package/manifest.json"))
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--output-dir", type=Path, default=Path("runs/local/artifacts/stage1098_software_target_negative_baselines"))
    parser.add_argument("--summary-json", type=Path, default=Path("runs/local/artifacts/stage1098_software_target_negative_baselines_summary.json"))
    args = parser.parse_args()

    package = json.loads(args.manifest.read_text(encoding="utf-8"))
    modes = ["empty", "signature_only", "copy_buggy_from_prompt"]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, Any] = {}
    scorer_path = args.repo_root / "scripts/score_stage1097_100m_software_target_predictions.py"

    for mode in modes:
        results[mode] = {}
        for split in ("eval", "hidden"):
            targets = _iter_jsonl(Path(package[f"{split}_targets_path"]))
            predictions: list[dict[str, Any]] = []
            for target in targets:
                if mode == "empty":
                    candidate = ""
                elif mode == "signature_only":
                    candidate = _signature_only(target)
                elif mode == "copy_buggy_from_prompt":
                    candidate = _buggy_from_prompt(str(target["prompt"]))
                else:
                    raise ValueError(mode)
                predictions.append({"task_id": target["task_id"], "candidate_code": candidate})
            prediction_path = args.output_dir / f"{split}_{mode}_predictions.jsonl"
            _write_jsonl(prediction_path, predictions)
            results[mode][split] = _score_split(scorer_path, args.manifest, split, prediction_path, args.output_dir, mode)

    summary = {
        "artifact_kind": "stage1098_software_target_negative_baselines",
        "status": "completed_negative_baselines",
        "manifest": str(args.manifest),
        "modes": modes,
        "results": results,
        "decision": (
            "Negative baselines for the Stage1096 target package. These establish the floor before 100M or 7B model predictions are scored."
        ),
    }
    args.summary_json.parent.mkdir(parents=True, exist_ok=True)
    args.summary_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
