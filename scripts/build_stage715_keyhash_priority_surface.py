#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
GSEL_RE = re.compile(r"gsel=([^\s;]+)")


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


def _selector_parts(text: str) -> tuple[str, str, str] | None:
    match = GSEL_RE.search(text)
    if not match:
        return None
    parts = match.group(1).split("|")
    if len(parts) < 4:
        return None
    _kind, domain, field, entity = parts[:4]
    if not domain or not field or not entity:
        return None
    return domain, field, entity


def _inject_priority_keys(text: Any) -> str:
    raw = str(text or "")
    parts = _selector_parts(raw)
    if parts is None:
        return raw
    domain, field, entity = parts
    priority = f"kh_domain={domain} kh_field={field} kh_entity={entity}"
    return GSEL_RE.sub(lambda match: f"{match.group(0)} {priority}", raw, count=1)


def _rewrite(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    rewritten: list[dict[str, Any]] = []
    touched = 0
    text_fields = (
        "retrieval_query_text",
        "retrieval_doc_text",
        "encoder_text",
        "state_text",
        "decoder_text",
        "json_decoder_text",
        "negative_decoder_text",
    )
    for row in rows:
        out = dict(row)
        row_touched = False
        for field in text_fields:
            if field in out:
                before = str(out[field] or "")
                after = _inject_priority_keys(before)
                out[field] = after
                row_touched = row_touched or after != before
        out["stage715_keyhash_priority_surface"] = bool(row_touched)
        touched += int(row_touched)
        rewritten.append(out)
    return rewritten, touched


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--artifact-json", required=True)
    args = parser.parse_args()

    source_manifest_path = (ROOT / args.source_manifest).resolve()
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    train_rows, train_touched = _rewrite([row for row in _iter_jsonl(Path(source_manifest["train_dataset_path"]))])
    eval_rows, eval_touched = _rewrite([row for row in _iter_jsonl(Path(source_manifest["eval_dataset_path"]))])

    output_dir = (ROOT / args.output_dir).resolve()
    train_path = output_dir / "agentkernel_lite_encdec_train.jsonl"
    eval_path = output_dir / "agentkernel_lite_encdec_eval.jsonl"
    _write_jsonl(train_path, train_rows)
    _write_jsonl(eval_path, eval_rows)

    manifest = dict(source_manifest)
    manifest.update(
        {
            "artifact_kind": "agentkernel_lite_encdec_stage715_keyhash_priority_surface",
            "manifest_path": str(output_dir / "agentkernel_lite_encdec_dataset_manifest.json"),
            "train_dataset_path": str(train_path),
            "eval_dataset_path": str(eval_path),
            "train_examples": len(train_rows),
            "eval_examples": len(eval_rows),
            "stage715_source_manifest": str(source_manifest_path),
            "stage715_train_rows_touched": train_touched,
            "stage715_eval_rows_touched": eval_touched,
            "stage715_note": "Adds reusable kh_domain/kh_field/kh_entity keys immediately after gsel so keyhash8 prioritizes selector identity over family/collision boilerplate.",
            "timestamp": int(time.time()),
        }
    )
    manifest_path = output_dir / "agentkernel_lite_encdec_dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    artifact = {
        "artifact_kind": "stage715_keyhash_priority_surface",
        "dataset_manifest": str(manifest_path),
        "source_manifest": str(source_manifest_path),
        "train_examples": len(train_rows),
        "eval_examples": len(eval_rows),
        "train_rows_touched": train_touched,
        "eval_rows_touched": eval_touched,
        "timestamp": int(time.time()),
    }
    artifact_path = (ROOT / args.artifact_json).resolve()
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(artifact, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
