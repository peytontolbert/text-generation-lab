from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9083_current_frontier_reconciliation_after_route_card_graph import (  # noqa: E402
    AUTHORITY_CLOSED,
    RECOVERED_RECENT_CONTROLS,
    build_card,
    validate_card,
)


def registry(latest: int = 9082) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9083_reconciles_route_card_graph_chain() -> None:
    card = build_card(registry())
    assert card["checks"]["source_stage9080_passed"] is True
    assert card["checks"]["source_stage9081_passed"] is True
    assert card["checks"]["source_stage9082_passed"] is True
    assert card["metrics"]["stage9082_added_nodes"] >= 5
    assert card["metrics"]["stage9082_added_edges"] >= 13
    assert len(RECOVERED_RECENT_CONTROLS) >= 7


def test_stage9083_keeps_route_card_and_trainer_paths_closed() -> None:
    card = build_card(registry())
    assert card["metrics"]["route_cards_materialized_now"] is False
    assert card["metrics"]["compiler_handoff_ready_now"] is False
    assert card["metrics"]["trainer_dry_run_ready_now"] is False
    assert card["metrics"]["trainer_dry_run_executed_now"] is False
    assert card["metrics"]["candidate_rows_materialized"] == 0
    assert card["metrics"]["training_ready"] is False
    assert not any(card["authority"].values())


def test_stage9083_validation_rejects_open_trainer_or_bad_frontier() -> None:
    card = build_card(registry())
    assert validate_card(card, registry()) == []
    bad = build_card(registry())
    bad["metrics"]["trainer_dry_run_ready_now"] = True
    assert "trainer_dry_run_ready_now" in validate_card(bad, registry())
    bad_route = build_card(registry())
    bad_route["metrics"]["route_cards_materialized_now"] = True
    assert "route_cards_materialized_now" in validate_card(bad_route, registry())
    bad_authority = build_card(registry())
    bad_authority["authority"]["harness_execution_authorized_next"] = True
    assert "authority_open" in validate_card(bad_authority, registry())
    assert "unexpected_registry_frontier:9999" in validate_card(card, registry(latest=9999))
