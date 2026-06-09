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
    parser.add_argument(
        "--source-manifest",
        default="runs/local/tmp/stage664_atomic_binding_overfit_sweep/n128/agentkernel_lite_encdec_dataset_manifest.json",
    )
    parser.add_argument(
        "--details-jsonl",
        default="runs/local/artifacts/knowledge_compression_moe_residual_10k_stage666_atomic_overfit_128_polish_lr5e5_steps1000/retrieval_eval_stage666_fast_details.jsonl",
    )
    parser.add_argument("--output-dir", default="runs/local/tmp/stage668_mined_residual_negative_consolidation_n128")
    parser.add_argument("--artifact-json", default="runs/local/artifacts/stage668_mined_residual_negative_consolidation.json")
    parser.add_argument("--miss-weight", type=float, default=3.0)
    args = parser.parse_args()

    source_manifest_path = (ROOT / args.source_manifest).resolve()
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    source_train = Path(source_manifest["train_dataset_path"])
    rows = [row for row in iter_jsonl(source_train)]
    by_id = {str(row.get("source_id") or row.get("example_id")): row for row in rows}
    doc_by_id = {key: str(row.get("retrieval_doc_text", "") or "") for key, row in by_id.items()}

    details_path = (ROOT / args.details_jsonl).resolve()
    details = [row for row in iter_jsonl(details_path)]
    predicted_by_id = {
        str(row.get("unit_id")): str(row.get("predicted_source_id"))
        for row in details
        if not bool(row.get("answer_top1"))
    }

    rewritten: list[dict[str, Any]] = []
    mined = 0
    for row in rows:
        source_id = str(row.get("source_id") or row.get("example_id"))
        out = dict(row)
        predicted_id = predicted_by_id.get(source_id, "")
        negatives: list[str] = []
        if predicted_id and predicted_id != source_id and predicted_id in doc_by_id:
            negatives.append(doc_by_id[predicted_id])
        if negatives:
            mined += 1
            out["retrieval_negative_doc_texts"] = negatives
            out["retrieval_loss_weight"] = float(args.miss_weight)
            out["stage668_mined_negative_source_ids"] = [predicted_id]
        else:
            out["retrieval_negative_doc_texts"] = []
            out["retrieval_loss_weight"] = 1.0
            out["stage668_mined_negative_source_ids"] = []
        out["stage668_goal"] = "Use mined residual top-1 confusions instead of equal-weight all-negative consolidation."
        rewritten.append(out)

    output_dir = (ROOT / args.output_dir).resolve()
    train_path = output_dir / "agentkernel_lite_encdec_train.jsonl"
    eval_path = output_dir / "agentkernel_lite_encdec_eval.jsonl"
    write_jsonl(train_path, rewritten)
    write_jsonl(eval_path, rows)

    manifest = dict(source_manifest)
    manifest.update(
        {
            "artifact_kind": "agentkernel_lite_encdec_stage668_mined_residual_negative_consolidation",
            "manifest_path": str(output_dir / "agentkernel_lite_encdec_dataset_manifest.json"),
            "train_dataset_path": str(train_path),
            "eval_dataset_path": str(eval_path),
            "train_examples": len(rewritten),
            "eval_examples": len(rows),
            "stage668_source_manifest": str(source_manifest_path),
            "stage668_details_jsonl": str(details_path),
            "stage668_mined_negative_rows": mined,
            "stage668_miss_weight": float(args.miss_weight),
            "stage668_goal": "Turn 64->128 recursive doubling into clean 2x by targeting actual residual confusions.",
            "stage668_acceptance": "Near-perfect 128-row exact/answer recovery under no-filter full-corpus scoring.",
            "timestamp": int(time.time()),
        }
    )
    manifest_path = output_dir / "agentkernel_lite_encdec_dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    artifact = {
        "artifact_kind": "stage668_mined_residual_negative_consolidation",
        "source_manifest": str(source_manifest_path),
        "details_jsonl": str(details_path),
        "dataset_manifest": str(manifest_path),
        "rows": len(rows),
        "mined_negative_rows": mined,
        "miss_weight": float(args.miss_weight),
        "verified_bits": sum(float(row.get("stage653_verified_bits_if_correct", 0.0) or 0.0) for row in rows),
        "decision_rule": "If mined residual negatives improve Stage666, use them as the consolidation phase before each recursive doubling.",
        "timestamp": int(time.time()),
    }
    artifact_path = (ROOT / args.artifact_json).resolve()
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(artifact, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
