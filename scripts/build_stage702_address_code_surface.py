#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def _rewrite(rows: list[dict[str, Any]], *, prefix: str) -> list[dict[str, Any]]:
    out_rows: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        out = dict(row)
        source_id = str(row.get("source_id") or row.get("example_id") or f"row_{index:04d}")
        addr = f"{prefix}{index:04x}"
        out["stage702_address_code"] = addr
        out["stage702_source_id"] = source_id
        out["retrieval_query_text"] = f"addr={addr} {row.get('retrieval_query_text', '')}"
        out["retrieval_doc_text"] = f"addr={addr} {row.get('retrieval_doc_text', '')}"
        out_rows.append(out)
    return out_rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--artifact-json", required=True)
    parser.add_argument("--prefix", default="a")
    args = parser.parse_args()

    source_manifest_path = (ROOT / args.source_manifest).resolve()
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    train_rows = [row for row in _iter_jsonl(Path(source_manifest["train_dataset_path"]))]
    eval_rows = [row for row in _iter_jsonl(Path(source_manifest["eval_dataset_path"]))]
    output_dir = (ROOT / args.output_dir).resolve()
    train_out = _rewrite(train_rows, prefix=str(args.prefix))
    eval_out = _rewrite(eval_rows, prefix=str(args.prefix))
    train_path = output_dir / "agentkernel_lite_encdec_train.jsonl"
    eval_path = output_dir / "agentkernel_lite_encdec_eval.jsonl"
    _write_jsonl(train_path, train_out)
    _write_jsonl(eval_path, eval_out)

    manifest = dict(source_manifest)
    manifest.update(
        {
            "artifact_kind": "agentkernel_lite_encdec_stage702_address_code_surface",
            "manifest_path": str(output_dir / "agentkernel_lite_encdec_dataset_manifest.json"),
            "train_dataset_path": str(train_path),
            "eval_dataset_path": str(eval_path),
            "train_examples": len(train_out),
            "eval_examples": len(eval_out),
            "stage702_source_manifest": str(source_manifest_path),
            "stage702_address_code_prefix": str(args.prefix),
            "stage702_note": "Diagnostic only: shared row address is an external identity code and is not accepted as generalized neural KBPP without a transfer test.",
            "timestamp": int(time.time()),
        }
    )
    manifest_path = output_dir / "agentkernel_lite_encdec_dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    artifact = {
        "artifact_kind": "stage702_address_code_surface",
        "dataset_manifest": str(manifest_path),
        "source_manifest": str(source_manifest_path),
        "train_examples": len(train_out),
        "eval_examples": len(eval_out),
        "note": manifest["stage702_note"],
        "timestamp": int(time.time()),
    }
    artifact_path = (ROOT / args.artifact_json).resolve()
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(artifact, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
