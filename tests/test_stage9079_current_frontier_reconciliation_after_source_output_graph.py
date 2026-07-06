from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9079_current_frontier_reconciliation_after_source_output_graph import (  # noqa: E402
    AUTHORITY_CLOSED,
    RECOVERED_RECENT_CONTROLS,
    build_card,
    validate_card,
)


def registry(latest: int = 9078) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9079_reconciles_source_output_graph_chain() -> None:
    card = build_card(registry())
    assert card["checks"]["source_stage9076_passed"] is True
    assert card["checks"]["source_stage9077_passed"] is True
    assert card["checks"]["source_stage9078_passed"] is True
    assert card["metrics"]["stage9078_added_nodes"] >= 5
    assert card["metrics"]["stage9078_added_edges"] >= 9
    assert len(RECOVERED_RECENT_CONTROLS) >= 7


def test_stage9079_keeps_access_and_training_closed() -> None:
    card = build_card(registry())
    assert card["metrics"]["ticket_instantiated_now"] is False
    assert card["metrics"]["source_metadata_read_now"] is False
    assert card["metrics"]["repository_source_bodies_read_now"] is False
    assert card["metrics"]["route_cards_materialized_now"] is False
    assert card["metrics"]["candidate_rows_materialized"] == 0
    assert card["metrics"]["training_ready"] is False
    assert not any(card["authority"].values())


def test_stage9079_validation_rejects_open_access_or_bad_frontier() -> None:
    card = build_card(registry())
    assert validate_card(card, registry()) == []
    bad = build_card(registry())
    bad["metrics"]["source_metadata_read_now"] = True
    assert "source_metadata_read_now" in validate_card(bad, registry())
    bad_training = build_card(registry())
    bad_training["metrics"]["training_authorized"] = True
    assert "training_authorized" in validate_card(bad_training, registry())
    bad_authority = build_card(registry())
    bad_authority["authority"]["source_emission_authorized"] = True
    assert "authority_open" in validate_card(bad_authority, registry())
    assert "unexpected_registry_frontier:9999" in validate_card(card, registry(latest=9999))
