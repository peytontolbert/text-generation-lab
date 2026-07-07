from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9107_current_frontier_reconciliation_after_execution_authorization_graph import (  # noqa: E402
    AUTHORITY_CLOSED,
    RECOVERED_RECENT_CONTROLS,
    build_card,
    validate_card,
)


def registry(latest: int = 9106) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9107_reconciles_execution_authorization_graph_chain() -> None:
    card = build_card(registry())
    assert card["checks"]["source_stage9104_passed"] is True
    assert card["checks"]["source_stage9105_passed"] is True
    assert card["checks"]["source_stage9106_passed"] is True
    assert card["metrics"]["stage9106_added_nodes"] >= 6
    assert card["metrics"]["stage9106_added_edges"] >= 16
    assert len(RECOVERED_RECENT_CONTROLS) >= 8


def test_stage9107_keeps_every_execution_path_closed() -> None:
    card = build_card(registry())
    assert card["metrics"]["same_stage_execution_authorized"] is False
    assert card["metrics"]["next_stage_execution_authorized"] is False
    assert card["metrics"]["trainer_executed_now"] is False
    assert card["metrics"]["contract_only_invoked_now"] is False
    assert card["metrics"]["runtime_assertions_executed_now"] is False
    assert card["metrics"]["model_input_rows_now"] == 0
    assert card["metrics"]["model_forward_attempted"] is False
    assert card["metrics"]["decoder_ce_authorized"] is False
    assert card["metrics"]["cleanup_authorized_now"] is False
    assert card["metrics"]["training_ready"] is False
    assert not any(card["authority"].values())


def test_stage9107_validation_rejects_open_execution_or_bad_frontier() -> None:
    card = build_card(registry())
    assert validate_card(card, registry()) == []
    same_stage = build_card(registry())
    same_stage["metrics"]["same_stage_execution_authorized"] = True
    assert "same_stage_execution_authorized" in validate_card(same_stage, registry())
    trainer = build_card(registry())
    trainer["metrics"]["trainer_executed_now"] = True
    assert "trainer_executed_now" in validate_card(trainer, registry())
    rows = build_card(registry())
    rows["metrics"]["model_input_rows_now"] = 1
    assert "model_input_rows_now" in validate_card(rows, registry())
    cleanup = build_card(registry())
    cleanup["metrics"]["cleanup_authorized_now"] = True
    assert "cleanup_authorized_now" in validate_card(cleanup, registry())
    authority = build_card(registry())
    authority["authority"]["model_execution_authorized_next"] = True
    assert "authority_open" in validate_card(authority, registry())
    assert "unexpected_registry_frontier:9999" in validate_card(card, registry(latest=9999))
