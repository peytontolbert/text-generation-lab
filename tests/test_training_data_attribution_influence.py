from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from training_data_attribution_influence import attribution_card, influence_row


def test_helpful_neighbor_has_positive_influence() -> None:
    card = influence_row(
        {"row_id": "eval", "task": "fix auth token expiry", "task_tags": ["auth", "pytest"], "label": "FIX_AUTH"},
        {"row_id": "train", "task": "repair auth token expiry pytest", "task_tags": ["auth", "pytest"], "label": "FIX_AUTH"},
    )
    assert card["influence_type"] == "helpful_neighbor"
    assert card["helpful_score"] > card["harmful_score"]


def test_conflicting_label_near_neighbor_is_harmful() -> None:
    card = influence_row(
        {"row_id": "eval", "task": "fix auth token expiry", "task_tags": ["auth", "pytest"], "label": "FIX_AUTH"},
        {"row_id": "bad", "task": "fix auth token expiry", "task_tags": ["auth", "pytest"], "label": "CHANGE_DOCS", "label_issue_score": 0.8},
    )
    assert card["influence_type"] == "harmful_conflicting"
    assert card["conflicting_label"] is True


def test_missing_neighborhood_recommends_generate_neighbors() -> None:
    card = attribution_card(
        [{"row_id": "eval", "task": "fix auth token expiry", "task_tags": ["auth"], "label": "FIX_AUTH"}],
        [{"row_id": "unrelated", "task": "update CSS theme", "task_tags": ["frontend"], "label": "STYLE"}],
    )
    assert card["eval_cards"][0]["recommendation"] == "generate_or_retrieve_neighbors"


def test_attribution_card_routes_harmful_conflicts_for_review() -> None:
    card = attribution_card(
        [{"row_id": "eval", "task": "fix auth token expiry", "task_tags": ["auth", "pytest"], "label": "FIX_AUTH"}],
        [
            {"row_id": "good", "task": "repair auth token expiry pytest", "task_tags": ["auth", "pytest"], "label": "FIX_AUTH"},
            {"row_id": "bad", "task": "repair auth token expiry pytest", "task_tags": ["auth", "pytest"], "label": "CHANGE_DOCS", "label_issue_score": 0.8},
        ],
    )
    eval_card = card["eval_cards"][0]
    assert eval_card["recommendation"] == "review_harmful_conflicts"
    assert eval_card["top_harmful_candidates"][0]["train_id"] == "bad"
    assert card["authority"]["training"] is False
