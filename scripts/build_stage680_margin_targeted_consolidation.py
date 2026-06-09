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
    parser.add_argument("--topk-details-jsonl", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--artifact-json", required=True)
    parser.add_argument("--miss-margin-threshold", type=float, default=0.05)
    parser.add_argument("--fragile-correct-threshold", type=float, default=0.02)
    parser.add_argument("--miss-weight", type=float, default=2.5)
    parser.add_argument("--fragile-correct-weight", type=float, default=2.0)
    args = parser.parse_args()

    source_manifest_path = (ROOT / args.source_manifest).resolve()
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    source_train = Path(source_manifest["train_dataset_path"])
    rows = [row for row in iter_jsonl(source_train)]
    by_id = {str(row.get("source_id") or row.get("example_id")): row for row in rows}
    doc_by_id = {key: str(row.get("retrieval_doc_text", "") or "") for key, row in by_id.items()}

    details_path = (ROOT / args.topk_details_jsonl).resolve()
    details = {str(row.get("unit_id")): row for row in iter_jsonl(details_path)}

    targeted_misses = 0
    targeted_fragile_correct = 0
    untouched = 0
    rewritten: list[dict[str, Any]] = []
    for row in rows:
        source_id = str(row.get("source_id") or row.get("example_id"))
        detail = details.get(source_id, {})
        margin = detail.get("margin_to_best_wrong")
        answer_top1 = bool(detail.get("answer_top1"))
        best_wrong_id = str(detail.get("best_wrong_source_id") or "")
        out = dict(row)
        negative_doc = doc_by_id.get(best_wrong_id, "")
        out["retrieval_negative_doc_texts"] = []
        out["stage680_best_wrong_source_id"] = best_wrong_id
        out["stage680_margin_to_best_wrong"] = margin
        if (
            (not answer_top1)
            and margin is not None
            and float(margin) >= -float(args.miss_margin_threshold)
            and negative_doc
        ):
            targeted_misses += 1
            out["retrieval_negative_doc_texts"] = [negative_doc]
            out["retrieval_loss_weight"] = float(args.miss_weight)
            out["stage680_role"] = "repair_low_margin_miss"
        elif (
            answer_top1
            and margin is not None
            and float(margin) <= float(args.fragile_correct_threshold)
            and negative_doc
        ):
            targeted_fragile_correct += 1
            out["retrieval_negative_doc_texts"] = [negative_doc]
            out["retrieval_loss_weight"] = float(args.fragile_correct_weight)
            out["stage680_role"] = "protect_fragile_correct"
        else:
            untouched += 1
            out["retrieval_loss_weight"] = 1.0
            out["stage680_role"] = "base_replay"
        out["stage680_goal"] = "Use top-k margins to repair near misses while protecting fragile correct bindings."
        rewritten.append(out)

    output_dir = (ROOT / args.output_dir).resolve()
    train_path = output_dir / "agentkernel_lite_encdec_train.jsonl"
    eval_path = output_dir / "agentkernel_lite_encdec_eval.jsonl"
    write_jsonl(train_path, rewritten)
    write_jsonl(eval_path, rows)

    manifest = dict(source_manifest)
    manifest.update(
        {
            "artifact_kind": "agentkernel_lite_encdec_stage680_margin_targeted_consolidation",
            "manifest_path": str(output_dir / "agentkernel_lite_encdec_dataset_manifest.json"),
            "train_dataset_path": str(train_path),
            "eval_dataset_path": str(eval_path),
            "train_examples": len(rewritten),
            "eval_examples": len(rows),
            "stage680_source_manifest": str(source_manifest_path),
            "stage680_topk_details_jsonl": str(details_path),
            "stage680_targeted_misses": targeted_misses,
            "stage680_targeted_fragile_correct": targeted_fragile_correct,
            "stage680_base_replay_rows": untouched,
            "stage680_miss_margin_threshold": float(args.miss_margin_threshold),
            "stage680_fragile_correct_threshold": float(args.fragile_correct_threshold),
            "stage680_miss_weight": float(args.miss_weight),
            "stage680_fragile_correct_weight": float(args.fragile_correct_weight),
            "timestamp": int(time.time()),
        }
    )
    manifest_path = output_dir / "agentkernel_lite_encdec_dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    artifact = {
        "artifact_kind": "stage680_margin_targeted_consolidation",
        "source_manifest": str(source_manifest_path),
        "topk_details_jsonl": str(details_path),
        "dataset_manifest": str(manifest_path),
        "rows": len(rows),
        "targeted_misses": targeted_misses,
        "targeted_fragile_correct": targeted_fragile_correct,
        "base_replay_rows": untouched,
        "miss_margin_threshold": float(args.miss_margin_threshold),
        "fragile_correct_threshold": float(args.fragile_correct_threshold),
        "miss_weight": float(args.miss_weight),
        "fragile_correct_weight": float(args.fragile_correct_weight),
        "verified_bits": sum(float(row.get("stage653_verified_bits_if_correct", 0.0) or 0.0) for row in rows),
        "timestamp": int(time.time()),
    }
    artifact_path = (ROOT / args.artifact_json).resolve()
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(artifact, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
