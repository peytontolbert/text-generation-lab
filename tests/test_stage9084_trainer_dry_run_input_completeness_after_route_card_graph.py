from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9084_trainer_dry_run_input_completeness_after_route_card_graph import (  # noqa: E402
    ADDITIONAL_REQUIRED_INPUTS,
    AUTHORITY_CLOSED,
    REQUIRED_BLOCKING_ASSERTIONS,
    build_checklist,
    validate_checklist,
)


def registry(latest: int = 9083) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9084_adds_source_ticket_and_route_card_inputs() -> None:
    card = build_checklist(registry())
    for required in ADDITIONAL_REQUIRED_INPUTS:
        assert required in card["future_required_inputs"]
    for assertion in REQUIRED_BLOCKING_ASSERTIONS:
        assert assertion in card["required_blocking_assertions"]
    assert card["checks"]["additional_inputs_added"] is True
    assert card["checks"]["blocking_assertions_recorded"] is True


def test_stage9084_keeps_trainer_readiness_closed() -> None:
    card = build_checklist(registry())
    assert card["metrics"]["trainer_dry_run_ready_now"] is False
    assert card["metrics"]["trainer_dry_run_executed_now"] is False
    assert card["metrics"]["route_cards_materialized_now"] is False
    assert card["metrics"]["candidate_rows_materialized"] == 0
    assert card["metrics"]["training_ready"] is False
    assert not any(card["authority"].values())


def test_stage9084_validation_rejects_missing_inputs_or_open_trainer() -> None:
    card = build_checklist(registry())
    assert validate_checklist(card, registry()) == []
    missing = build_checklist(registry())
    missing["future_required_inputs"].remove("route_card_materialization_audit_output.json")
    assert "missing_additional_input:route_card_materialization_audit_output.json" in validate_checklist(missing, registry())
    bad = build_checklist(registry())
    bad["metrics"]["trainer_dry_run_ready_now"] = True
    assert "trainer_dry_run_ready_now" in validate_checklist(bad, registry())
    bad_authority = build_checklist(registry())
    bad_authority["authority"]["model_execution_authorized_next"] = True
    assert "authority_open" in validate_checklist(bad_authority, registry())
    assert "unexpected_registry_frontier:9999" in validate_checklist(card, registry(latest=9999))
