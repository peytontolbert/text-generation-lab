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
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--artifact-json", required=True)
    parser.add_argument("--rows", type=int, default=32)
    args = parser.parse_args()

    source_manifest_path = (ROOT / args.source_manifest).resolve()
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    source_train = Path(source_manifest["train_dataset_path"])
    rows = []
    for row in iter_jsonl(source_train):
        if str(row.get("stage783_role", "")) not in {"selector_dropped_direct_answer", ""}:
            continue
        expected = str(row.get("expected_content", "") or "").strip()
        if not expected:
            continue
        out = dict(row)
        out["decoder_text"] = expected
        out["json_decoder_text"] = json.dumps({"action": "respond", "content": expected}, sort_keys=True)
        out["negative_decoder_text"] = ""
        out["decoder_loss_weight"] = 1.0
        out["retrieval_loss_weight"] = 0.0
        out["retrieval_negative_doc_texts"] = []
        out["stage785_role"] = "answer_only_decoder_overfit"
        out["stage785_goal"] = "Test whether the decoder can memorize a tiny selector-dropped answer-only set."
        rows.append(out)
        if len(rows) >= int(args.rows):
            break

    output_dir = (ROOT / args.output_dir).resolve()
    train_path = output_dir / "agentkernel_lite_encdec_train.jsonl"
    eval_path = output_dir / "agentkernel_lite_encdec_eval.jsonl"
    write_jsonl(train_path, rows)
    write_jsonl(eval_path, rows)

    manifest = dict(source_manifest)
    manifest.update(
        {
            "artifact_kind": "agentkernel_lite_encdec_stage785_answer_only_decoder_overfit",
            "manifest_path": str(output_dir / "agentkernel_lite_encdec_dataset_manifest.json"),
            "train_dataset_path": str(train_path),
            "eval_dataset_path": str(eval_path),
            "train_examples": len(rows),
            "eval_examples": len(rows),
            "source_manifest_path": str(source_manifest_path),
            "stage785_rows": len(rows),
            "stage785_goal": "Decoder-only answer memorization diagnostic.",
            "timestamp": int(time.time()),
        }
    )
    manifest_path = output_dir / "agentkernel_lite_encdec_dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    artifact = {
        "artifact_kind": "stage785_answer_only_decoder_overfit_dataset",
        "dataset_manifest": str(manifest_path),
        "source_manifest": str(source_manifest_path),
        "rows": len(rows),
        "timestamp": int(time.time()),
    }
    artifact_path = (ROOT / args.artifact_json).resolve()
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(artifact, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
