#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-manifest", required=True)
    parser.add_argument("--frontier-topk-details-jsonl", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--artifact-json", required=True)
    parser.add_argument("--miss-margin-threshold", type=float, default=0.04)
    parser.add_argument("--miss-weight", type=float, default=2.0)
    args = parser.parse_args()

    source_manifest_path = (ROOT / args.source_manifest).resolve()
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    source_train = Path(source_manifest["train_dataset_path"])
    rows = [row for row in iter_jsonl(source_train)]
    doc_by_id = {
        str(row.get("source_id") or row.get("example_id")): str(row.get("retrieval_doc_text", "") or "")
        for row in rows
    }
    details_path = (ROOT / args.frontier_topk_details_jsonl).resolve()
    details = {str(row.get("unit_id")): row for row in iter_jsonl(details_path)}

    targeted = 0
    base = 0
    rewritten: list[dict[str, Any]] = []
    for row in rows:
        source_id = str(row.get("source_id") or row.get("example_id"))
        detail = details.get(source_id, {})
        answer_top1 = bool(detail.get("answer_top1"))
        margin = detail.get("margin_to_best_wrong")
        best_wrong_id = str(detail.get("best_wrong_source_id") or "")
        negative_doc = doc_by_id.get(best_wrong_id, "")
        out = dict(row)
        out["retrieval_negative_doc_texts"] = []
        out["stage686_margin_to_best_wrong"] = margin
        out["stage686_best_wrong_source_id"] = best_wrong_id
        if (
            (not answer_top1)
            and negative_doc
            and margin is not None
            and float(margin) >= -float(args.miss_margin_threshold)
        ):
            targeted += 1
            out["retrieval_negative_doc_texts"] = [negative_doc]
            out["retrieval_loss_weight"] = float(args.miss_weight)
            out["stage686_role"] = "repair_low_margin_miss"
        else:
            base += 1
            out["retrieval_loss_weight"] = 1.0
            out["stage686_role"] = "base_replay_no_freeze"
        out["stage686_goal"] = "Repair only stable low-margin misses; do not hard-negative-freeze correct rows."
        rewritten.append(out)

    output_dir = (ROOT / args.output_dir).resolve()
    train_path = output_dir / "agentkernel_lite_encdec_train.jsonl"
    eval_path = output_dir / "agentkernel_lite_encdec_eval.jsonl"
    write_jsonl(train_path, rewritten)
    write_jsonl(eval_path, rows)

    manifest = dict(source_manifest)
    manifest.update(
        {
            "artifact_kind": "agentkernel_lite_encdec_stage686_repair_only_margin_consolidation",
            "manifest_path": str(output_dir / "agentkernel_lite_encdec_dataset_manifest.json"),
            "train_dataset_path": str(train_path),
            "eval_dataset_path": str(eval_path),
            "train_examples": len(rewritten),
            "eval_examples": len(rows),
            "stage686_frontier_topk_details_jsonl": str(details_path),
            "stage686_targeted_misses": targeted,
            "stage686_base_replay_rows": base,
            "stage686_miss_margin_threshold": float(args.miss_margin_threshold),
            "stage686_miss_weight": float(args.miss_weight),
            "timestamp": int(time.time()),
        }
    )
    manifest_path = output_dir / "agentkernel_lite_encdec_dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    artifact = {
        "artifact_kind": "stage686_repair_only_margin_consolidation",
        "dataset_manifest": str(manifest_path),
        "rows": len(rows),
        "targeted_misses": targeted,
        "base_replay_rows": base,
        "miss_margin_threshold": float(args.miss_margin_threshold),
        "miss_weight": float(args.miss_weight),
        "verified_bits": sum(float(row.get("stage653_verified_bits_if_correct", 0.0) or 0.0) for row in rows),
        "timestamp": int(time.time()),
    }
    artifact_path = (ROOT / args.artifact_json).resolve()
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(artifact, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
