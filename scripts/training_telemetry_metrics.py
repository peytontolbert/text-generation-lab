from __future__ import annotations

import math
from typing import Any, Iterable


def softmax(logits: Iterable[float]) -> list[float]:
    values = [float(x) for x in logits]
    if not values:
        return []
    top = max(values)
    exps = [math.exp(x - top) for x in values]
    total = sum(exps) or 1.0
    return [x / total for x in exps]


def entropy(probs: Iterable[float]) -> float:
    return float(-sum(p * math.log(max(p, 1e-12)) for p in probs))


def margin_confidence_entropy(logits: Iterable[float], *, label: int | None = None) -> dict[str, Any]:
    probs = softmax(logits)
    if not probs:
        return {"predicted_index": None, "confidence": 0.0, "margin": 0.0, "entropy": 0.0, "correct": None}
    ranked = sorted(enumerate(probs), key=lambda item: item[1], reverse=True)
    pred, conf = ranked[0]
    second = ranked[1][1] if len(ranked) > 1 else 0.0
    return {
        "predicted_index": pred,
        "confidence": float(conf),
        "margin": float(conf - second),
        "entropy": entropy(probs),
        "correct": (pred == label) if label is not None else None,
    }


def row_field_telemetry(row_id: str, field: str, logits: Iterable[float], labels: list[str], gold_label: str | None) -> dict[str, Any]:
    label_index = labels.index(gold_label) if gold_label in labels else None
    card = margin_confidence_entropy(logits, label=label_index)
    predicted = labels[card["predicted_index"]] if card["predicted_index"] is not None and card["predicted_index"] < len(labels) else None
    return {
        "row_id": row_id,
        "field": field,
        "labels": labels,
        "gold_label": gold_label,
        "predicted_label": predicted,
        **card,
    }


def high_confidence_wrong_rows(rows: Iterable[dict[str, Any]], *, confidence_threshold: float = 0.8) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        if row.get("correct") is False and float(row.get("confidence", 0.0)) >= confidence_threshold:
            out.append(row)
    return out


def token_loss_map(row_id: str, token_ids: list[int], token_losses: list[float], *, token_texts: list[str] | None = None) -> dict[str, Any]:
    if len(token_ids) != len(token_losses):
        raise ValueError("token_ids and token_losses must have same length")
    token_texts = token_texts or [str(token_id) for token_id in token_ids]
    if len(token_texts) != len(token_ids):
        raise ValueError("token_texts and token_ids must have same length")
    positions = [
        {"position": index, "token_id": int(token_id), "token_text": token_texts[index], "loss": float(loss)}
        for index, (token_id, loss) in enumerate(zip(token_ids, token_losses))
    ]
    total = sum(float(loss) for loss in token_losses)
    return {
        "row_id": row_id,
        "token_count": len(token_ids),
        "mean_loss": float(total / max(1, len(token_ids))),
        "max_loss": float(max(token_losses) if token_losses else 0.0),
        "positions": positions,
    }


def failure_bucket(row: dict[str, Any]) -> str:
    if row.get("internal_leak"):
        return "internal_leak"
    if row.get("short_output"):
        return "short_output"
    if row.get("repetition"):
        return "repetition"
    if row.get("correct") is False and float(row.get("confidence", 0.0)) >= 0.8:
        return "high_confidence_wrong"
    if row.get("correct") is False:
        return "wrong_low_confidence"
    return "ok"


def summarize_failure_buckets(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    buckets: dict[str, int] = {}
    for row in rows:
        bucket = failure_bucket(row)
        buckets[bucket] = buckets.get(bucket, 0) + 1
    return buckets
