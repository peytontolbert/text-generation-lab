from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from dataset_cartography_active_learning import active_learning_batch, cartography_card, example_dynamics_card, forgetting_events


def test_forgetting_events_count_true_to_false_transitions() -> None:
    assert forgetting_events([False, True, True, False, True, False]) == 2


def test_noisy_label_routes_review() -> None:
    card = example_dynamics_card({
        "row_id": "noisy",
        "confidence_history": [0.1, 0.12],
        "loss_history": [2.0, 2.1],
        "correct_history": [False, False],
        "label_issue_score": 0.8,
    })
    assert card["bucket"] == "REVIEW_OR_QUARANTINE_NOISY"
    assert card["recommended_action"] == "review_label_or_source"


def test_easy_duplicate_routes_downsample() -> None:
    card = example_dynamics_card({
        "row_id": "easy_dup",
        "confidence_history": [0.9, 0.92],
        "loss_history": [0.1, 0.09],
        "correct_history": [True, True],
        "duplicate_score": 0.9,
    })
    assert card["bucket"] == "DOWNSAMPLE_EASY_REDUNDANT"


def test_ambiguous_and_hard_rows_are_selected_for_active_learning() -> None:
    rows = [
        {"row_id": "easy", "confidence_history": [0.95, 0.96], "loss_history": [0.05, 0.04], "correct_history": [True, True], "duplicate_score": 0.9},
        {"row_id": "ambig", "confidence_history": [0.2, 0.8, 0.4], "loss_history": [1.5, 0.3, 1.1], "correct_history": [False, True, False]},
        {"row_id": "hard", "confidence_history": [0.3, 0.35], "loss_history": [1.6, 1.4], "correct_history": [False, False]},
    ]
    card = cartography_card(rows)
    batch = active_learning_batch(rows, budget=2)
    assert card["neighbor_generation_rows"] >= 2
    assert "easy" not in batch["selected_row_ids"]
    assert set(batch["selected_row_ids"]) == {"ambig", "hard"}
    assert batch["authority"]["training"] is False
