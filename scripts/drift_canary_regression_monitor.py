from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_MIN_BASELINE = 0.0


def evaluate_canary(canary: dict[str, Any]) -> dict[str, Any]:
    canary_id = str(canary.get("canary_id") or canary.get("slice") or canary.get("id") or "unknown_canary")
    baseline = float(canary.get("baseline_score", DEFAULT_MIN_BASELINE))
    current = float(canary.get("current_score", canary.get("new_score", 0.0)))
    min_score = float(canary.get("min_score", baseline))
    max_drop = float(canary.get("max_allowed_drop", 0.0))
    delta = current - baseline
    failures: list[str] = []
    if current < min_score:
        failures.append("below_min_score")
    if delta < -max_drop:
        failures.append("regression_drop_exceeded")
    if canary.get("locked_eval_leakage") is True:
        failures.append("locked_eval_leakage")
    if canary.get("contamination_detected") is True:
        failures.append("contamination_detected")
    if canary.get("metric_card_present") is False:
        failures.append("missing_metric_card")
    return {
        "canary_id": canary_id,
        "slice_tags": canary.get("slice_tags", []),
        "baseline_score": baseline,
        "current_score": current,
        "delta": round(delta, 6),
        "min_score": min_score,
        "max_allowed_drop": max_drop,
        "passed": not failures,
        "promotion_block_reasons": failures,
    }


def evaluate_canaries(canaries: list[dict[str, Any]]) -> dict[str, Any]:
    records = [evaluate_canary(canary) for canary in canaries]
    failed = [record for record in records if not record["passed"]]
    forgotten = [record["canary_id"] for record in failed if "regression_drop_exceeded" in record["promotion_block_reasons"] or "below_min_score" in record["promotion_block_reasons"]]
    return {
        "canaries": len(canaries),
        "records": records,
        "metrics": {
            "canaries": len(canaries),
            "passed_canaries": len(records) - len(failed),
            "failed_canaries": len(failed),
            "forgotten_skill_count": len(forgotten),
            "forgotten_skills": forgotten,
            "promotion_blocked": bool(failed),
            "promotion_block_reasons": sorted({reason for record in failed for reason in record["promotion_block_reasons"]}),
        },
        "passed": not failed and bool(records),
    }


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate drift canaries and regression gates from metric cards.")
    parser.add_argument("canaries", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    data = read_json(args.canaries)
    rows = data.get("canaries", data if isinstance(data, list) else [])
    card = evaluate_canaries(rows)
    text = json.dumps(card, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
