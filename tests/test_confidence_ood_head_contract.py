from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from confidence_ood_head_contract import calibration_card, confidence_decision, normalize_prediction


def test_logits_normalize_to_confidence_margin_entropy() -> None:
    pred = normalize_prediction({
        "row_id": "ok",
        "logits": {"SAFE": 3.0, "RETRIEVE": 0.0, "UNSAFE": -1.0},
        "target": "SAFE",
        "evidence_sufficient": True,
    })
    assert pred["pred"] == "SAFE"
    assert pred["correct"] is True
    assert pred["confidence"] > 0.90
    assert pred["margin"] > 0.80
    assert 0.0 <= pred["entropy"] <= 1.0


def test_all_green_correct_prediction_is_shadow_accept_only() -> None:
    decision = confidence_decision({
        "row_id": "accept",
        "logits": {"SAFE": 3.0, "RETRIEVE": 0.1, "UNSAFE": -0.4},
        "target": "SAFE",
        "evidence_sufficient": True,
        "ood_score": 0.1,
    })
    assert decision["route"] == "ACCEPT_CALIBRATED_SHADOW"
    assert decision["calibrated_shadow_accept"] is True
    assert decision["model_execution_authorized"] is False
    assert decision["decoder_ce_authorized"] is False
    assert decision["training_authorized"] is False


def test_high_confidence_wrong_routes_review() -> None:
    decision = confidence_decision({
        "row_id": "wrong",
        "logits": {"SAFE": 3.0, "RETRIEVE": 0.1, "UNSAFE": -0.4},
        "target": "RETRIEVE",
        "evidence_sufficient": True,
        "ood_score": 0.1,
    })
    assert decision["route"] == "REVIEW_HIGH_CONFIDENCE_WRONG"
    assert decision["high_confidence_wrong"] is True
    assert "high_confidence_wrong" in decision["reasons"]


def test_ood_or_missing_evidence_routes_retrieve() -> None:
    decision = confidence_decision({
        "row_id": "ood",
        "confidence": 0.6,
        "margin": 0.2,
        "entropy": 0.4,
        "ood_score": 0.8,
        "pred": "SAFE",
        "target": "SAFE",
        "correct": True,
        "evidence_sufficient": False,
    })
    assert decision["route"] == "RETRIEVE_OOD_OR_INSUFFICIENT"
    assert "ood_score_high" in decision["reasons"]
    assert "evidence_insufficient" in decision["reasons"]


def test_authority_or_leak_blocks_accept() -> None:
    decision = confidence_decision({
        "row_id": "blocked",
        "confidence": 0.95,
        "margin": 0.5,
        "entropy": 0.1,
        "ood_score": 0.0,
        "pred": "SAFE",
        "target": "SAFE",
        "correct": True,
        "evidence_sufficient": True,
        "authority": {"runtime": True},
    })
    assert decision["route"] == "BLOCK_AUTHORITY_OR_LEAK"
    assert decision["calibrated_shadow_accept"] is False


def test_calibration_card_reports_brier_ece_and_keeps_authority_closed() -> None:
    card = calibration_card([
        {"row_id": "ok", "logits": {"SAFE": 3.0, "RETRIEVE": 0.1}, "target": "SAFE", "evidence_sufficient": True, "ood_score": 0.1},
        {"row_id": "wrong", "logits": {"SAFE": 3.0, "RETRIEVE": 0.1}, "target": "RETRIEVE", "evidence_sufficient": True, "ood_score": 0.1},
    ])
    assert card["rows"] == 2
    assert card["brier"] >= 0.0
    assert card["ece"] >= 0.0
    assert card["high_confidence_wrong_rows"] == 1
    assert card["unsafe_decisions"] == 0
    assert card["authority"]["training"] is False
