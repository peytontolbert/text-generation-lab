#!/usr/bin/env python3
"""Build train/eval manifests for Stage1071 direct-answer targets."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def _iter_jsonl(path: Path):
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def _manifest(path: Path, train_path: Path, eval_path: Path, train_rows: list[dict[str, Any]], eval_rows: list[dict[str, Any]], name: str) -> dict[str, Any]:
    manifest = {
        "artifact_kind": "stage1072_direct_answer_dataset_manifest",
        "name": name,
        "train_dataset_path": str(train_path),
        "eval_dataset_path": str(eval_path),
        "train_examples": len(train_rows),
        "eval_examples": len(eval_rows),
        "train_operation_counts": dict(Counter(str(row.get("operation", "unknown")) for row in train_rows)),
        "eval_operation_counts": dict(Counter(str(row.get("operation", "unknown")) for row in eval_rows)),
        "decision": "Manifest for direct-answer decoder or direct value-ranking evaluation over Stage1071 selected-answer targets.",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets-jsonl", type=Path, default=Path("runs/local/artifacts/stage1071_stage1069_direct_answer_targets.jsonl"))
    parser.add_argument("--output-dir", type=Path, default=Path("runs/local/artifacts/stage1072_direct_answer_dataset"))
    parser.add_argument("--summary-json", type=Path, default=Path("runs/local/artifacts/stage1072_direct_answer_dataset_summary.json"))
    args = parser.parse_args()

    by_split: dict[str, list[dict[str, Any]]] = {}
    for row in _iter_jsonl(args.targets_jsonl):
        by_split.setdefault(str(row.get("split", "unknown")), []).append(row)
    train_rows = by_split.get("train", []) + by_split.get("calibration", [])
    eval_rows = by_split.get("eval", [])
    hidden_rows = by_split.get("hidden_eval", [])

    train_path = args.output_dir / "agentkernel_lite_encdec_train.jsonl"
    eval_path = args.output_dir / "agentkernel_lite_encdec_eval.jsonl"
    hidden_train_path = args.output_dir / "agentkernel_lite_encdec_hidden_train_context.jsonl"
    hidden_eval_path = args.output_dir / "agentkernel_lite_encdec_hidden_eval.jsonl"
    _write_jsonl(train_path, train_rows)
    _write_jsonl(eval_path, eval_rows)
    _write_jsonl(hidden_train_path, train_rows)
    _write_jsonl(hidden_eval_path, hidden_rows)

    eval_manifest_path = args.output_dir / "agentkernel_lite_encdec_dataset_manifest.json"
    hidden_manifest_path = args.output_dir / "agentkernel_lite_encdec_hidden_dataset_manifest.json"
    eval_manifest = _manifest(eval_manifest_path, train_path, eval_path, train_rows, eval_rows, "stage1072_eval")
    hidden_manifest = _manifest(hidden_manifest_path, hidden_train_path, hidden_eval_path, train_rows, hidden_rows, "stage1072_hidden_eval")

    summary = {
        "artifact_kind": "stage1072_direct_answer_dataset",
        "status": "completed_stage1072_direct_answer_dataset_manifests",
        "source_targets_jsonl": str(args.targets_jsonl),
        "eval_manifest": str(eval_manifest_path),
        "hidden_manifest": str(hidden_manifest_path),
        "eval_manifest_summary": eval_manifest,
        "hidden_manifest_summary": hidden_manifest,
        "by_split_rows": {split: len(rows) for split, rows in sorted(by_split.items())},
    }
    args.summary_json.parent.mkdir(parents=True, exist_ok=True)
    args.summary_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
