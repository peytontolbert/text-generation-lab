from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9124_route_card_schema_recovery_design import ROUTE_ENUM  # noqa: E402
from scripts.build_stage9136_synthetic_route_card_materializer_smoke import (  # noqa: E402
    build_smoke,
    validate_smoke,
)
from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # noqa: E402
from scripts.route_card_materializer import (  # noqa: E402
    materialize_synthetic_route_cards,
    validate_route_card,
    validate_route_cards,
)


def registry(latest: int = 9135) -> dict:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9136_materializes_synthetic_route_cards_for_all_routes() -> None:
    cards = materialize_synthetic_route_cards()

    assert len(cards) == len(ROUTE_ENUM)
    assert {card["route"] for card in cards} == set(ROUTE_ENUM)
    assert validate_route_cards(cards) == []
    assert all((card["provenance"] or {}).get("synthetic_only") is True for card in cards)
    assert all(not any(card["authority"].values()) for card in cards)


def test_stage9136_route_card_validation_rejects_bad_cards() -> None:
    card = materialize_synthetic_route_cards()[0]
    card["route"] = "UNKNOWN"
    assert any("unknown_route" in failure for failure in validate_route_card(card))

    card = materialize_synthetic_route_cards()[0]
    card["authority"]["runtime_authorized"] = True
    assert any("authority_open" in failure for failure in validate_route_card(card))

    card = [item for item in materialize_synthetic_route_cards() if item["route"] == "KEEP_BOUNDED_DECODER"][0]
    card["decoder_budget_ok"] = False
    assert any("bounded_decoder_without_budget_ok" in failure for failure in validate_route_card(card))


def test_stage9136_smoke_passes_without_real_inputs_or_execution() -> None:
    smoke = build_smoke(registry())

    assert validate_smoke(smoke, registry()) == []
    assert smoke["checks"]["all_routes_covered"] is True
    assert smoke["checks"]["all_cards_synthetic_only"] is True
    assert smoke["checks"]["all_cards_authority_closed"] is True
    metrics = smoke["metrics"]
    assert metrics["real_judge_rows_used"] == 0
    assert metrics["real_ranker_rows_used"] == 0
    assert metrics["real_route_cards_materialized"] == 0
    assert metrics["synthetic_route_cards_materialized_now"] is True
    assert metrics["route_cards_materialized_now"] is False
    assert metrics["route_to_loss_translation_ready_now"] is False
    assert metrics["loss_mask_cards_materialized_now"] is False
    assert metrics["compiler_handoff_ready_now"] is False
    assert metrics["dataset_rows_loaded"] is False
    assert metrics["trainer_executed_now"] is False
    assert metrics["model_forward_attempted"] is False
    assert metrics["training_authorized"] is False
    assert metrics["decoder_ce_authorized"] is False
    assert metrics["denoise_ce_authorized"] is False
    assert metrics["runtime_authorized_flag"] is False
    assert metrics["cleanup_authorized_now"] is False


def test_stage9136_rejects_bad_frontier_and_real_input_counts() -> None:
    smoke = build_smoke(registry())

    assert "unexpected_registry_frontier:9999" in validate_smoke(smoke, registry(latest=9999))
    smoke["metrics"]["real_judge_rows_used"] = 1
    assert "real_judge_rows_used" in validate_smoke(smoke, registry())
