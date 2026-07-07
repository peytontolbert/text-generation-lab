from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9112_current_frontier_reconciliation_after_metadata_preflight_graph import (  # noqa: E402
    AUTHORITY_CLOSED,
    RECOVERED_RECENT_CONTROLS,
    REMAINING_BLOCKERS,
    build_card,
    validate_card,
)


def registry(latest: int = 9111) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9112_reconciles_metadata_preflight_graph_chain() -> None:
    card = build_card(registry())

    assert card["checks"]["source_stage9109_passed"] is True
    assert card["checks"]["source_stage9110_passed"] is True
    assert card["checks"]["source_stage9111_passed"] is True
    assert card["metrics"]["stage9111_added_nodes"] >= 7
    assert card["metrics"]["stage9111_added_edges"] >= 24
    assert len(RECOVERED_RECENT_CONTROLS) >= 8
    assert "metadata_only_arxiv_inventory_ticket_missing" in REMAINING_BLOCKERS


def test_stage9112_keeps_data_and_training_paths_closed() -> None:
    card = build_card(registry())
    metrics = card["metrics"]

    assert metrics["arxiv_access_performed"] is False
    assert metrics["arxiv_stat_performed"] is False
    assert metrics["dataset_rows_loaded"] is False
    assert metrics["repository_source_bodies_loaded"] is False
    assert metrics["arxiv_write_authorized"] is False
    assert metrics["data_mining_authorized"] is False
    assert metrics["route_cards_materialized_now"] is False
    assert metrics["route_to_loss_translation_ready_now"] is False
    assert metrics["trainer_executed_now"] is False
    assert metrics["contract_only_invoked_now"] is False
    assert metrics["model_input_rows_now"] == 0
    assert metrics["model_forward_attempted"] is False
    assert metrics["training_ready"] is False
    assert metrics["training_authorized"] is False
    assert metrics["decoder_ce_authorized"] is False
    assert metrics["denoise_ce_authorized"] is False
    assert metrics["runtime_authorized_flag"] is False
    assert metrics["cleanup_authorized_now"] is False
    assert not any(card["authority"].values())


def test_stage9112_validation_rejects_open_data_training_or_bad_frontier() -> None:
    card = build_card(registry())
    assert validate_card(card, registry()) == []

    arxiv = build_card(registry())
    arxiv["metrics"]["arxiv_access_performed"] = True
    assert "arxiv_access_performed" in validate_card(arxiv, registry())

    source = build_card(registry())
    source["metrics"]["repository_source_bodies_loaded"] = True
    assert "repository_source_bodies_loaded" in validate_card(source, registry())

    route = build_card(registry())
    route["metrics"]["route_cards_materialized_now"] = True
    assert "route_cards_materialized_now" in validate_card(route, registry())

    trainer = build_card(registry())
    trainer["metrics"]["trainer_executed_now"] = True
    assert "trainer_executed_now" in validate_card(trainer, registry())

    rows = build_card(registry())
    rows["metrics"]["model_input_rows_now"] = 1
    assert "model_input_rows_now" in validate_card(rows, registry())

    authority = build_card(registry())
    authority["authority"]["model_execution_authorized_next"] = True
    assert "authority_open" in validate_card(authority, registry())

    assert "unexpected_registry_frontier:9999" in validate_card(card, registry(latest=9999))
