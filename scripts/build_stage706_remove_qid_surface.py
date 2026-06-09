#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
QID_RE = re.compile(r"\s*qid=[^\s;]+")


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


def _strip_qid(text: Any) -> str:
    return QID_RE.sub("", str(text or "")).replace("  ", " ").strip()


def _rewrite(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rewritten: list[dict[str, Any]] = []
    text_fields = (
        "retrieval_query_text",
        "retrieval_doc_text",
        "encoder_text",
        "state_text",
    )
    for row in rows:
        out = dict(row)
        for field in text_fields:
            if field in out:
                out[field] = _strip_qid(out[field])
        out["stage706_removed_qid"] = True
        rewritten.append(out)
    return rewritten


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--artifact-json", required=True)
    args = parser.parse_args()

    source_manifest_path = (ROOT / args.source_manifest).resolve()
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    train_rows = _rewrite([row for row in _iter_jsonl(Path(source_manifest["train_dataset_path"]))])
    eval_rows = _rewrite([row for row in _iter_jsonl(Path(source_manifest["eval_dataset_path"]))])

    output_dir = (ROOT / args.output_dir).resolve()
    train_path = output_dir / "agentkernel_lite_encdec_train.jsonl"
    eval_path = output_dir / "agentkernel_lite_encdec_eval.jsonl"
    _write_jsonl(train_path, train_rows)
    _write_jsonl(eval_path, eval_rows)

    manifest = dict(source_manifest)
    manifest.update(
        {
            "artifact_kind": "agentkernel_lite_encdec_stage706_remove_qid_surface",
            "manifest_path": str(output_dir / "agentkernel_lite_encdec_dataset_manifest.json"),
            "train_dataset_path": str(train_path),
            "eval_dataset_path": str(eval_path),
            "train_examples": len(train_rows),
            "eval_examples": len(eval_rows),
            "stage706_source_manifest": str(source_manifest_path),
            "stage706_note": "Removes unique qid text to test whether key-hash gains are reusable or row-ID leakage.",
            "timestamp": int(time.time()),
        }
    )
    manifest_path = output_dir / "agentkernel_lite_encdec_dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    artifact = {
        "artifact_kind": "stage706_remove_qid_surface",
        "dataset_manifest": str(manifest_path),
        "source_manifest": str(source_manifest_path),
        "train_examples": len(train_rows),
        "eval_examples": len(eval_rows),
        "timestamp": int(time.time()),
    }
    artifact_path = (ROOT / args.artifact_json).resolve()
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(artifact, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
