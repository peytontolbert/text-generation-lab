from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9108_central_graph_gap_walk_remaining_trainer_blockers import (  # noqa: E402
    AUTHORITY_CLOSED,
    REMAINING_BLOCKERS,
    REQUIRED_CONTROL_NODES,
    build_card,
    validate_card,
)


def registry(latest: int = 9107) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9108_confirms_required_control_nodes() -> None:
    card = build_card(registry())
    assert card["checks"]["required_control_nodes_present"] is True
    assert card["metrics"]["present_control_nodes"] == len(REQUIRED_CONTROL_NODES)
    assert card["metrics"]["missing_control_nodes"] == 0


def test_stage9108_records_remaining_trainer_blockers() -> None:
    card = build_card(registry())
    blockers = {row["blocker"] for row in card["remaining_blockers"]}
    assert len(REMAINING_BLOCKERS) >= 7
    assert "explicit_user_execution_request_missing" in blockers
    assert "real_source_output_ticket_not_instantiated" in blockers
    assert "route_cards_not_materialized" in blockers
    assert "route_to_loss_translation_not_materialized" in blockers
    assert "trainer_contract_only_artifacts_not_materialized" in blockers
    assert "final_pre_execution_audit_missing" in blockers
    assert "one_run_training_ticket_missing" in blockers


def test_stage9108_keeps_data_execution_and_training_closed() -> None:
    card = build_card(registry())
    metrics = card["metrics"]
    assert metrics["same_stage_execution_authorized"] is False
    assert metrics["next_stage_execution_authorized"] is False
    assert metrics["source_output_ticket_instantiated_now"] is False
    assert metrics["row_bodies_read_now"] is False
    assert metrics["route_cards_materialized_now"] is False
    assert metrics["route_to_loss_translation_ready_now"] is False
    assert metrics["model_input_rows_now"] == 0
    assert metrics["trainer_executed_now"] is False
    assert metrics["contract_only_invoked_now"] is False
    assert metrics["model_forward_attempted"] is False
    assert metrics["training_ready"] is False
    assert metrics["cleanup_authorized_now"] is False
    assert not any(card["authority"].values())


def test_stage9108_validation_rejects_open_execution_data_or_bad_frontier() -> None:
    card = build_card(registry())
    assert validate_card(card, registry()) == []
    route_cards = build_card(registry())
    route_cards["metrics"]["route_cards_materialized_now"] = True
    assert "route_cards_materialized_now" in validate_card(route_cards, registry())
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
