from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence


AUTHORITY_CLOSED = {
    "model_execution": False,
    "training": False,
    "runtime": False,
    "source_body_emission": False,
    "decoder_ce": False,
    "denoise_ce": False,
    "scoring_authorized": False,
    "promotion_ready": False,
}

SAFE_ROUTES = {
    "ACCEPT_CALIBRATED_SHADOW",
    "ABSTAIN_LOW_CONFIDENCE",
    "RETRIEVE_OOD_OR_INSUFFICIENT",
    "REVIEW_HIGH_CONFIDENCE_WRONG",
    "BLOCK_AUTHORITY_OR_LEAK",
}


def _float(row: Mapping[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(row.get(key, default))
    except (TypeError, ValueError):
        return default


def _bool(row: Mapping[str, Any], key: str) -> bool:
    return bool(row.get(key))


def _softmax(values: Sequence[float]) -> list[float]:
    if not values:
        return []
    max_v = max(values)
    exps = [math.exp(v - max_v) for v in values]
    total = sum(exps) or 1.0
    return [v / total for v in exps]


def _entropy(probs: Sequence[float]) -> float:
    if not probs:
        return 0.0
    return -sum(p * math.log(max(p, 1e-12)) for p in probs)


def normalize_prediction(row: Mapping[str, Any]) -> dict[str, Any]:
    logits = row.get("logits")
    labels = row.get("labels")
    if isinstance(logits, Mapping):
        ordered_labels = list(logits.keys())
        ordered_logits = [float(logits[label]) for label in ordered_labels]
    elif isinstance(logits, Sequence) and not isinstance(logits, (str, bytes)):
        ordered_logits = [float(v) for v in logits]
        if isinstance(labels, Sequence) and not isinstance(labels, (str, bytes)):
            ordered_labels = [str(v) for v in labels]
        else:
            ordered_labels = [str(i) for i in range(len(ordered_logits))]
    else:
        confidence = max(0.0, min(1.0, _float(row, "confidence", 0.0)))
        pred = str(row.get("pred") or row.get("prediction") or "")
        target = str(row.get("target") or "")
        return {
            "row_id": str(row.get("row_id") or row.get("id") or ""),
            "pred": pred,
            "target": target,
            "correct": bool(row.get("correct", pred == target and bool(pred))),
            "confidence": confidence,
            "margin": max(0.0, min(1.0, _float(row, "margin", 0.0))),
            "entropy": max(0.0, _float(row, "entropy", 0.0)),
            "ood_score": max(0.0, min(1.0, _float(row, "ood_score", 0.0))),
            "evidence_sufficient": _bool(row, "evidence_sufficient"),
            "authority_true": _bool(row, "authority_true") or any(value is True for value in (row.get("authority") if isinstance(row.get("authority"), dict) else {}).values()),
            "internal_leak": _bool(row, "internal_leak") or _bool(row, "leak_or_locked"),
        }

    probs = _softmax(ordered_logits)
    ranked = sorted(zip(ordered_labels, probs), key=lambda item: item[1], reverse=True)
    pred, top1 = ranked[0] if ranked else ("", 0.0)
    top2 = ranked[1][1] if len(ranked) > 1 else 0.0
    target = str(row.get("target") or row.get("gold") or "")
    max_entropy = math.log(max(len(probs), 2))
    normalized_entropy = _entropy(probs) / max_entropy if max_entropy else 0.0
    return {
        "row_id": str(row.get("row_id") or row.get("id") or ""),
        "pred": pred,
        "target": target,
        "correct": pred == target and bool(target),
        "confidence": top1,
        "margin": max(0.0, top1 - top2),
        "entropy": normalized_entropy,
        "ood_score": max(0.0, min(1.0, _float(row, "ood_score", normalized_entropy))),
        "evidence_sufficient": _bool(row, "evidence_sufficient"),
        "authority_true": _bool(row, "authority_true") or any(value is True for value in (row.get("authority") if isinstance(row.get("authority"), dict) else {}).values()),
        "internal_leak": _bool(row, "internal_leak") or _bool(row, "leak_or_locked"),
    }


def confidence_decision(row: Mapping[str, Any]) -> dict[str, Any]:
    p = normalize_prediction(row)
    reasons: list[str] = []
    high_confidence_wrong = p["confidence"] >= 0.80 and not p["correct"]
    calibrated_shadow_accept = (
        p["correct"]
        and p["confidence"] >= 0.70
        and p["margin"] >= 0.15
        and p["entropy"] <= 0.55
        and p["ood_score"] < 0.55
        and p["evidence_sufficient"]
    )

    if p["authority_true"]:
        reasons.append("authority_true")
    if p["internal_leak"]:
        reasons.append("internal_leak")
    if high_confidence_wrong:
        reasons.append("high_confidence_wrong")
    if p["confidence"] < 0.50:
        reasons.append("confidence_low")
    if p["margin"] < 0.10:
        reasons.append("margin_low")
    if p["entropy"] > 0.70:
        reasons.append("entropy_high")
    if p["ood_score"] >= 0.55:
        reasons.append("ood_score_high")
    if not p["evidence_sufficient"]:
        reasons.append("evidence_insufficient")

    if p["authority_true"] or p["internal_leak"]:
        route = "BLOCK_AUTHORITY_OR_LEAK"
    elif high_confidence_wrong:
        route = "REVIEW_HIGH_CONFIDENCE_WRONG"
    elif p["ood_score"] >= 0.55 or not p["evidence_sufficient"]:
        route = "RETRIEVE_OOD_OR_INSUFFICIENT"
    elif p["confidence"] < 0.50 or p["margin"] < 0.10 or p["entropy"] > 0.70:
        route = "ABSTAIN_LOW_CONFIDENCE"
    elif calibrated_shadow_accept:
        route = "ACCEPT_CALIBRATED_SHADOW"
    else:
        route = "ABSTAIN_LOW_CONFIDENCE"

    return {
        "row_id": p["row_id"],
        "route": route,
        "safe_route": route in SAFE_ROUTES,
        "high_confidence_wrong": high_confidence_wrong,
        "calibrated_shadow_accept": route == "ACCEPT_CALIBRATED_SHADOW",
        "confidence": round(p["confidence"], 6),
        "margin": round(p["margin"], 6),
        "entropy": round(p["entropy"], 6),
        "ood_score": round(p["ood_score"], 6),
        "pred": p["pred"],
        "target": p["target"],
        "correct": p["correct"],
        "reasons": sorted(set(reasons)),
        "model_execution_authorized": False,
        "decoder_ce_authorized": False,
        "training_authorized": False,
        "authority": AUTHORITY_CLOSED,
    }


def calibration_card(rows: list[Mapping[str, Any]], bins: int = 10) -> dict[str, Any]:
    decisions = [confidence_decision(row) for row in rows]
    if not decisions:
        brier = 0.0
        ece = 0.0
    else:
        brier = sum((d["confidence"] - (1.0 if d["correct"] else 0.0)) ** 2 for d in decisions) / len(decisions)
        ece = 0.0
        for idx in range(bins):
            lo = idx / bins
            hi = (idx + 1) / bins
            bucket = [d for d in decisions if (lo <= d["confidence"] < hi) or (idx == bins - 1 and d["confidence"] == 1.0)]
            if not bucket:
                continue
            acc = sum(1 for d in bucket if d["correct"]) / len(bucket)
            conf = sum(d["confidence"] for d in bucket) / len(bucket)
            ece += (len(bucket) / len(decisions)) * abs(acc - conf)
    route_counts: dict[str, int] = {}
    for decision in decisions:
        route_counts[decision["route"]] = route_counts.get(decision["route"], 0) + 1
    unsafe = [d for d in decisions if not d["safe_route"] or d["model_execution_authorized"] or d["decoder_ce_authorized"] or d["training_authorized"]]
    return {
        "rows": len(decisions),
        "brier": round(brier, 6),
        "ece": round(ece, 6),
        "route_counts": dict(sorted(route_counts.items())),
        "high_confidence_wrong_rows": sum(1 for d in decisions if d["high_confidence_wrong"]),
        "calibrated_shadow_accept_rows": sum(1 for d in decisions if d["calibrated_shadow_accept"]),
        "unsafe_decisions": len(unsafe),
        "decisions": decisions,
        "authority": AUTHORITY_CLOSED,
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="No-execution confidence/OOD head calibration contract.")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rows = read_jsonl(args.input) if args.input else [
        {"row_id": "ok", "logits": {"SAFE": 3.0, "RETRIEVE": 0.2}, "target": "SAFE", "evidence_sufficient": True, "ood_score": 0.1},
        {"row_id": "wrong", "logits": {"SAFE": 3.0, "RETRIEVE": 0.2}, "target": "RETRIEVE", "evidence_sufficient": True, "ood_score": 0.1},
    ]
    card = calibration_card(rows)
    text = json.dumps(card, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
