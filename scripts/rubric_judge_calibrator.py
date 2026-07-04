from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

AUTHORITY_CLOSED = {
    "model_execution": False,
    "training": False,
    "runtime": False,
    "source_body_emission": False,
    "gemma": False,
    "scoring_authorized": False,
}

DEFAULT_WEIGHTS = {
    "correctness": 0.35,
    "grounding": 0.20,
    "minimality": 0.12,
    "safety": 0.15,
    "style": 0.08,
    "test_plan": 0.10,
}


def clamp(value: Any, low: float = 0.0, high: float = 1.0) -> float:
    try:
        x = float(value)
    except (TypeError, ValueError):
        x = 0.0
    return max(low, min(high, x))


def rubric_score(dimensions: Mapping[str, Any], weights: Mapping[str, float] | None = None) -> dict[str, Any]:
    weights = dict(weights or DEFAULT_WEIGHTS)
    total_weight = sum(max(0.0, float(w)) for w in weights.values()) or 1.0
    contributions: dict[str, float] = {}
    for name, weight in sorted(weights.items()):
        contributions[name] = clamp(dimensions.get(name, 0.0)) * max(0.0, float(weight)) / total_weight
    return {
        "score": float(sum(contributions.values())),
        "contributions": contributions,
        "missing_dimensions": sorted(name for name in weights if name not in dimensions),
    }


def expected_verifier_agreement(score: float, *, accept_threshold: float = 0.75) -> bool:
    return score >= accept_threshold


def calibrate_judge_row(row: Mapping[str, Any], *, accept_threshold: float = 0.75, review_threshold: float = 0.55, high_conf_threshold: float = 0.85) -> dict[str, Any]:
    row_id = str(row.get("row_id") or row.get("id") or "")
    rubric = rubric_score(row.get("rubric", {}) if isinstance(row.get("rubric"), Mapping) else {})
    judge_score = clamp(row.get("judge_score", rubric["score"]))
    judge_confidence = clamp(row.get("judge_confidence", judge_score))
    verifier_pass = bool(row.get("verifier_pass", False))
    hidden_or_leak = bool(row.get("hidden_reference", False) or row.get("internal_token_leak", False) or row.get("authority_open", False))
    judge_accepts = judge_score >= accept_threshold and judge_confidence >= review_threshold
    verifier_disagreement = judge_accepts != verifier_pass
    reasons: list[str] = []
    if hidden_or_leak:
        route = "QUARANTINE"
        reasons.append("authority_or_leak_risk")
    elif verifier_disagreement and judge_confidence >= high_conf_threshold:
        route = "MANUAL_REVIEW"
        reasons.append("high_confidence_judge_verifier_disagreement")
    elif verifier_disagreement:
        route = "MANUAL_REVIEW"
        reasons.append("judge_verifier_disagreement")
    elif verifier_pass and judge_accepts:
        route = "ACCEPT_VERIFIED"
        reasons.append("rubric_and_verifier_agree_accept")
    elif not verifier_pass and not judge_accepts:
        route = "REJECT_OR_REPAIR"
        reasons.append("rubric_and_verifier_agree_reject")
    elif judge_score < review_threshold:
        route = "REJECT_OR_REPAIR"
        reasons.append("low_rubric_score")
    else:
        route = "MANUAL_REVIEW"
        reasons.append("uncertain_calibration")
    calibrated_confidence = judge_confidence * (1.0 - abs(judge_score - rubric["score"]))
    if verifier_disagreement:
        calibrated_confidence *= 0.5
    if hidden_or_leak:
        calibrated_confidence = 0.0
    return {
        "row_id": row_id,
        "rubric_score": rubric["score"],
        "rubric_contributions": rubric["contributions"],
        "missing_rubric_dimensions": rubric["missing_dimensions"],
        "judge_score": judge_score,
        "judge_confidence": judge_confidence,
        "calibrated_confidence": clamp(calibrated_confidence),
        "verifier_pass": verifier_pass,
        "judge_accepts": judge_accepts,
        "verifier_disagreement": verifier_disagreement,
        "risk_route": route,
        "reasons": sorted(set(reasons)),
        "authority": AUTHORITY_CLOSED,
    }


def calibration_card(rows: list[Mapping[str, Any]], *, accept_threshold: float = 0.75) -> dict[str, Any]:
    calibrated = [calibrate_judge_row(row, accept_threshold=accept_threshold) for row in rows]
    route_counts = Counter(row["risk_route"] for row in calibrated)
    disagreement = sum(1 for row in calibrated if row["verifier_disagreement"])
    high_conf_disagreement = sum(1 for row in calibrated if "high_confidence_judge_verifier_disagreement" in row["reasons"])
    brier_rows = []
    for row in calibrated:
        target = 1.0 if row["verifier_pass"] else 0.0
        brier_rows.append((row["calibrated_confidence"] - target) ** 2)
    return {
        "passed": high_conf_disagreement == 0,
        "rows": len(calibrated),
        "route_counts": dict(sorted(route_counts.items())),
        "verifier_disagreement_rows": disagreement,
        "high_confidence_disagreement_rows": high_conf_disagreement,
        "mean_brier": float(sum(brier_rows) / max(1, len(brier_rows))),
        "calibrated_rows": calibrated,
        "authority": AUTHORITY_CLOSED,
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate rubric/judge outputs against verifier signals without model execution.")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rows = read_jsonl(args.input) if args.input else [
        {"row_id": "accept", "rubric": {"correctness": 1, "grounding": 1, "minimality": .8, "safety": 1, "style": .8, "test_plan": .7}, "judge_score": .9, "judge_confidence": .8, "verifier_pass": True},
        {"row_id": "review", "rubric": {"correctness": .9, "grounding": .8, "minimality": .8, "safety": .9, "style": .7, "test_plan": .7}, "judge_score": .9, "judge_confidence": .95, "verifier_pass": False},
    ]
    card = calibration_card(rows)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
