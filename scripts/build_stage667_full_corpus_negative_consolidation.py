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
    parser.add_argument("--output-dir", default="runs/local/tmp/stage667_full_corpus_negative_consolidation_n128")
    parser.add_argument("--artifact-json", default="runs/local/artifacts/stage667_full_corpus_negative_consolidation.json")
    parser.add_argument("--max-negatives", type=int, default=127)
    args = parser.parse_args()

    source_manifest_path = (ROOT / args.source_manifest).resolve()
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    source_train = Path(source_manifest["train_dataset_path"])
    rows = [row for row in iter_jsonl(source_train)]
    docs = [str(row.get("retrieval_doc_text", "") or "") for row in rows]
    if any(not doc for doc in docs):
        raise RuntimeError("all rows must have retrieval_doc_text")

    rewritten: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        out = dict(row)
        negatives = [doc for j, doc in enumerate(docs) if j != idx]
        out["retrieval_negative_doc_texts"] = negatives[: max(0, int(args.max_negatives))]
        out["retrieval_loss_weight"] = float(out.get("retrieval_loss_weight", 1.0) or 1.0)
        out["stage667_full_corpus_negative_count"] = len(out["retrieval_negative_doc_texts"])
        out["stage667_goal"] = "Expose cross-batch/full-corpus negatives during recursive atomic binding consolidation."
        rewritten.append(out)

    output_dir = (ROOT / args.output_dir).resolve()
    train_path = output_dir / "agentkernel_lite_encdec_train.jsonl"
    eval_path = output_dir / "agentkernel_lite_encdec_eval.jsonl"
    write_jsonl(train_path, rewritten)
    write_jsonl(eval_path, rows)

    manifest = dict(source_manifest)
    manifest.update(
        {
            "artifact_kind": "agentkernel_lite_encdec_stage667_full_corpus_negative_consolidation",
            "manifest_path": str(output_dir / "agentkernel_lite_encdec_dataset_manifest.json"),
            "train_dataset_path": str(train_path),
            "eval_dataset_path": str(eval_path),
            "train_examples": len(rewritten),
            "eval_examples": len(rows),
            "stage667_source_manifest": str(source_manifest_path),
            "stage667_full_corpus_negatives": True,
            "stage667_max_negatives_per_row": int(args.max_negatives),
            "stage667_goal": "Turn the 64->128 recursive doubling step into a clean 2x by adding full-corpus negative pressure during consolidation.",
            "stage667_acceptance": "Near-perfect 128-row exact/answer recovery under no-filter full-corpus scoring.",
            "timestamp": int(time.time()),
        }
    )
    manifest_path = output_dir / "agentkernel_lite_encdec_dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    artifact = {
        "artifact_kind": "stage667_full_corpus_negative_consolidation",
        "source_manifest": str(source_manifest_path),
        "dataset_manifest": str(manifest_path),
        "rows": len(rows),
        "max_negatives_per_row": int(args.max_negatives),
        "mean_negatives_per_row": sum(len(row["retrieval_negative_doc_texts"]) for row in rewritten) / len(rewritten),
        "verified_bits": sum(float(row.get("stage653_verified_bits_if_correct", 0.0) or 0.0) for row in rows),
        "decision_rule": "If this solves 128, continue recursive doubling with full-corpus-negative consolidation at each rung.",
        "timestamp": int(time.time()),
    }
    artifact_path = (ROOT / args.artifact_json).resolve()
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(artifact, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
