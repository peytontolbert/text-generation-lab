from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9080_no_data_route_card_materialization_audit_instance_design import (  # noqa: E402
    AUTHORITY_CLOSED,
    FUTURE_REQUIRED_INPUTS,
    FUTURE_REQUIRED_OUTPUTS,
    build_design,
    validate_design,
)


def registry(latest: int = 9079) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9080_designs_inactive_route_card_audit_instance() -> None:
    card = build_design(registry())
    template = card["instance_template"]
    assert template["required_inputs"] == FUTURE_REQUIRED_INPUTS
    assert template["required_outputs"] == FUTURE_REQUIRED_OUTPUTS
    assert card["metrics"]["instance_instantiated_now"] is False
    assert card["metrics"]["route_cards_materialized_now"] is False


def test_stage9080_keeps_compiler_and_trainer_closed() -> None:
    card = build_design(registry())
    assert card["metrics"]["source_output_ticket_instantiated_now"] is False
    assert card["metrics"]["source_metadata_read_now"] is False
    assert card["metrics"]["candidate_rows_materialized"] == 0
    assert card["metrics"]["compiler_handoff_ready_now"] is False
    assert card["metrics"]["trainer_dry_run_ready_now"] is False
    assert card["metrics"]["training_ready"] is False
    assert not any(card["authority"].values())


def test_stage9080_validation_rejects_open_materialization_or_bad_frontier() -> None:
    card = build_design(registry())
    assert validate_design(card, registry()) == []
    bad = build_design(registry())
    bad["metrics"]["route_cards_materialized_now"] = True
    assert "route_cards_materialized_now" in validate_design(bad, registry())
    bad_template = build_design(registry())
    bad_template["instance_template"]["closed_now"]["source_metadata_read_now"] = True
    assert "template_opened_current_operation" in validate_design(bad_template, registry())
    bad_authority = build_design(registry())
    bad_authority["authority"]["decoder_ce_training_authorized_next"] = True
    assert "authority_open" in validate_design(bad_authority, registry())
    assert "unexpected_registry_frontier:9999" in validate_design(card, registry(latest=9999))
