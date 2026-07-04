from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable, Mapping


AUTHORITY_CLOSED = {
    "model_execution": False,
    "training": False,
    "runtime": False,
    "source_body_emission": False,
    "scoring_authorized": False,
}

LEAK_MARKERS = ("target_body", "oracle", "expected_answer", "clean_state", "decoder_text", "gold_label")
LOCKED_MARKERS = ("locked_eval", "hidden_eval", "promotion_only")
TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+")


def stable_hash(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()[:16]


def tokens(text: str) -> set[str]:
    return {tok.lower() for tok in TOKEN_RE.findall(text)}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def pair_features(row: Mapping[str, Any]) -> dict[str, Any]:
    task = str(row.get("task") or row.get("query") or row.get("prompt") or "")
    evidence = str(row.get("evidence") or row.get("text") or row.get("span") or row.get("content") or "")
    task_tokens = tokens(task)
    evidence_tokens = tokens(evidence)
    overlap = task_tokens & evidence_tokens
    union = task_tokens | evidence_tokens
    source_type = str(row.get("source_type") or row.get("type") or "source")
    retrieval_score = _safe_float(row.get("retrieval_score", row.get("bm25_score", row.get("dense_score", 0.0))))
    grounding_score = _safe_float(row.get("grounding_score", row.get("source_grounding_score", 0.0)))
    freshness_score = _safe_float(row.get("freshness_score", 0.0))
    path_match = bool(row.get("path_match") or row.get("symbol_match") or row.get("test_match"))
    exact_phrase = bool(task.strip() and evidence.strip() and task.strip().lower() in evidence.lower())
    leak_text = " ".join([task, evidence, json.dumps(row.get("metadata", {}), sort_keys=True)]).lower()
    leak_flags = sorted(marker for marker in LEAK_MARKERS if marker in leak_text)
    locked_flags = sorted(marker for marker in LOCKED_MARKERS if marker in leak_text or str(row.get("split", "")).lower().startswith("locked"))
    return {
        "task_token_count": len(task_tokens),
        "evidence_token_count": len(evidence_tokens),
        "overlap_count": len(overlap),
        "jaccard": len(overlap) / max(1, len(union)),
        "retrieval_score": retrieval_score,
        "grounding_score": grounding_score,
        "freshness_score": freshness_score,
        "source_type": source_type,
        "path_or_symbol_match": path_match,
        "exact_phrase_match": exact_phrase,
        "leak_flags": leak_flags,
        "locked_flags": locked_flags,
    }


def reranker_logit(features: Mapping[str, Any]) -> float:
    source_bonus = {
        "source": 0.35,
        "test": 0.30,
        "error": 0.25,
        "symbol": 0.25,
        "patch_context": 0.20,
        "doc": -0.05,
        "memory": -0.10,
    }.get(str(features.get("source_type")), 0.0)
    return (
        -1.15
        + 3.0 * float(features["jaccard"])
        + 0.75 * min(1.0, float(features["retrieval_score"]))
        + 0.85 * min(1.0, float(features["grounding_score"]))
        + 0.25 * min(1.0, float(features["freshness_score"]))
        + (0.55 if features["path_or_symbol_match"] else 0.0)
        + (0.45 if features["exact_phrase_match"] else 0.0)
        + source_bonus
    )


def calibrate_pair(row: Mapping[str, Any], *, positive_threshold: float = 0.5) -> dict[str, Any]:
    row_id = str(row.get("row_id") or row.get("pair_id") or row.get("id") or stable_hash(json.dumps(row, sort_keys=True)))
    features = pair_features(row)
    logit = reranker_logit(features)
    probability = sigmoid(logit)
    label = row.get("label", row.get("relevant", row.get("is_relevant")))
    label_bool = bool(label) if label is not None else None
    pred_bool = probability >= positive_threshold
    blocked = bool(features["leak_flags"] or features["locked_flags"])
    reasons = []
    if features["leak_flags"]:
        reasons.append("leak_marker_present")
    if features["locked_flags"]:
        reasons.append("locked_eval_or_hidden_marker")
    if label_bool is not None and pred_bool != label_bool and probability >= 0.85:
        reasons.append("high_confidence_wrong")
    route = "BLOCK_LEAK_OR_LOCKED" if blocked else ("KEEP_RETRIEVAL_PAIR" if pred_bool else "LOW_RELEVANCE_PAIR")
    if "high_confidence_wrong" in reasons:
        route = "CALIBRATION_REVIEW"
    return {
        "row_id": row_id,
        "features": features,
        "reranker_logit": round(logit, 6),
        "reranker_probability": round(probability, 6),
        "predicted_relevant": pred_bool,
        "label_relevant": label_bool,
        "correct": (pred_bool == label_bool) if label_bool is not None else None,
        "route": route,
        "reasons": reasons,
        "authority": AUTHORITY_CLOSED,
    }


def brier_score(cards: Iterable[Mapping[str, Any]]) -> float | None:
    vals = []
    for card in cards:
        if card.get("label_relevant") is None:
            continue
        p = float(card["reranker_probability"])
        y = 1.0 if card["label_relevant"] else 0.0
        vals.append((p - y) ** 2)
    if not vals:
        return None
    return sum(vals) / len(vals)


def expected_calibration_error(cards: Iterable[Mapping[str, Any]], *, bins: int = 5) -> float | None:
    buckets: list[list[Mapping[str, Any]]] = [[] for _ in range(bins)]
    labeled = 0
    for card in cards:
        if card.get("label_relevant") is None:
            continue
        labeled += 1
        idx = min(bins - 1, int(float(card["reranker_probability"]) * bins))
        buckets[idx].append(card)
    if labeled == 0:
        return None
    ece = 0.0
    for bucket in buckets:
        if not bucket:
            continue
        conf = sum(float(c["reranker_probability"]) for c in bucket) / len(bucket)
        acc = sum(float(bool(c["correct"])) for c in bucket) / len(bucket)
        ece += (len(bucket) / labeled) * abs(conf - acc)
    return ece


def calibration_card(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    pair_cards = [calibrate_pair(row) for row in rows]
    routes = Counter(card["route"] for card in pair_cards)
    reasons = Counter(reason for card in pair_cards for reason in card["reasons"])
    labeled = [card for card in pair_cards if card.get("label_relevant") is not None]
    exact = None
    if labeled:
        exact = sum(1 for card in labeled if card["correct"]) / len(labeled)
    probs = [float(card["reranker_probability"]) for card in pair_cards]
    return {
        "rows": len(pair_cards),
        "labeled_rows": len(labeled),
        "exact": exact,
        "brier": brier_score(pair_cards),
        "ece": expected_calibration_error(pair_cards),
        "mean_probability": sum(probs) / max(1, len(probs)),
        "route_counts": dict(sorted(routes.items())),
        "reason_counts": dict(sorted(reasons.items())),
        "blocked_rows": routes.get("BLOCK_LEAK_OR_LOCKED", 0),
        "high_confidence_wrong_rows": reasons.get("high_confidence_wrong", 0),
        "pair_cards": pair_cards,
        "authority": AUTHORITY_CLOSED,
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Deterministic no-authority cross-encoder reranker calibration contract.")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rows = read_jsonl(args.input) if args.input else [
        {"row_id": "good", "task": "fix auth token validation", "evidence": "auth.py validates token expiry and issuer", "source_type": "source", "retrieval_score": 0.9, "grounding_score": 0.8, "path_match": True, "label": True},
        {"row_id": "bad", "task": "fix auth token validation", "evidence": "README discusses installation", "source_type": "doc", "retrieval_score": 0.1, "label": False},
    ]
    card = calibration_card(rows)
    text = json.dumps(card, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
