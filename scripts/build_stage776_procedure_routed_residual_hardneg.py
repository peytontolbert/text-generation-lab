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


def miss_weight(operation: str, exact_miss: bool, args: argparse.Namespace) -> float:
    if operation == "schema":
        return float(args.schema_weight)
    if operation == "math_identity":
        return float(args.math_weight)
    if operation == "composition":
        return float(args.composition_weight if exact_miss else args.miss_weight)
    if operation == "code_api_semantics":
        return float(args.code_weight)
    return float(args.miss_weight)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-manifest", required=True)
    parser.add_argument("--train-details-jsonl", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--artifact-json", required=True)
    parser.add_argument("--miss-weight", type=float, default=6.0)
    parser.add_argument("--schema-weight", type=float, default=10.0)
    parser.add_argument("--math-weight", type=float, default=8.0)
    parser.add_argument("--composition-weight", type=float, default=8.0)
    parser.add_argument("--code-weight", type=float, default=6.0)
    args = parser.parse_args()

    source_manifest_path = (ROOT / args.source_manifest).resolve()
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    source_train = Path(source_manifest["train_dataset_path"])
    source_eval = Path(source_manifest["eval_dataset_path"])
    rows = [row for row in iter_jsonl(source_train)]
    eval_rows = [row for row in iter_jsonl(source_eval)]

    doc_by_id = {
        str(row.get("source_id") or row.get("example_id")): str(row.get("retrieval_doc_text", "") or "")
        for row in rows
    }

    details_path = (ROOT / args.train_details_jsonl).resolve()
    details_by_id = {str(row.get("unit_id")): row for row in iter_jsonl(details_path)}

    rewritten: list[dict[str, Any]] = []
    targeted = 0
    answer_misses = 0
    exact_misses = 0
    missing_negative = 0
    by_operation: dict[str, int] = {}
    by_operation_exact: dict[str, int] = {}

    for row in rows:
        source_id = str(row.get("source_id") or row.get("example_id"))
        detail = details_by_id.get(source_id, {})
        answer_miss = not bool(detail.get("answer_top1", True))
        exact_miss = not bool(detail.get("top1", True))
        operation = str(detail.get("operation") or row.get("operation") or row.get("task_type") or "")
        predicted_id = str(detail.get("predicted_source_id") or "")
        negative_doc = doc_by_id.get(predicted_id, "")

        out = dict(row)
        out["retrieval_negative_doc_texts"] = []
        out["stage776_predicted_source_id"] = predicted_id
        out["stage776_answer_miss"] = bool(answer_miss)
        out["stage776_exact_miss"] = bool(exact_miss)
        out["stage776_factor_mode"] = "text_routed_multi_axis_compose_procedure"

        if answer_miss:
            answer_misses += 1
            by_operation[operation] = by_operation.get(operation, 0) + 1
        if exact_miss:
            exact_misses += 1
            by_operation_exact[operation] = by_operation_exact.get(operation, 0) + 1

        if (answer_miss or exact_miss) and predicted_id and predicted_id != source_id and negative_doc:
            targeted += 1
            out["retrieval_negative_doc_texts"] = [negative_doc]
            out["retrieval_loss_weight"] = miss_weight(operation, exact_miss, args)
            out["stage776_role"] = "procedure_routed_residual_hard_negative"
        else:
            if answer_miss or exact_miss:
                missing_negative += 1
            out["retrieval_loss_weight"] = 1.0
            out["stage776_role"] = "base_replay"
        out["stage776_goal"] = "Concentrate hard-negative pressure on the narrowed procedure-routed residual set."
        rewritten.append(out)

    output_dir = (ROOT / args.output_dir).resolve()
    train_path = output_dir / "agentkernel_lite_encdec_train.jsonl"
    eval_path = output_dir / "agentkernel_lite_encdec_eval.jsonl"
    write_jsonl(train_path, rewritten)
    write_jsonl(eval_path, eval_rows)

    manifest = dict(source_manifest)
    manifest.update(
        {
            "artifact_kind": "agentkernel_lite_encdec_stage776_procedure_routed_residual_hardneg",
            "manifest_path": str(output_dir / "agentkernel_lite_encdec_dataset_manifest.json"),
            "train_dataset_path": str(train_path),
            "eval_dataset_path": str(eval_path),
            "train_examples": len(rewritten),
            "eval_examples": len(eval_rows),
            "source_manifest_path": str(source_manifest_path),
            "stage776_train_details_jsonl": str(details_path),
            "stage776_targeted_hardneg_rows": targeted,
            "stage776_answer_miss_rows": answer_misses,
            "stage776_exact_miss_rows": exact_misses,
            "stage776_missing_negative_rows": missing_negative,
            "stage776_answer_miss_by_operation": by_operation,
            "stage776_exact_miss_by_operation": by_operation_exact,
            "stage776_weights": {
                "code": float(args.code_weight),
                "composition": float(args.composition_weight),
                "math": float(args.math_weight),
                "miss": float(args.miss_weight),
                "schema": float(args.schema_weight),
            },
            "timestamp": int(time.time()),
        }
    )
    manifest_path = output_dir / "agentkernel_lite_encdec_dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    artifact = {
        "artifact_kind": "stage776_procedure_routed_residual_hardneg_dataset",
        "dataset_manifest": str(manifest_path),
        "source_manifest": str(source_manifest_path),
        "train_details_jsonl": str(details_path),
        "rows": len(rewritten),
        "eval_rows": len(eval_rows),
        "targeted_hardneg_rows": targeted,
        "answer_miss_rows": answer_misses,
        "exact_miss_rows": exact_misses,
        "missing_negative_rows": missing_negative,
        "answer_miss_by_operation": by_operation,
        "exact_miss_by_operation": by_operation_exact,
        "weights": manifest["stage776_weights"],
        "timestamp": int(time.time()),
    }
    artifact_path = (ROOT / args.artifact_json).resolve()
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(artifact, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
