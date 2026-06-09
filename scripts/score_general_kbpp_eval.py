#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


DEPTH_WEIGHTS = {
    "atomic_fact": 1.0,
    "relation": 1.05,
    "schema": 1.05,
    "exception": 1.15,
    "procedure": 1.25,
    "causal_rule": 1.2,
    "math_identity": 1.2,
    "code_api_semantics": 1.2,
    "composition": 1.5,
    "counterfactual_false_claim": 1.2,
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_number}: expected a JSON object")
            rows.append(row)
    return rows


def normalize_answer(value: Any) -> str:
    return " ".join(str(value).strip().split()).casefold()


def load_predictions(path: Path) -> tuple[dict[str, dict[str, Any]], Counter[str]]:
    predictions: dict[str, dict[str, Any]] = {}
    duplicate_counts: Counter[str] = Counter()
    for row in load_jsonl(path):
        unit_id = row.get("unit_id")
        if not unit_id:
            raise ValueError(f"{path}: prediction row missing unit_id: {row}")
        if unit_id in predictions:
            duplicate_counts[str(unit_id)] += 1
            continue
        predictions[str(unit_id)] = row
    return predictions, duplicate_counts


def summarize_group(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    correct = sum(1 for row in rows if row["correct"])
    available_bits = sum(row["available_bits"] for row in rows)
    verified_bits = sum(row["verified_bits"] for row in rows)
    weighted_available_bits = sum(row["weighted_available_bits"] for row in rows)
    weighted_verified_bits = sum(row["weighted_verified_bits"] for row in rows)
    return {
        "total": total,
        "correct": correct,
        "accuracy": correct / total if total else None,
        "available_bits": available_bits,
        "verified_bits": verified_bits,
        "bit_recovery": verified_bits / available_bits if available_bits else None,
        "weighted_available_bits": weighted_available_bits,
        "weighted_verified_bits": weighted_verified_bits,
        "weighted_bit_recovery": weighted_verified_bits / weighted_available_bits if weighted_available_bits else None,
    }


def score(
    *,
    eval_rows: list[dict[str, Any]],
    predictions: dict[str, dict[str, Any]],
    duplicate_counts: Counter[str],
    param_count: float | None,
    inference_compute_proxy: float,
) -> dict[str, Any]:
    scored_rows: list[dict[str, Any]] = []
    seen_eval_ids: set[str] = set()

    for expected in eval_rows:
        unit_id = str(expected["unit_id"])
        seen_eval_ids.add(unit_id)
        prediction = predictions.get(unit_id)
        predicted_answer = "" if prediction is None else prediction.get("answer", "")
        correct = normalize_answer(predicted_answer) == normalize_answer(expected["answer"])
        available_bits = float(expected["verified_bits_if_correct"])
        verified_bits = available_bits if correct else 0.0
        unit_type = str(expected["unit_type"])
        weight = float(DEPTH_WEIGHTS.get(unit_type, 1.0))
        scored_rows.append(
            {
                "unit_id": unit_id,
                "unit_type": unit_type,
                "domain": expected.get("domain"),
                "generalization_split": expected.get("generalization_split"),
                "correct": correct,
                "expected_answer": expected["answer"],
                "predicted_answer": predicted_answer,
                "available_bits": available_bits,
                "verified_bits": verified_bits,
                "depth_weight": weight,
                "weighted_available_bits": available_bits * weight,
                "weighted_verified_bits": verified_bits * weight,
                "missing_prediction": prediction is None,
            }
        )

    by_type = defaultdict(list)
    by_domain = defaultdict(list)
    by_split = defaultdict(list)
    for row in scored_rows:
        by_type[row["unit_type"]].append(row)
        by_domain[row["domain"]].append(row)
        by_split[row["generalization_split"]].append(row)

    total = summarize_group(scored_rows)
    param_count_value = float(param_count) if param_count else None
    compute_proxy = max(float(inference_compute_proxy), 1e-12)
    verified_bits = float(total["verified_bits"])
    weighted_verified_bits = float(total["weighted_verified_bits"])
    composition = summarize_group([row for row in scored_rows if row["unit_type"] == "composition"])
    generalization = summarize_group([row for row in scored_rows if str(row["generalization_split"]).startswith("held_out")])

    extra_prediction_ids = sorted(set(predictions) - seen_eval_ids)
    result = {
        "artifact_kind": "general_kbpp_eval_score",
        "eval_units": len(eval_rows),
        "prediction_units": len(predictions),
        "missing_predictions": sum(1 for row in scored_rows if row["missing_prediction"]),
        "extra_predictions": len(extra_prediction_ids),
        "duplicate_prediction_unit_ids": dict(sorted(duplicate_counts.items())),
        "param_count": param_count_value,
        "inference_compute_proxy": compute_proxy,
        "total": total,
        "by_unit_type": {key: summarize_group(rows) for key, rows in sorted(by_type.items())},
        "by_domain": {key: summarize_group(rows) for key, rows in sorted(by_domain.items())},
        "by_generalization_split": {key: summarize_group(rows) for key, rows in sorted(by_split.items())},
        "composition": composition,
        "generalization": generalization,
        "kbpp": verified_bits / param_count_value if param_count_value else None,
        "composition_kbpp": float(composition["verified_bits"]) / param_count_value if param_count_value else None,
        "generalization_kbpp": float(generalization["verified_bits"]) / param_count_value if param_count_value else None,
        "eid_proxy": weighted_verified_bits / (param_count_value * compute_proxy) if param_count_value else None,
        "extra_prediction_unit_ids_sample": extra_prediction_ids[:20],
    }
    return result


def write_oracle_predictions(eval_rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for row in eval_rows:
            handle.write(
                json.dumps(
                    {
                        "unit_id": row["unit_id"],
                        "answer": row["answer"],
                    },
                    sort_keys=True,
                )
                + "\n"
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval-queries", default="runs/local/tmp/general_kbpp_pilot_v1/general_kbpp_eval_queries.jsonl")
    parser.add_argument("--predictions")
    parser.add_argument("--output", default="runs/local/artifacts/general_kbpp_pilot_score.json")
    parser.add_argument("--param-count", type=float)
    parser.add_argument("--inference-compute-proxy", type=float, default=1.0)
    parser.add_argument("--write-oracle-predictions")
    args = parser.parse_args()

    eval_rows = load_jsonl(ROOT / args.eval_queries)
    if args.write_oracle_predictions:
        write_oracle_predictions(eval_rows, ROOT / args.write_oracle_predictions)

    if not args.predictions:
        if args.write_oracle_predictions:
            return
        raise SystemExit("--predictions is required unless --write-oracle-predictions is used")

    predictions, duplicates = load_predictions(ROOT / args.predictions)
    result = score(
        eval_rows=eval_rows,
        predictions=predictions,
        duplicate_counts=duplicates,
        param_count=args.param_count,
        inference_compute_proxy=args.inference_compute_proxy,
    )
    output_path = ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
