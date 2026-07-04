from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from rubric_judge_calibrator import calibrate_judge_row, calibration_card, rubric_score


def test_rubric_score_tracks_missing_dimensions() -> None:
    card = rubric_score({"correctness": 1.0, "grounding": 0.5})
    assert 0.0 < card["score"] < 1.0
    assert "safety" in card["missing_dimensions"]


def test_calibrate_accepts_only_when_judge_and_verifier_agree() -> None:
    row = {"row_id": "r1", "rubric": {"correctness": 1, "grounding": 1, "minimality": 1, "safety": 1, "style": 1, "test_plan": 1}, "judge_score": 0.95, "judge_confidence": 0.9, "verifier_pass": True}
    card = calibrate_judge_row(row)
    assert card["risk_route"] == "ACCEPT_VERIFIED"
    assert card["verifier_disagreement"] is False


def test_high_confidence_disagreement_routes_manual_review() -> None:
    row = {"row_id": "r2", "rubric": {"correctness": 1, "grounding": 1, "minimality": 1, "safety": 1, "style": 1, "test_plan": 1}, "judge_score": 0.95, "judge_confidence": 0.95, "verifier_pass": False}
    card = calibrate_judge_row(row)
    assert card["risk_route"] == "MANUAL_REVIEW"
    assert "high_confidence_judge_verifier_disagreement" in card["reasons"]
    assert card["calibrated_confidence"] < card["judge_confidence"]


def test_leak_or_authority_risk_quarantines_even_if_scores_high() -> None:
    row = {"row_id": "r3", "rubric": {"correctness": 1, "grounding": 1, "minimality": 1, "safety": 1, "style": 1, "test_plan": 1}, "judge_score": 1.0, "judge_confidence": 1.0, "verifier_pass": True, "internal_token_leak": True}
    card = calibrate_judge_row(row)
    assert card["risk_route"] == "QUARANTINE"
    assert card["calibrated_confidence"] == 0.0


def test_calibration_card_counts_routes_and_blocks_high_conf_disagreement() -> None:
    rows = [
        {"row_id": "ok", "rubric": {"correctness": 1, "grounding": 1, "minimality": 1, "safety": 1, "style": 1, "test_plan": 1}, "judge_score": .9, "judge_confidence": .9, "verifier_pass": True},
        {"row_id": "bad", "rubric": {"correctness": 1, "grounding": 1, "minimality": 1, "safety": 1, "style": 1, "test_plan": 1}, "judge_score": .9, "judge_confidence": .95, "verifier_pass": False},
    ]
    card = calibration_card(rows)
    assert card["route_counts"]["ACCEPT_VERIFIED"] == 1
    assert card["route_counts"]["MANUAL_REVIEW"] == 1
    assert card["high_confidence_disagreement_rows"] == 1
    assert card["passed"] is False
