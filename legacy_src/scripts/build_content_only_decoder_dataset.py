#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterator


def _iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def _write_jsonl(path: Path, rows: Iterator[dict[str, Any]]) -> int:
    count = 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")
            count += 1
    return count


def _convert(row: dict[str, Any], *, source_suffix: str) -> dict[str, Any]:
    copied = dict(row)
    answer = str(copied.get("expected_content", "") or "").strip()
    copied["decoder_text"] = answer
    copied["json_decoder_text"] = json.dumps({"action": "respond", "content": answer}, ensure_ascii=True, separators=(",", ":"))
    copied["decoder_loss_weight"] = 1.0
    copied["source_type"] = f"{copied.get('source_type', 'dataset')}_{source_suffix}"
    copied["decoder_target_style"] = "content_only"
    return copied


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--objective", default="content_only_decoder")
    args = parser.parse_args()

    source_manifest = json.loads(Path(args.dataset_manifest).read_text(encoding="utf-8"))
    output_dir = Path(args.output_dir).resolve()
    train_path = output_dir / "agentkernel_lite_encdec_train.jsonl"
    eval_path = output_dir / "agentkernel_lite_encdec_eval.jsonl"
    train_count = _write_jsonl(
        train_path,
        (_convert(row, source_suffix="content_only") for row in _iter_jsonl(Path(str(source_manifest["train_dataset_path"])))),
    )
    eval_count = _write_jsonl(
        eval_path,
        (_convert(row, source_suffix="content_only") for row in _iter_jsonl(Path(str(source_manifest["eval_dataset_path"])))),
    )
    manifest_path = output_dir / "agentkernel_lite_encdec_dataset_manifest.json"
    manifest = dict(source_manifest)
    manifest.update(
        {
            "manifest_path": str(manifest_path),
            "train_dataset_path": str(train_path),
            "eval_dataset_path": str(eval_path),
            "train_examples": train_count,
            "eval_examples": eval_count,
            "total_examples": train_count + eval_count,
            "objective": str(args.objective),
            "source_manifest_path": str(Path(args.dataset_manifest).resolve()),
            "training_principle": "content-only decoder target: app/orchestrator owns structure, model learns verified answer continuation only",
        }
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
