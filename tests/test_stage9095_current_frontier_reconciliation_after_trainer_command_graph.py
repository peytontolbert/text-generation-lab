from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9095_current_frontier_reconciliation_after_trainer_command_graph import (  # noqa: E402
    AUTHORITY_CLOSED,
    RECOVERED_RECENT_CONTROLS,
    build_card,
    validate_card,
)


def registry(latest: int = 9094) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9095_reconciles_trainer_command_graph_chain() -> None:
    card = build_card(registry())
    assert card["checks"]["source_stage9092_passed"] is True
    assert card["checks"]["source_stage9093_passed"] is True
    assert card["checks"]["source_stage9094_passed"] is True
    assert card["metrics"]["stage9094_added_nodes"] >= 6
    assert card["metrics"]["stage9094_added_edges"] >= 16
    assert len(RECOVERED_RECENT_CONTROLS) >= 8


def test_stage9095_keeps_trainer_invocation_and_training_closed() -> None:
    card = build_card(registry())
    assert card["metrics"]["trainer_executed_now"] is False
    assert card["metrics"]["contract_only_invoked_now"] is False
    assert card["metrics"]["model_input_rows_now"] == 0
    assert card["metrics"]["model_forward_attempted"] is False
    assert card["metrics"]["decoder_ce_authorized"] is False
    assert card["metrics"]["denoise_ce_authorized"] is False
    assert card["metrics"]["training_ready"] is False
    assert not any(card["authority"].values())


def test_stage9095_validation_rejects_open_trainer_or_bad_frontier() -> None:
    card = build_card(registry())
    assert validate_card(card, registry()) == []
    bad = build_card(registry())
    bad["metrics"]["contract_only_invoked_now"] = True
    assert "contract_only_invoked_now" in validate_card(bad, registry())
    bad_rows = build_card(registry())
    bad_rows["metrics"]["model_input_rows_now"] = 1
    assert "model_input_rows_now" in validate_card(bad_rows, registry())
    bad_authority = build_card(registry())
    bad_authority["authority"]["model_execution_authorized_next"] = True
    assert "authority_open" in validate_card(bad_authority, registry())
    assert "unexpected_registry_frontier:9999" in validate_card(card, registry(latest=9999))
