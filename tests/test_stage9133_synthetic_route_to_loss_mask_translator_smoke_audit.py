from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9133_synthetic_route_to_loss_mask_translator_smoke_audit import (  # noqa: E402
    NEGATIVE_MUTATIONS,
    audit_cards,
    build_audit,
    mutate,
    run_negative_cases,
)
from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # noqa: E402
from scripts.synthetic_route_to_loss_mask_translator import translate_synthetic_fixtures  # noqa: E402


def registry(latest: int = 9132) -> dict:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9133_audits_clean_synthetic_cards() -> None:
    cards = translate_synthetic_fixtures()

    assert audit_cards(cards) == []


def test_stage9133_rejects_all_mutated_cards() -> None:
    cards = translate_synthetic_fixtures()
    negatives = run_negative_cases(cards)

    assert set(negatives) == set(NEGATIVE_MUTATIONS)
    assert all(item["rejected"] for item in negatives.values())
    assert any("authority_open" in failure for failure in audit_cards(mutate(cards, "open_authority")))
    assert any("decoder_ce_route_violation" in failure for failure in audit_cards(mutate(cards, "structured_decoder_ce")))
    assert any("quarantine_has_enabled_losses" in failure for failure in audit_cards(mutate(cards, "quarantine_enabled_loss")))
    assert any("missing_required_field:loss_weights" in failure for failure in audit_cards(mutate(cards, "missing_required_field")))
    assert any("real_route_card_used" in failure for failure in audit_cards(mutate(cards, "real_route_card_used")))


def test_stage9133_build_audit_passes_and_keeps_authority_closed() -> None:
    audit = build_audit(registry())

    assert audit["passed"] is True
    assert audit["checks"]["card_failures_empty"] is True
    assert audit["checks"]["negative_cases_rejected"] is True
    assert audit["checks"]["no_real_route_cards"] is True
    assert audit["checks"]["no_real_dataset_rows"] is True
    assert audit["checks"]["authority_closed"] is True
    assert audit["metrics"]["real_route_cards_used"] == 0
    assert audit["metrics"]["real_loss_masks_materialized"] == 0
    assert audit["metrics"]["route_cards_materialized_now"] is False
    assert audit["metrics"]["loss_mask_cards_materialized_now"] is False
    assert audit["metrics"]["compiler_handoff_ready_now"] is False
    assert audit["metrics"]["trainer_executed_now"] is False
    assert audit["metrics"]["model_forward_attempted"] is False
    assert audit["metrics"]["training_authorized"] is False
    assert audit["metrics"]["runtime_authorized_flag"] is False
    assert audit["metrics"]["cleanup_authorized_now"] is False
    assert not any(audit["authority"].values())


def test_stage9133_bad_registry_frontier_fails() -> None:
    audit = build_audit(registry(latest=9999))

    assert audit["passed"] is False
    assert "registry_frontier_stage9132" in audit["failures"]
