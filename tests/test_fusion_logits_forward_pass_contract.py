from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from fusion_logits_forward_pass_contract import fusion_card, fusion_decision


def test_all_green_only_allows_bounded_decoder_shadow_not_ce() -> None:
    decision = fusion_decision({
        "row_id": "ok",
        "structured_confidence": 0.92,
        "retrieval_confidence": 0.9,
        "retrieval_coverage": 0.88,
        "verifier_pass": True,
        "verifier_confidence": 0.8,
        "decoder_confidence": 0.8,
        "decoder_budget_ok": True,
        "decoder_schema_ok": True,
        "ood_score": 0.1,
    })
    assert decision["route"] == "ALLOW_BOUNDED_DECODER_SHADOW"
    assert decision["decoder_shadow_allowed"] is True
    assert decision["decoder_ce_authorized"] is False
    assert decision["model_execution_authorized"] is False


def test_low_retrieval_routes_retrieve_more() -> None:
    decision = fusion_decision({
        "row_id": "low_retrieval",
        "structured_confidence": 0.9,
        "retrieval_confidence": 0.2,
        "retrieval_coverage": 0.3,
        "verifier_pass": True,
        "decoder_budget_ok": True,
        "decoder_schema_ok": True,
    })
    assert decision["route"] == "RETRIEVE_MORE"
    assert "retrieval_coverage_low" in decision["reasons"]


def test_leak_or_authority_routes_abstain() -> None:
    decision = fusion_decision({
        "row_id": "bad",
        "authority": {"decoder_ce": True},
        "internal_leak": True,
        "structured_confidence": 1.0,
        "retrieval_confidence": 1.0,
        "retrieval_coverage": 1.0,
    })
    assert decision["route"] == "ABSTAIN_UNSAFE"
    assert decision["decoder_shadow_allowed"] is False


def test_high_ood_or_high_confidence_wrong_routes_repair() -> None:
    decision = fusion_decision({
        "row_id": "ood",
        "structured_confidence": 0.95,
        "retrieval_confidence": 0.95,
        "retrieval_coverage": 0.95,
        "ood_score": 0.9,
        "decoder_budget_ok": True,
        "decoder_schema_ok": True,
    })
    assert decision["route"] == "REPAIR_STRUCTURED"
    assert "ood_score_high" in decision["reasons"]


def test_fusion_card_counts_routes_and_keeps_authority_closed() -> None:
    card = fusion_card([
        {"row_id": "ok", "structured_confidence": .9, "retrieval_confidence": .9, "retrieval_coverage": .9, "verifier_pass": True, "verifier_confidence": .8, "decoder_confidence": .8, "decoder_budget_ok": True, "decoder_schema_ok": True},
        {"row_id": "missing", "structured_confidence": .8, "retrieval_confidence": .2, "retrieval_coverage": .2},
    ])
    assert card["rows"] == 2
    assert card["route_counts"]["ALLOW_BOUNDED_DECODER_SHADOW"] == 1
    assert card["route_counts"]["RETRIEVE_MORE"] == 1
    assert card["unsafe_decisions"] == 0
    assert card["authority"]["training"] is False
