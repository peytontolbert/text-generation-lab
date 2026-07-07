from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9132_synthetic_route_to_loss_mask_translator_smoke import (  # noqa: E402
    build_smoke,
    validate_smoke,
)
from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # noqa: E402
from scripts.synthetic_route_to_loss_mask_translator import (  # noqa: E402
    translate_synthetic_fixtures,
    validate_synthetic_loss_masks,
)


def registry(latest: int = 9131) -> dict:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9132_translates_all_synthetic_fixtures() -> None:
    cards = translate_synthetic_fixtures()

    assert len(cards) == 6
    assert validate_synthetic_loss_masks(cards) == []
    assert all(card["anti_cheat"]["synthetic_only"] is True for card in cards)
    assert all(card["anti_cheat"]["real_route_card_used"] is False for card in cards)
    assert all(not any(card["authority"].values()) for card in cards)


def test_stage9132_decoder_ce_only_for_bounded_decoder_route() -> None:
    cards = translate_synthetic_fixtures()
    decoder_cards = [card for card in cards if "decoder_ce" in card["enabled_losses"]]

    assert len(decoder_cards) == 1
    assert decoder_cards[0]["row_id"] == "synthetic_keep_bounded_decoder"
    assert decoder_cards[0]["decoder_ce_allowed"] is True
    assert decoder_cards[0]["denoise_ce_allowed"] is False
    assert decoder_cards[0]["runtime_reward_allowed"] is False


def test_stage9132_quarantine_and_non_decode_routes_block_decoder_loss() -> None:
    by_route = {card["loss_authority_evidence"]["route"]: card for card in translate_synthetic_fixtures()}

    assert by_route["QUARANTINE_LABEL_CONFLICT"]["enabled_losses"] == []
    assert "decoder_ce" not in by_route["HOLD_LONG_OUTPUT"]["enabled_losses"]
    assert "decoder_ce" not in by_route["NEEDS_RETRIEVAL"]["enabled_losses"]
    assert "decoder_ce" not in by_route["USE_FOR_DENOISE_REPAIR"]["enabled_losses"]
    assert by_route["USE_FOR_DENOISE_REPAIR"]["enabled_losses"] == ["denoise_ce"]


def test_stage9132_smoke_passes_without_real_data_or_execution() -> None:
    smoke = build_smoke(registry())

    assert validate_smoke(smoke, registry()) == []
    assert all(smoke["checks"].values())
    metrics = smoke["metrics"]
    assert metrics["synthetic_loss_masks_materialized_now"] is True
    assert metrics["real_route_cards_used"] == 0
    assert metrics["real_loss_masks_materialized"] == 0
    assert metrics["route_cards_materialized_now"] is False
    assert metrics["loss_mask_cards_materialized_now"] is False
    assert metrics["compiler_handoff_ready_now"] is False
    assert metrics["dataset_rows_loaded"] is False
    assert metrics["repository_source_bodies_loaded"] is False
    assert metrics["trainer_executed_now"] is False
    assert metrics["model_forward_attempted"] is False
    assert metrics["training_authorized"] is False
    assert metrics["decoder_ce_authorized"] is False
    assert metrics["denoise_ce_authorized"] is False
    assert metrics["runtime_authorized_flag"] is False
    assert metrics["cleanup_authorized_now"] is False
    assert not any(smoke["authority"].values())


def test_stage9132_rejects_bad_frontier_and_open_authority() -> None:
    smoke = build_smoke(registry())

    assert "unexpected_registry_frontier:9999" in validate_smoke(smoke, registry(latest=9999))
    smoke["authority"]["model_execution_authorized_next"] = True
    assert "authority_open" in validate_smoke(smoke, registry())
