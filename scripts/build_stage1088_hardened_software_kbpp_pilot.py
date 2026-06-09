#!/usr/bin/env python3
"""Build a hardened Stage1086-style pilot with held-out repair templates."""

from __future__ import annotations

import argparse
import importlib.util
import json
import random
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_stage1086(repo_root: Path):
    path = repo_root / "scripts/build_stage1086_software_kbpp_pilot_harness.py"
    spec = importlib.util.spec_from_file_location("stage1086_builder", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load stage1086 builder: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=_repo_root())
    parser.add_argument("--output-dir", type=Path, default=Path("runs/local/artifacts/stage1088_hardened_software_kbpp_pilot"))
    parser.add_argument("--summary-json", type=Path, default=Path("runs/local/artifacts/stage1088_hardened_software_kbpp_pilot_summary.json"))
    parser.add_argument("--train-copies", type=int, default=16)
    parser.add_argument("--eval-copies", type=int, default=4)
    parser.add_argument("--hidden-copies", type=int, default=4)
    parser.add_argument("--seed", type=int, default=1088)
    args = parser.parse_args()

    random.seed(int(args.seed))
    stage1086 = _load_stage1086(args.repo_root.resolve())
    templates = list(stage1086.TEMPLATES)
    train_templates = templates[:5]
    heldout_templates = templates[5:]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    split_specs = {
        "train": (train_templates, int(args.train_copies)),
        "eval": (heldout_templates, int(args.eval_copies)),
        "hidden": (heldout_templates, int(args.hidden_copies)),
    }
    by_split: dict[str, int] = {}
    by_category: dict[str, dict[str, int]] = {}
    for split, (split_templates, copies) in split_specs.items():
        rows: list[dict[str, Any]] = []
        for copy_index in range(copies):
            local_templates = list(split_templates)
            random.shuffle(local_templates)
            for template_index, template in enumerate(local_templates):
                row = stage1086._task_from_template(template, copy_index * len(split_templates) + template_index, split)
                row["stage1088_holdout"] = {
                    "heldout_template": split != "train",
                    "train_symbols": [str(item["function_name"]) for item in train_templates],
                    "eval_symbols": [str(item["function_name"]) for item in heldout_templates],
                }
                rows.append(row)
                by_category.setdefault(split, {}).setdefault(str(template["category"]), 0)
                by_category[split][str(template["category"])] += 1
        by_split[split] = len(rows)
        _write_jsonl(args.output_dir / f"{split}.jsonl", rows)
    manifest = {
        "artifact_kind": "stage1088_hardened_software_kbpp_pilot_manifest",
        "train_path": str(args.output_dir / "train.jsonl"),
        "eval_path": str(args.output_dir / "eval.jsonl"),
        "hidden_path": str(args.output_dir / "hidden.jsonl"),
        "prediction_schema": {"task_id": "string", "candidate_code": "complete Python function string"},
        "verifier_script": "scripts/score_stage1086_software_kbpp_predictions.py",
        "holdout_rule": "eval/hidden function templates are absent from train",
    }
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "artifact_kind": "stage1088_hardened_software_kbpp_pilot",
        "status": "completed_hardened_software_kbpp_pilot",
        "manifest": str(args.output_dir / "manifest.json"),
        "by_split": by_split,
        "by_category": by_category,
        "train_symbols": [str(item["function_name"]) for item in train_templates],
        "heldout_symbols": [str(item["function_name"]) for item in heldout_templates],
        "verified_decision_bits": sum(count * 8 for count in by_split.values()),
        "decision": "Hardened software-KBPP pilot with eval/hidden repair templates absent from train. This blocks exact symbol+contract proof-memory lookup.",
    }
    args.summary_json.parent.mkdir(parents=True, exist_ok=True)
    args.summary_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
