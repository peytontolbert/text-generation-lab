from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from statistics import mean, pstdev
from typing import Any, Iterable, Mapping


AUTHORITY_CLOSED = {
    "model_execution": False,
    "training": False,
    "runtime": False,
    "source_body_emission": False,
    "scoring_authorized": False,
}


def _floats(values: Any) -> list[float]:
    if not isinstance(values, list):
        return []
    out = []
    for value in values:
        try:
            out.append(float(value))
        except (TypeError, ValueError):
            pass
    return out


def _bools(values: Any) -> list[bool]:
    if not isinstance(values, list):
        return []
    return [bool(value) for value in values]


def forgetting_events(correct_history: Iterable[bool]) -> int:
    values = list(correct_history)
    return sum(1 for before, after in zip(values, values[1:]) if before and not after)


def example_dynamics_card(row: Mapping[str, Any]) -> dict[str, Any]:
    row_id = str(row.get("row_id") or row.get("example_id") or row.get("id") or "")
    confidences = _floats(row.get("confidence_history", row.get("confidences", [])))
    losses = _floats(row.get("loss_history", row.get("losses", [])))
    correctness = _bools(row.get("correct_history", row.get("correctness", [])))
    if not confidences and "confidence" in row:
        confidences = [float(row["confidence"])]
    if not losses and "loss" in row:
        losses = [float(row["loss"])]
    confidence_mean = mean(confidences) if confidences else None
    confidence_variability = pstdev(confidences) if len(confidences) > 1 else 0.0
    loss_mean = mean(losses) if losses else None
    loss_variability = pstdev(losses) if len(losses) > 1 else 0.0
    forgets = forgetting_events(correctness)
    final_correct = correctness[-1] if correctness else row.get("correct")
    label_issue_score = float(row.get("label_issue_score", 0.0) or 0.0)
    duplicate_score = float(row.get("duplicate_score", 0.0) or 0.0)
    source_trust = float(row.get("source_trust", 1.0) or 0.0)

    high_loss = loss_mean is not None and loss_mean >= 1.25
    low_conf = confidence_mean is not None and confidence_mean <= 0.45
    high_conf = confidence_mean is not None and confidence_mean >= 0.85
    high_var = confidence_variability >= 0.18 or loss_variability >= 0.35
    likely_noisy = label_issue_score >= 0.5 or (high_loss and not high_var and source_trust < 0.5)
    redundant = high_conf and not high_var and duplicate_score >= 0.7 and bool(final_correct)
    ambiguous = high_var and not likely_noisy
    hard = (high_loss or low_conf or forgets > 0) and not likely_noisy and not redundant

    if likely_noisy:
        bucket = "REVIEW_OR_QUARANTINE_NOISY"
        action = "review_label_or_source"
    elif redundant:
        bucket = "DOWNSAMPLE_EASY_REDUNDANT"
        action = "downsample"
    elif ambiguous:
        bucket = "KEEP_AMBIGUOUS_GENERALIZATION"
        action = "keep_and_add_counterfactual_neighbors"
    elif hard:
        bucket = "UPSAMPLE_HARD_OR_ADD_NEIGHBORS"
        action = "upsample_or_generate_neighbors"
    elif high_conf and bool(final_correct):
        bucket = "EASY_LEARNED"
        action = "keep_low_weight"
    else:
        bucket = "NORMAL_KEEP"
        action = "keep"

    return {
        "row_id": row_id,
        "task_tags": row.get("task_tags", []),
        "confidence_mean": confidence_mean,
        "confidence_variability": confidence_variability,
        "loss_mean": loss_mean,
        "loss_variability": loss_variability,
        "forgetting_events": forgets,
        "final_correct": final_correct,
        "label_issue_score": label_issue_score,
        "duplicate_score": duplicate_score,
        "source_trust": source_trust,
        "bucket": bucket,
        "recommended_action": action,
        "authority": AUTHORITY_CLOSED,
    }


def cartography_card(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    cards = [example_dynamics_card(row) for row in rows]
    buckets = Counter(card["bucket"] for card in cards)
    actions = Counter(card["recommended_action"] for card in cards)
    losses = [card["loss_mean"] for card in cards if card["loss_mean"] is not None]
    confs = [card["confidence_mean"] for card in cards if card["confidence_mean"] is not None]
    return {
        "rows": len(cards),
        "bucket_counts": dict(sorted(buckets.items())),
        "action_counts": dict(sorted(actions.items())),
        "mean_loss": mean(losses) if losses else None,
        "mean_confidence": mean(confs) if confs else None,
        "forgetting_event_rows": sum(1 for card in cards if card["forgetting_events"] > 0),
        "label_review_rows": buckets.get("REVIEW_OR_QUARANTINE_NOISY", 0),
        "downsample_rows": buckets.get("DOWNSAMPLE_EASY_REDUNDANT", 0),
        "neighbor_generation_rows": buckets.get("UPSAMPLE_HARD_OR_ADD_NEIGHBORS", 0) + buckets.get("KEEP_AMBIGUOUS_GENERALIZATION", 0),
        "example_cards": cards,
        "authority": AUTHORITY_CLOSED,
    }


def active_learning_batch(rows: list[Mapping[str, Any]], *, budget: int = 10) -> dict[str, Any]:
    card = cartography_card(rows)
    priority = {
        "REVIEW_OR_QUARANTINE_NOISY": 100,
        "KEEP_AMBIGUOUS_GENERALIZATION": 80,
        "UPSAMPLE_HARD_OR_ADD_NEIGHBORS": 70,
        "NORMAL_KEEP": 20,
        "EASY_LEARNED": 5,
        "DOWNSAMPLE_EASY_REDUNDANT": -10,
    }
    selected = sorted(
        card["example_cards"],
        key=lambda item: (
            priority.get(str(item["bucket"]), 0),
            float(item["forgetting_events"]),
            float(item["confidence_variability"] or 0.0),
            float(item["loss_mean"] or 0.0),
        ),
        reverse=True,
    )[: max(0, budget)]
    return {
        "budget": budget,
        "selected_count": len(selected),
        "selected_row_ids": [item["row_id"] for item in selected],
        "selected_cards": selected,
        "cartography": card,
        "authority": AUTHORITY_CLOSED,
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Deterministic dataset cartography and active-learning sampler contract.")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--budget", type=int, default=10)
    args = parser.parse_args()
    rows = read_jsonl(args.input) if args.input else [
        {"row_id": "easy", "confidence_history": [0.9, 0.95], "loss_history": [0.1, 0.08], "correct_history": [True, True], "duplicate_score": 0.8},
        {"row_id": "ambig", "confidence_history": [0.2, 0.8, 0.4], "loss_history": [1.5, 0.3, 1.1], "correct_history": [False, True, False]},
    ]
    card = active_learning_batch(rows, budget=args.budget)
    text = json.dumps(card, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
