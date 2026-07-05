from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from moe_lora_adapter_router_contract import router_card, router_decision


def test_ready_language_task_repo_routes_composed_shadow_without_authority() -> None:
    decision = router_decision({
        "row_id": "ok",
        "language_family": "python",
        "task_family": "repo_repair",
        "repo_family": "test_heavy",
        "language_slice_ready": True,
        "task_slice_ready": True,
        "repo_slice_ready": True,
        "language_confidence": 0.9,
        "task_confidence": 0.85,
        "repo_confidence": 0.8,
    })
    assert decision["route"] == "ROUTE_COMPOSED_ADAPTER_SHADOW"
    assert decision["adapter_shadow_allowed"] is True
    assert len(decision["selected_adapters"]) == 3
    assert decision["adapter_training_authorized"] is False
    assert decision["model_execution_authorized"] is False
    assert decision["decoder_ce_authorized"] is False


def test_missing_slice_readiness_requests_slice_evidence() -> None:
    decision = router_decision({
        "row_id": "slice",
        "language_family": "rust",
        "task_family": "repo_repair",
        "language_slice_ready": False,
        "task_slice_ready": True,
        "language_confidence": 0.8,
        "task_confidence": 0.8,
    })
    assert decision["route"] == "REQUEST_SLICE_EVIDENCE"
    assert decision["adapter_shadow_allowed"] is False
    assert "language_slice_not_ready" in decision["reasons"]


def test_missing_adapter_inventory_falls_back_to_base_shared() -> None:
    decision = router_decision({
        "row_id": "base",
        "language_family": "unknown_lang",
        "task_family": "repo_repair",
        "language_slice_ready": True,
        "task_slice_ready": True,
        "language_confidence": 0.9,
        "task_confidence": 0.9,
    })
    assert decision["route"] == "USE_BASE_SHARED"
    assert "language_adapter_missing" in decision["reasons"]


def test_authority_or_ood_forces_abstain() -> None:
    decision = router_decision({
        "row_id": "unsafe",
        "language_family": "python",
        "task_family": "repo_repair",
        "language_slice_ready": True,
        "task_slice_ready": True,
        "authority": {"adapter_training": True},
        "ood_score": 0.9,
    })
    assert decision["route"] == "ABSTAIN_ADAPTER_ROUTE"
    assert decision["selected_adapters"] == []
    assert "authority_true" in decision["reasons"]
    assert "ood_score_high" in decision["reasons"]


def test_router_card_counts_routes_and_keeps_authority_closed() -> None:
    card = router_card([
        {"row_id": "ok", "language_family": "python", "task_family": "repo_repair", "repo_family": "test_heavy", "language_slice_ready": True, "task_slice_ready": True, "repo_slice_ready": True, "language_confidence": .9, "task_confidence": .85, "repo_confidence": .8},
        {"row_id": "slice", "language_family": "rust", "task_family": "repo_repair", "language_slice_ready": False, "task_slice_ready": True, "language_confidence": .8, "task_confidence": .8},
    ])
    assert card["rows"] == 2
    assert card["route_counts"]["ROUTE_COMPOSED_ADAPTER_SHADOW"] == 1
    assert card["route_counts"]["REQUEST_SLICE_EVIDENCE"] == 1
    assert card["unsafe_decisions"] == 0
    assert card["authority"]["training"] is False
    assert card["authority"]["adapter_training"] is False
