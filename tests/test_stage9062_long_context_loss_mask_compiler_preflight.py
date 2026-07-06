from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9062_long_context_loss_mask_compiler_preflight import (  # noqa: E402
    audit_loss_mask_preflight,
    build_preflight,
    closed_route_card,
    run_negative_cases,
    structured_after_all_gates_card,
    translate_route_losses,
)


def test_stage9062_loss_mask_preflight_passes() -> None:
    preflight = build_preflight()
    assert preflight["passed"] is True
    assert preflight["checks"]["decoder_denoise_runtime_closed"] is True
    assert preflight["metrics"]["training_authorized"] is False


def test_stage9062_closed_and_structured_preflight_cards_pass() -> None:
    assert audit_loss_mask_preflight(closed_route_card()) == []
    assert audit_loss_mask_preflight(structured_after_all_gates_card()) == []
    translated = translate_route_losses(structured_after_all_gates_card()["losses_enabled"])
    assert translated["symbol_binding_ce"] is True
    assert translated["decoder_ce"] is False
    assert translated["denoise_ce"] is False


def test_stage9062_negative_cases_rejected() -> None:
    negatives = run_negative_cases()
    assert negatives
    assert all(item["rejected"] for item in negatives.values())
