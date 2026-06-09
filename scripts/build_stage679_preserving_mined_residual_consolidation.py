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
    parser.add_argument("--details-jsonl", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--artifact-json", required=True)
    parser.add_argument("--miss-weight", type=float, default=2.0)
    parser.add_argument("--correct-weight", type=float, default=2.0)
    args = parser.parse_args()

    source_manifest_path = (ROOT / args.source_manifest).resolve()
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    source_train = Path(source_manifest["train_dataset_path"])
    rows = [row for row in iter_jsonl(source_train)]
    by_id = {str(row.get("source_id") or row.get("example_id")): row for row in rows}
    doc_by_id = {key: str(row.get("retrieval_doc_text", "") or "") for key, row in by_id.items()}

    details_path = (ROOT / args.details_jsonl).resolve()
    details = [row for row in iter_jsonl(details_path)]
    detail_by_id = {str(row.get("unit_id")): row for row in details}

    rewritten: list[dict[str, Any]] = []
    mined = 0
    preserved = 0
    for row in rows:
        source_id = str(row.get("source_id") or row.get("example_id"))
        detail = detail_by_id.get(source_id, {})
        answer_top1 = bool(detail.get("answer_top1"))
        predicted_id = str(detail.get("predicted_source_id") or "")
        out = dict(row)
        negatives: list[str] = []
        if (not answer_top1) and predicted_id and predicted_id != source_id and predicted_id in doc_by_id:
            negatives.append(doc_by_id[predicted_id])
        if negatives:
            mined += 1
            out["retrieval_negative_doc_texts"] = negatives
            out["retrieval_loss_weight"] = float(args.miss_weight)
            out["stage679_mined_negative_source_ids"] = [predicted_id]
            out["stage679_role"] = "repair_wrong_top1"
        else:
            if answer_top1:
                preserved += 1
                out["retrieval_loss_weight"] = float(args.correct_weight)
                out["stage679_role"] = "preserve_correct_top1"
            else:
                out["retrieval_loss_weight"] = 1.0
                out["stage679_role"] = "unmined_residual"
            out["retrieval_negative_doc_texts"] = []
            out["stage679_mined_negative_source_ids"] = []
        out["stage679_goal"] = "Preserve already-correct bindings while repairing mined residual top-1 confusions."
        rewritten.append(out)

    output_dir = (ROOT / args.output_dir).resolve()
    train_path = output_dir / "agentkernel_lite_encdec_train.jsonl"
    eval_path = output_dir / "agentkernel_lite_encdec_eval.jsonl"
    write_jsonl(train_path, rewritten)
    write_jsonl(eval_path, rows)

    manifest = dict(source_manifest)
    manifest.update(
        {
            "artifact_kind": "agentkernel_lite_encdec_stage679_preserving_mined_residual_consolidation",
            "manifest_path": str(output_dir / "agentkernel_lite_encdec_dataset_manifest.json"),
            "train_dataset_path": str(train_path),
            "eval_dataset_path": str(eval_path),
            "train_examples": len(rewritten),
            "eval_examples": len(rows),
            "stage679_source_manifest": str(source_manifest_path),
            "stage679_details_jsonl": str(details_path),
            "stage679_mined_negative_rows": mined,
            "stage679_preserved_correct_rows": preserved,
            "stage679_miss_weight": float(args.miss_weight),
            "stage679_correct_weight": float(args.correct_weight),
            "stage679_goal": "Anti-forgetting consolidation for the 256 atomic binding rung.",
            "timestamp": int(time.time()),
        }
    )
    manifest_path = output_dir / "agentkernel_lite_encdec_dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    artifact = {
        "artifact_kind": "stage679_preserving_mined_residual_consolidation",
        "source_manifest": str(source_manifest_path),
        "details_jsonl": str(details_path),
        "dataset_manifest": str(manifest_path),
        "rows": len(rows),
        "mined_negative_rows": mined,
        "preserved_correct_rows": preserved,
        "miss_weight": float(args.miss_weight),
        "correct_weight": float(args.correct_weight),
        "verified_bits": sum(float(row.get("stage653_verified_bits_if_correct", 0.0) or 0.0) for row in rows),
        "decision_rule": "If repeated mined negatives forget, raise correct-row replay weight while keeping residual negatives targeted.",
        "timestamp": int(time.time()),
    }
    artifact_path = (ROOT / args.artifact_json).resolve()
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(artifact, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
