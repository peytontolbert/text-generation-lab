from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

ABSTAIN = "ABSTAIN"
DEFAULT_SOURCE_WEIGHTS = {
    "verifier": 1.0,
    "golden_rule": 0.95,
    "static_analysis": 0.85,
    "rubric_judge": 0.70,
    "teacher": 0.65,
    "retrieval_ranker": 0.55,
    "heuristic": 0.45,
}


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _bool(value: Any) -> bool:
    return value is True or str(value).lower() in {"1", "true", "yes"}


def _votes(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    votes = row.get("votes", row.get("label_votes", []))
    return list(votes) if isinstance(votes, list) else []


def combine_votes(
    row: Mapping[str, Any],
    *,
    source_weights: Mapping[str, float] | None = None,
    min_confidence: float = 0.60,
    min_margin: float = 0.15,
) -> dict[str, Any]:
    weights = dict(DEFAULT_SOURCE_WEIGHTS)
    if source_weights:
        weights.update({str(k): float(v) for k, v in source_weights.items()})
    scores: dict[str, float] = defaultdict(float)
    contributing_votes = []
    invalid_votes = 0
    for vote in _votes(row):
        if not isinstance(vote, Mapping):
            invalid_votes += 1
            continue
        label = str(vote.get("label", "")).strip()
        if not label or label == ABSTAIN:
            continue
        source = str(vote.get("source", "heuristic"))
        if _bool(vote.get("leak_or_contaminated")) or _bool(vote.get("locked_eval_source")):
            invalid_votes += 1
            continue
        confidence = max(0.0, min(1.0, _float(vote.get("confidence", 1.0), 1.0)))
        weight = max(0.0, weights.get(source, weights["heuristic"]))
        score = confidence * weight
        if score <= 0.0:
            continue
        scores[label] += score
        contributing_votes.append({"label": label, "source": source, "score": round(score, 6)})
    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    top_label = ordered[0][0] if ordered else ABSTAIN
    top_score = ordered[0][1] if ordered else 0.0
    second_score = ordered[1][1] if len(ordered) > 1 else 0.0
    total = sum(scores.values())
    confidence = top_score / total if total else 0.0
    margin = (top_score - second_score) / total if total else 0.0
    reasons = []
    if not contributing_votes:
        reasons.append("no_valid_votes")
    if len(scores) > 1:
        reasons.append("conflicting_votes")
    if invalid_votes:
        reasons.append("invalid_or_contaminated_votes")
    if confidence < min_confidence:
        reasons.append("weak_label_confidence_low")
    if margin < min_margin:
        reasons.append("weak_label_margin_low")
    if top_label == ABSTAIN:
        route = "ABSTAIN_NO_WEAK_LABEL"
    elif confidence < min_confidence or margin < min_margin:
        route = "HOLD_WEAK_LABEL_REVIEW"
    else:
        route = "ACCEPT_WEAK_LABEL_SHADOW"
    return {
        "row_id": str(row.get("row_id", row.get("id", "unknown_row"))),
        "weak_label": top_label,
        "weak_label_confidence": round(confidence, 6),
        "weak_label_margin": round(margin, 6),
        "weak_label_route": route,
        "label_scores": {label: round(score, 6) for label, score in ordered},
        "contributing_votes": contributing_votes,
        "invalid_vote_count": invalid_votes,
        "reasons": reasons,
        "authority": {
            "training_authorized": False,
            "promotion_ready": False,
            "decoder_ce_authorized": False,
            "runtime_authorized": False,
        },
    }


def label_model_card(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    records = [combine_votes(row) for row in rows]
    routes = Counter(record["weak_label_route"] for record in records)
    labels = Counter(record["weak_label"] for record in records)
    return {
        "rows": len(rows),
        "records": records,
        "metrics": {
            "rows": len(rows),
            "accepted_shadow_rows": routes.get("ACCEPT_WEAK_LABEL_SHADOW", 0),
            "review_rows": routes.get("HOLD_WEAK_LABEL_REVIEW", 0),
            "abstain_rows": routes.get("ABSTAIN_NO_WEAK_LABEL", 0),
            "route_counts": dict(routes),
            "label_counts": dict(labels),
            "authority_rows": 0,
        },
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="No-authority weak supervision label model for dataset judge rows.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    card = label_model_card(read_jsonl(args.manifest))
    text = json.dumps(card, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
