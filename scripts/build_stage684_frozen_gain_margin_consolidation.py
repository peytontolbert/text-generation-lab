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


def answer_correct_ids(path: Path) -> set[str]:
    return {str(row.get("unit_id")) for row in iter_jsonl(path) if bool(row.get("answer_top1"))}


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-manifest", required=True)
    parser.add_argument("--frontier-topk-details-jsonl", required=True)
    parser.add_argument("--frontier-fast-details-jsonl", required=True)
    parser.add_argument("--previous-fast-details-jsonl", required=True)
    parser.add_argument("--overcontinue-fast-details-jsonl", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--artifact-json", required=True)
    parser.add_argument("--miss-margin-threshold", type=float, default=0.04)
    parser.add_argument("--fragile-correct-threshold", type=float, default=0.02)
    parser.add_argument("--miss-weight", type=float, default=2.0)
    parser.add_argument("--protect-weight", type=float, default=3.0)
    args = parser.parse_args()

    source_manifest_path = (ROOT / args.source_manifest).resolve()
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    source_train = Path(source_manifest["train_dataset_path"])
    rows = [row for row in iter_jsonl(source_train)]
    doc_by_id = {
        str(row.get("source_id") or row.get("example_id")): str(row.get("retrieval_doc_text", "") or "")
        for row in rows
    }

    frontier_fast_path = (ROOT / args.frontier_fast_details_jsonl).resolve()
    previous_fast_path = (ROOT / args.previous_fast_details_jsonl).resolve()
    overcontinue_fast_path = (ROOT / args.overcontinue_fast_details_jsonl).resolve()
    frontier_correct = answer_correct_ids(frontier_fast_path)
    previous_correct = answer_correct_ids(previous_fast_path)
    overcontinue_correct = answer_correct_ids(overcontinue_fast_path)
    newly_won = frontier_correct - previous_correct
    overcontinue_lost = frontier_correct - overcontinue_correct

    topk_path = (ROOT / args.frontier_topk_details_jsonl).resolve()
    topk = {str(row.get("unit_id")): row for row in iter_jsonl(topk_path)}

    protected = 0
    targeted_misses = 0
    base_replay = 0
    rewritten: list[dict[str, Any]] = []
    for row in rows:
        source_id = str(row.get("source_id") or row.get("example_id"))
        detail = topk.get(source_id, {})
        margin = detail.get("margin_to_best_wrong")
        best_wrong_id = str(detail.get("best_wrong_source_id") or "")
        negative_doc = doc_by_id.get(best_wrong_id, "")
        answer_top1 = source_id in frontier_correct

        out = dict(row)
        out["retrieval_negative_doc_texts"] = []
        out["stage684_best_wrong_source_id"] = best_wrong_id
        out["stage684_margin_to_best_wrong"] = margin
        out["stage684_newly_won"] = source_id in newly_won
        out["stage684_overcontinue_lost"] = source_id in overcontinue_lost

        should_protect = (
            answer_top1
            and negative_doc
            and (
                source_id in newly_won
                or source_id in overcontinue_lost
                or (margin is not None and float(margin) <= float(args.fragile_correct_threshold))
            )
        )
        should_repair = (
            (not answer_top1)
            and negative_doc
            and margin is not None
            and float(margin) >= -float(args.miss_margin_threshold)
        )
        if should_protect:
            protected += 1
            out["retrieval_negative_doc_texts"] = [negative_doc]
            out["retrieval_loss_weight"] = float(args.protect_weight)
            out["stage684_role"] = "freeze_frontier_gain_or_fragile_correct"
        elif should_repair:
            targeted_misses += 1
            out["retrieval_negative_doc_texts"] = [negative_doc]
            out["retrieval_loss_weight"] = float(args.miss_weight)
            out["stage684_role"] = "repair_stable_low_margin_miss"
        else:
            base_replay += 1
            out["retrieval_loss_weight"] = 1.0
            out["stage684_role"] = "base_replay"
        out["stage684_goal"] = "Freeze Stage682 gains and repair only stable low-margin misses."
        rewritten.append(out)

    output_dir = (ROOT / args.output_dir).resolve()
    train_path = output_dir / "agentkernel_lite_encdec_train.jsonl"
    eval_path = output_dir / "agentkernel_lite_encdec_eval.jsonl"
    write_jsonl(train_path, rewritten)
    write_jsonl(eval_path, rows)

    manifest = dict(source_manifest)
    manifest.update(
        {
            "artifact_kind": "agentkernel_lite_encdec_stage684_frozen_gain_margin_consolidation",
            "manifest_path": str(output_dir / "agentkernel_lite_encdec_dataset_manifest.json"),
            "train_dataset_path": str(train_path),
            "eval_dataset_path": str(eval_path),
            "train_examples": len(rewritten),
            "eval_examples": len(rows),
            "stage684_frontier_topk_details_jsonl": str(topk_path),
            "stage684_frontier_fast_details_jsonl": str(frontier_fast_path),
            "stage684_previous_fast_details_jsonl": str(previous_fast_path),
            "stage684_overcontinue_fast_details_jsonl": str(overcontinue_fast_path),
            "stage684_newly_won_rows": len(newly_won),
            "stage684_overcontinue_lost_rows": len(overcontinue_lost),
            "stage684_protected_rows": protected,
            "stage684_targeted_misses": targeted_misses,
            "stage684_base_replay_rows": base_replay,
            "stage684_miss_margin_threshold": float(args.miss_margin_threshold),
            "stage684_fragile_correct_threshold": float(args.fragile_correct_threshold),
            "stage684_miss_weight": float(args.miss_weight),
            "stage684_protect_weight": float(args.protect_weight),
            "timestamp": int(time.time()),
        }
    )
    manifest_path = output_dir / "agentkernel_lite_encdec_dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    artifact = {
        "artifact_kind": "stage684_frozen_gain_margin_consolidation",
        "dataset_manifest": str(manifest_path),
        "rows": len(rows),
        "newly_won_rows": len(newly_won),
        "overcontinue_lost_rows": len(overcontinue_lost),
        "protected_rows": protected,
        "targeted_misses": targeted_misses,
        "base_replay_rows": base_replay,
        "miss_margin_threshold": float(args.miss_margin_threshold),
        "fragile_correct_threshold": float(args.fragile_correct_threshold),
        "miss_weight": float(args.miss_weight),
        "protect_weight": float(args.protect_weight),
        "verified_bits": sum(float(row.get("stage653_verified_bits_if_correct", 0.0) or 0.0) for row in rows),
        "timestamp": int(time.time()),
    }
    artifact_path = (ROOT / args.artifact_json).resolve()
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(artifact, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
