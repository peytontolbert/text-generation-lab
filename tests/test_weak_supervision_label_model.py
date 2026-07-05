from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from weak_supervision_label_model import combine_votes, label_model_card


def test_accepts_consistent_high_quality_votes_shadow_only() -> None:
    row = {
        "row_id": "ok",
        "votes": [
            {"source": "verifier", "label": "CORRECT_PRIOR", "confidence": 0.95},
            {"source": "static_analysis", "label": "CORRECT_PRIOR", "confidence": 0.90},
        ],
    }
    card = combine_votes(row)
    assert card["weak_label"] == "CORRECT_PRIOR"
    assert card["weak_label_route"] == "ACCEPT_WEAK_LABEL_SHADOW"
    assert card["authority"]["training_authorized"] is False


def test_conflicting_close_votes_route_review() -> None:
    row = {
        "row_id": "conflict",
        "votes": [
            {"source": "teacher", "label": "COPY_PRIOR", "confidence": 0.8},
            {"source": "teacher", "label": "RETRIEVE_MORE", "confidence": 0.78},
        ],
    }
    card = combine_votes(row)
    assert card["weak_label_route"] == "HOLD_WEAK_LABEL_REVIEW"
    assert "conflicting_votes" in card["reasons"]
    assert "weak_label_margin_low" in card["reasons"]


def test_contaminated_votes_are_ignored() -> None:
    row = {
        "row_id": "contam",
        "votes": [
            {"source": "verifier", "label": "CORRECT_PRIOR", "confidence": 1.0, "locked_eval_source": True},
            {"source": "heuristic", "label": "ABSTAIN", "confidence": 1.0},
        ],
    }
    card = combine_votes(row)
    assert card["weak_label"] == "ABSTAIN"
    assert card["weak_label_route"] == "ABSTAIN_NO_WEAK_LABEL"
    assert "invalid_or_contaminated_votes" in card["reasons"]


def test_label_model_card_counts_routes() -> None:
    card = label_model_card([
        {"row_id": "ok", "votes": [{"source": "verifier", "label": "A", "confidence": 1.0}]},
        {
            "row_id": "review",
            "votes": [
                {"source": "teacher", "label": "A", "confidence": 0.7},
                {"source": "teacher", "label": "B", "confidence": 0.69},
            ],
        },
        {"row_id": "none", "votes": []},
    ])
    assert card["metrics"]["accepted_shadow_rows"] == 1
    assert card["metrics"]["review_rows"] == 1
    assert card["metrics"]["abstain_rows"] == 1
    assert card["metrics"]["authority_rows"] == 0
