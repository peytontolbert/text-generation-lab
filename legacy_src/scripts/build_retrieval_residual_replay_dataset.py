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


def build(args: argparse.Namespace) -> dict[str, Any]:
    source_manifest = json.loads(Path(args.dataset_manifest).read_text(encoding="utf-8"))
    train_path = Path(str(source_manifest["train_dataset_path"]))
    eval_path = Path(str(source_manifest["eval_dataset_path"]))
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    train_by_source = {str(row.get("source_id", "") or ""): row for row in _iter_jsonl(train_path)}
    eval_by_source = {str(row.get("source_id", "") or ""): row for row in _iter_jsonl(eval_path)}
    missed_ids: list[str] = []
    missed_eval_ids: list[str] = []
    predicted_ids: list[str] = []
    predicted_eval_ids: list[str] = []
    for detail in _iter_jsonl(Path(args.details_jsonl)):
        if bool(detail.get("top1")):
            continue
        source_id = str(detail.get("source_id", "") or "")
        predicted_id = str(detail.get("predicted_source_id", "") or "")
        if source_id in train_by_source:
            missed_ids.append(source_id)
        elif bool(args.include_eval_misses) and source_id in eval_by_source:
            missed_eval_ids.append(source_id)
        if bool(args.include_predicted_near_misses) and predicted_id in train_by_source:
            predicted_ids.append(predicted_id)
        elif bool(args.include_eval_misses) and bool(args.include_predicted_near_misses) and predicted_id in eval_by_source:
            predicted_eval_ids.append(predicted_id)

    selected: list[dict[str, Any]] = []
    for source_id, row_source, reason in [
        *[(source_id, train_by_source, "train_retrieval_top1_failure") for source_id in missed_ids],
        *[(source_id, eval_by_source, "eval_retrieval_top1_failure") for source_id in missed_eval_ids],
    ]:
        row = dict(row_source[source_id])
        row["source_type"] = f"{row.get('source_type', 'retrieval')}_residual_replay"
        row["residual_reason"] = reason
        selected.extend(dict(row) for _ in range(max(1, int(args.repeat_failures))))
    for source_id, row_source, reason in [
        *[(source_id, train_by_source, "predicted_near_miss_neighbor") for source_id in predicted_ids],
        *[(source_id, eval_by_source, "eval_predicted_near_miss_neighbor") for source_id in predicted_eval_ids],
    ]:
        row = dict(row_source[source_id])
        row["source_type"] = f"{row.get('source_type', 'retrieval')}_residual_replay"
        row["residual_reason"] = reason
        selected.extend(dict(row) for _ in range(max(1, int(args.repeat_near_misses))))

    if bool(args.mix_original_train):
        selected.extend(_iter_jsonl(train_path))

    output_train = out_dir / "agentkernel_lite_encdec_train.jsonl"
    output_eval = out_dir / "agentkernel_lite_encdec_eval.jsonl"
    with output_train.open("w", encoding="utf-8") as handle:
        for row in selected:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    output_eval.write_text(eval_path.read_text(encoding="utf-8"), encoding="utf-8")

    manifest = dict(source_manifest)
    manifest.update(
        {
            "manifest_path": str(out_dir / "agentkernel_lite_encdec_dataset_manifest.json"),
            "train_dataset_path": str(output_train),
            "eval_dataset_path": str(output_eval),
            "source_manifest_path": str(Path(args.dataset_manifest).resolve()),
            "objective": "retrieval_residual_replay",
            "residual_details_jsonl": str(Path(args.details_jsonl).resolve()),
            "missed_train_source_ids": len(set(missed_ids)),
            "missed_eval_source_ids": len(set(missed_eval_ids)),
            "near_miss_source_ids": len(set(predicted_ids)),
            "near_miss_eval_source_ids": len(set(predicted_eval_ids)),
            "train_examples": len(selected),
            "eval_examples": sum(1 for _ in _iter_jsonl(output_eval)),
            "repeat_failures": int(args.repeat_failures),
            "repeat_near_misses": int(args.repeat_near_misses),
            "mixed_original_train": bool(args.mix_original_train),
        }
    )
    manifest_path = out_dir / "agentkernel_lite_encdec_dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-manifest", required=True)
    parser.add_argument("--details-jsonl", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--repeat-failures", type=int, default=8)
    parser.add_argument("--include-predicted-near-misses", type=int, choices=(0, 1), default=1)
    parser.add_argument("--include-eval-misses", type=int, choices=(0, 1), default=0)
    parser.add_argument("--repeat-near-misses", type=int, default=2)
    parser.add_argument("--mix-original-train", type=int, choices=(0, 1), default=1)
    args = parser.parse_args()
    print(json.dumps(build(args), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
