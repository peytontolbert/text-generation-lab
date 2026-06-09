#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def add_metric(slot: dict[str, float], result: dict[str, Any]) -> None:
    slot["total"] += float(result.get("total") or 0.0)
    slot["exact_correct"] += float(result.get("exact_correct") or 0.0)
    slot["answer_correct"] += float(result.get("answer_correct") or 0.0)
    slot["available_bits"] += float(result.get("available_bits") or 0.0)
    slot["exact_verified_bits"] += float(result.get("exact_verified_bits") or 0.0)
    slot["answer_verified_bits"] += float(result.get("answer_verified_bits") or 0.0)


def summarize(slot: dict[str, float], *, params: float) -> dict[str, Any]:
    total = int(slot["total"])
    available_bits = float(slot["available_bits"])
    exact_bits = float(slot["exact_verified_bits"])
    answer_bits = float(slot["answer_verified_bits"])
    return {
        "total": total,
        "exact_correct": int(slot["exact_correct"]),
        "answer_correct": int(slot["answer_correct"]),
        "exact_accuracy": float(slot["exact_correct"]) / total if total else None,
        "answer_accuracy": float(slot["answer_correct"]) / total if total else None,
        "available_bits": available_bits,
        "exact_verified_bits": exact_bits,
        "answer_verified_bits": answer_bits,
        "exact_bit_recovery": exact_bits / available_bits if available_bits else None,
        "answer_bit_recovery": answer_bits / available_bits if available_bits else None,
        "exact_kbpp": exact_bits / params if params else None,
        "answer_kbpp": answer_bits / params if params else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shards", nargs="+", required=True)
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()

    aggregate: dict[tuple[str, float], dict[str, float]] = {}
    params = 0.0
    bundle_dir = ""
    dataset_manifest = ""
    shard_summaries = []
    for shard_arg in args.shards:
        shard_path = (ROOT / shard_arg).resolve()
        shard = json.loads(shard_path.read_text(encoding="utf-8"))
        params = float(shard.get("parameter_count") or params)
        bundle_dir = str(shard.get("bundle_dir") or bundle_dir)
        dataset_manifest = str(shard.get("dataset_manifest") or dataset_manifest)
        shard_summaries.append(
            {
                "path": str(shard_path),
                "operation_filter": shard.get("operation_filter", []),
            }
        )
        for result in shard.get("results", []):
            key = (str(result.get("key_factor_mode") or "model"), float(result.get("key_factor_weight") or 0.0))
            slot = aggregate.setdefault(
                key,
                {
                    "total": 0.0,
                    "exact_correct": 0.0,
                    "answer_correct": 0.0,
                    "available_bits": 0.0,
                    "exact_verified_bits": 0.0,
                    "answer_verified_bits": 0.0,
                },
            )
            add_metric(slot, result)

    results = []
    for (mode, weight), slot in aggregate.items():
        result = summarize(slot, params=params)
        result["key_factor_mode"] = mode
        result["key_factor_weight"] = weight
        results.append(result)
    results.sort(key=lambda item: (float(item.get("answer_kbpp") or 0.0), float(item.get("exact_kbpp") or 0.0)), reverse=True)

    output = {
        "artifact_kind": "retrieval_factor_grid_shard_aggregate",
        "bundle_dir": bundle_dir,
        "dataset_manifest": dataset_manifest,
        "parameter_count": params,
        "shards": shard_summaries,
        "results": results,
    }
    output_path = (ROOT / args.output_json).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
