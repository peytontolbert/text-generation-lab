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
    parser.add_argument("--train-details-jsonl", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--artifact-json", required=True)
    parser.add_argument("--miss-weight", type=float, default=16.0)
    args = parser.parse_args()

    source_manifest_path = (ROOT / args.source_manifest).resolve()
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    source_train = Path(source_manifest["train_dataset_path"])
    source_eval = Path(source_manifest["eval_dataset_path"])
    train_rows = [row for row in iter_jsonl(source_train)]
    eval_rows = [row for row in iter_jsonl(source_eval)]

    row_by_id = {str(row.get("source_id") or row.get("example_id")): row for row in train_rows}
    doc_by_id = {source_id: str(row.get("retrieval_doc_text", "") or "") for source_id, row in row_by_id.items()}
    details_path = (ROOT / args.train_details_jsonl).resolve()
    details = [row for row in iter_jsonl(details_path)]

    selected: list[dict[str, Any]] = []
    missing_negative = 0
    for detail in details:
        if str(detail.get("operation")) != "schema":
            continue
        if bool(detail.get("top1", True)):
            continue
        source_id = str(detail.get("unit_id") or "")
        predicted_id = str(detail.get("predicted_source_id") or "")
        base = row_by_id.get(source_id)
        negative_doc = doc_by_id.get(predicted_id, "")
        if not base:
            continue
        out = dict(base)
        out["stage781_role"] = "schema_residual_exact_miss_overfit"
        out["stage781_predicted_source_id"] = predicted_id
        out["stage781_goal"] = "Test whether isolated schema residual misses can be moved by neural-only contrastive training."
        out["retrieval_loss_weight"] = float(args.miss_weight)
        if predicted_id and predicted_id != source_id and negative_doc:
            out["retrieval_negative_doc_texts"] = [negative_doc]
        else:
            out["retrieval_negative_doc_texts"] = []
            missing_negative += 1
        selected.append(out)

    output_dir = (ROOT / args.output_dir).resolve()
    train_path = output_dir / "agentkernel_lite_encdec_train.jsonl"
    eval_path = output_dir / "agentkernel_lite_encdec_eval.jsonl"
    write_jsonl(train_path, selected)
    write_jsonl(eval_path, eval_rows)

    manifest = dict(source_manifest)
    manifest.update(
        {
            "artifact_kind": "agentkernel_lite_encdec_stage781_schema_residual_overfit",
            "manifest_path": str(output_dir / "agentkernel_lite_encdec_dataset_manifest.json"),
            "train_dataset_path": str(train_path),
            "eval_dataset_path": str(eval_path),
            "train_examples": len(selected),
            "eval_examples": len(eval_rows),
            "source_manifest_path": str(source_manifest_path),
            "stage781_train_details_jsonl": str(details_path),
            "stage781_schema_exact_miss_rows": len(selected),
            "stage781_missing_negative_rows": missing_negative,
            "stage781_miss_weight": float(args.miss_weight),
            "timestamp": int(time.time()),
        }
    )
    manifest_path = output_dir / "agentkernel_lite_encdec_dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    artifact = {
        "artifact_kind": "stage781_schema_residual_overfit_dataset",
        "dataset_manifest": str(manifest_path),
        "source_manifest": str(source_manifest_path),
        "train_details_jsonl": str(details_path),
        "schema_exact_miss_rows": len(selected),
        "eval_rows": len(eval_rows),
        "missing_negative_rows": missing_negative,
        "miss_weight": float(args.miss_weight),
        "timestamp": int(time.time()),
    }
    artifact_path = (ROOT / args.artifact_json).resolve()
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(artifact, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
