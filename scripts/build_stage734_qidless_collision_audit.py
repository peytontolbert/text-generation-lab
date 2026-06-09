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
TEXT_FIELDS = {
    "decoder_text",
    "encoder_text",
    "json_decoder_text",
    "negative_decoder_text",
    "retrieval_doc_text",
    "retrieval_query_text",
    "state_text",
}


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


def strip_qid(text: str) -> tuple[str, int]:
    rewritten, count = QID_RE.subn("", str(text or ""))
    return rewritten, count


def rewrite_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    removed = 0
    for key in TEXT_FIELDS:
        if key not in out:
            continue
        out[key], count = strip_qid(str(out.get(key, "") or ""))
        removed += count
    out["stage734_qidless_collision_audit"] = True
    out["stage734_qid_tokens_removed"] = removed
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-manifest",
        default="runs/local/tmp/stage726_selector_collision_factor_surface/agentkernel_lite_encdec_dataset_manifest.json",
    )
    parser.add_argument("--output-dir", default="runs/local/tmp/stage734_qidless_collision_audit")
    parser.add_argument("--artifact-json", default="runs/local/artifacts/stage734_qidless_collision_audit.json")
    args = parser.parse_args()

    source_manifest_path = (ROOT / args.source_manifest).resolve()
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    train_rows = [rewrite_row(row) for row in iter_jsonl(Path(str(source_manifest["train_dataset_path"])))]
    eval_rows = [rewrite_row(row) for row in iter_jsonl(Path(str(source_manifest["eval_dataset_path"])))]

    output_dir = (ROOT / args.output_dir).resolve()
    train_path = output_dir / "agentkernel_lite_encdec_train.jsonl"
    eval_path = output_dir / "agentkernel_lite_encdec_eval.jsonl"
    write_jsonl(train_path, train_rows)
    write_jsonl(eval_path, eval_rows)

    train_removed = sum(int(row.get("stage734_qid_tokens_removed", 0) or 0) for row in train_rows)
    eval_removed = sum(int(row.get("stage734_qid_tokens_removed", 0) or 0) for row in eval_rows)
    manifest = dict(source_manifest)
    manifest.update(
        {
            "artifact_kind": "agentkernel_lite_encdec_stage734_qidless_collision_audit",
            "manifest_path": str(output_dir / "agentkernel_lite_encdec_dataset_manifest.json"),
            "train_dataset_path": str(train_path),
            "eval_dataset_path": str(eval_path),
            "train_examples": len(train_rows),
            "eval_examples": len(eval_rows),
            "stage734_source_manifest": str(source_manifest_path),
            "stage734_qidless_collision_audit": True,
            "stage734_train_qid_tokens_removed": train_removed,
            "stage734_eval_qid_tokens_removed": eval_removed,
            "stage734_goal": "Audit Stage732-733 text-domain/field/entity factor without qid text in natural query/doc fields.",
            "timestamp": int(time.time()),
        }
    )
    manifest_path = output_dir / "agentkernel_lite_encdec_dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    artifact = {
        "artifact_kind": "stage734_qidless_collision_audit",
        "source_manifest": str(source_manifest_path),
        "dataset_manifest": str(manifest_path),
        "train_rows": len(train_rows),
        "eval_rows": len(eval_rows),
        "train_qid_tokens_removed": train_removed,
        "eval_qid_tokens_removed": eval_removed,
        "decision_rule": "Stage733 should retain >=8 answer KBPP with text_domain_field_entity when qid is removed from natural text.",
        "timestamp": int(time.time()),
    }
    artifact_path = (ROOT / args.artifact_json).resolve()
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(artifact, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
