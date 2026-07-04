from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path
from typing import Any

DEFAULT_SINGLE_MODALITY_CEILING = 0.80
DEFAULT_REQUIRED_LIFT = 0.05


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def audit_ablation_card(card: dict[str, Any], *, single_modality_ceiling: float = DEFAULT_SINGLE_MODALITY_CEILING, required_lift: float = DEFAULT_REQUIRED_LIFT) -> dict[str, Any]:
    objective = str(card.get("objective") or card.get("objective_family") or card.get("name") or "")
    split = str(card.get("split") or "all")
    full_score = _float(card.get("full_score", card.get("joint_exact", card.get("exact", 0.0))))
    majority_score = _float(card.get("majority_baseline", card.get("majority_exact", 0.0)))
    modality_scores_raw = card.get("modality_scores") if isinstance(card.get("modality_scores"), dict) else {}
    dropout_scores_raw = card.get("dropout_scores") if isinstance(card.get("dropout_scores"), dict) else {}
    combo_scores_raw = card.get("combo_scores") if isinstance(card.get("combo_scores"), dict) else {}
    modality_scores = {str(k): _float(v) for k, v in modality_scores_raw.items()}
    dropout_scores = {str(k): _float(v) for k, v in dropout_scores_raw.items()}
    combo_scores = {str(k): _float(v) for k, v in combo_scores_raw.items()}
    strongest_modality = max(modality_scores.items(), key=lambda kv: kv[1], default=(None, 0.0))
    strongest_combo = max(combo_scores.items(), key=lambda kv: kv[1], default=(None, 0.0))
    weakest_dropout = min(dropout_scores.items(), key=lambda kv: kv[1], default=(None, full_score))
    lift_over_strongest = full_score - strongest_modality[1]
    lift_over_majority = full_score - majority_score
    failures: list[str] = []
    if not modality_scores:
        failures.append("missing_modality_scores")
    if strongest_modality[1] >= single_modality_ceiling:
        failures.append("single_modality_shortcut")
    if lift_over_strongest < required_lift:
        failures.append("insufficient_multimodal_lift")
    if strongest_combo[1] >= single_modality_ceiling and full_score - strongest_combo[1] < required_lift:
        failures.append("combo_shortcut_or_no_lift")
    if dropout_scores and full_score - weakest_dropout[1] < required_lift:
        failures.append("dropout_not_sensitive")
    if majority_score >= single_modality_ceiling:
        failures.append("majority_baseline_too_high")
    return {
        "objective": objective,
        "split": split,
        "passed": not failures,
        "failures": failures,
        "full_score": full_score,
        "majority_score": majority_score,
        "strongest_modality": {"name": strongest_modality[0], "score": strongest_modality[1]},
        "strongest_combo": {"name": strongest_combo[0], "score": strongest_combo[1]},
        "weakest_dropout": {"name": weakest_dropout[0], "score": weakest_dropout[1]},
        "lift_over_strongest_modality": round(lift_over_strongest, 6),
        "lift_over_majority": round(lift_over_majority, 6),
        "single_modality_ceiling": single_modality_ceiling,
        "required_lift": required_lift,
    }


def audit_ablation_cards(cards: list[dict[str, Any]], *, single_modality_ceiling: float = DEFAULT_SINGLE_MODALITY_CEILING, required_lift: float = DEFAULT_REQUIRED_LIFT) -> dict[str, Any]:
    row_cards = [audit_ablation_card(card, single_modality_ceiling=single_modality_ceiling, required_lift=required_lift) for card in cards]
    failure_counts: dict[str, int] = collections.Counter(failure for card in row_cards for failure in card["failures"])
    return {
        "passed": all(card["passed"] for card in row_cards),
        "cards": len(cards),
        "passing_cards": sum(1 for card in row_cards if card["passed"]),
        "failing_cards": sum(1 for card in row_cards if not card["passed"]),
        "failure_counts": dict(sorted(failure_counts.items())),
        "row_cards": row_cards,
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit modality dropout/ablation cards for shortcut dominance and multimodal lift.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--single-modality-ceiling", type=float, default=DEFAULT_SINGLE_MODALITY_CEILING)
    parser.add_argument("--required-lift", type=float, default=DEFAULT_REQUIRED_LIFT)
    args = parser.parse_args()
    card = audit_ablation_cards(read_jsonl(args.manifest), single_modality_ceiling=args.single_modality_ceiling, required_lift=args.required_lift)
    text = json.dumps(card, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
