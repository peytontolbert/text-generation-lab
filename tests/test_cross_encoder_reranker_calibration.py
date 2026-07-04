from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from cross_encoder_reranker_calibration import calibrate_pair, calibration_card


def test_relevant_source_pair_scores_above_irrelevant_doc_pair() -> None:
    good = calibrate_pair({
        "row_id": "good",
        "task": "repair pytest auth token expiry failure",
        "evidence": "tests/test_auth.py asserts token expiry and auth.py validates token expiry",
        "source_type": "source",
        "retrieval_score": 0.9,
        "grounding_score": 0.8,
        "path_match": True,
        "label": True,
    })
    bad = calibrate_pair({
        "row_id": "bad",
        "task": "repair pytest auth token expiry failure",
        "evidence": "README installation instructions for unrelated package setup",
        "source_type": "doc",
        "retrieval_score": 0.05,
        "label": False,
    })
    assert good["reranker_probability"] > bad["reranker_probability"]
    assert good["route"] == "KEEP_RETRIEVAL_PAIR"
    assert bad["route"] == "LOW_RELEVANCE_PAIR"


def test_leak_and_locked_markers_block_pair() -> None:
    card = calibrate_pair({
        "row_id": "leak",
        "task": "fix symbol binding",
        "evidence": "expected_answer says clean_state target_body",
        "split": "locked_eval",
        "label": True,
    })
    assert card["route"] == "BLOCK_LEAK_OR_LOCKED"
    assert "leak_marker_present" in card["reasons"]
    assert "locked_eval_or_hidden_marker" in card["reasons"]


def test_high_confidence_wrong_routes_calibration_review() -> None:
    card = calibrate_pair({
        "row_id": "wrong",
        "task": "auth token auth token auth token",
        "evidence": "auth token auth token auth token auth token",
        "source_type": "source",
        "retrieval_score": 1.0,
        "grounding_score": 1.0,
        "path_match": True,
        "label": False,
    })
    assert card["reranker_probability"] >= 0.85
    assert card["route"] == "CALIBRATION_REVIEW"
    assert "high_confidence_wrong" in card["reasons"]


def test_calibration_card_reports_metrics_and_closed_authority() -> None:
    card = calibration_card([
        {"row_id": "good", "task": "fix import error", "evidence": "ImportError in app.py", "source_type": "error", "retrieval_score": 1.0, "label": True},
        {"row_id": "bad", "task": "fix import error", "evidence": "unrelated docs", "source_type": "doc", "label": False},
    ])
    assert card["rows"] == 2
    assert card["labeled_rows"] == 2
    assert card["brier"] is not None
    assert card["ece"] is not None
    assert card["authority"]["training"] is False
