from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9138_real_route_card_input_authorization_gate_design import REQUIRED_TICKET_FIELDS  # noqa: E402
from scripts.build_stage9140_real_route_card_input_ticket_template import (  # noqa: E402
    build_ticket_template,
    validate_ticket_template,
)
from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # noqa: E402


def registry(latest: int = 9139) -> dict:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9140_template_passes_and_is_not_instance() -> None:
    card = build_ticket_template(registry())

    assert validate_ticket_template(card, registry()) == []
    assert all(card["checks"].values())
    ticket = card["ticket_template"]
    assert ticket["ticket_kind"] == "REAL_ROUTE_CARD_INPUT_PREFLIGHT_TEMPLATE_NOT_INSTANCE"
    assert ticket["approved_for_execution"] is False
    assert ticket["max_rows"] == 0
    assert ticket["dry_run_only"] is True
    assert ticket["no_source_bodies"] is True
    assert ticket["no_decoder_targets"] is True
    assert ticket["no_trainer_execution"] is True
    assert not any(ticket["authority"].values())
    assert not any(card["authority"].values())


def test_stage9140_template_contains_required_fields_and_controls() -> None:
    card = build_ticket_template(registry())
    ticket = card["ticket_template"]

    assert set(REQUIRED_TICKET_FIELDS).issubset(set(ticket))
    assert "explicit_user_approval_for_real_input_ticket_instance" in ticket["required_manual_approvals"]
    assert "separate_authorization_for_any_arxiv_path" in ticket["required_manual_approvals"]
    assert "separate_authorization_before_route_card_materialization" in ticket["required_manual_approvals"]
    assert "no_arxiv_path_without_separate_authorization" in ticket["required_preflight_checks"]
    assert "source_body" in ticket["forbidden_input_fields"]
    assert "decoder_target" in ticket["forbidden_input_fields"]
    assert "hidden_reference" in ticket["forbidden_input_fields"]


def test_stage9140_does_not_authorize_real_input_or_execution() -> None:
    card = build_ticket_template(registry())
    metrics = card["metrics"]

    assert metrics["ticket_template_materialized"] is True
    assert metrics["ticket_instance_materialized"] is False
    assert metrics["approved_for_execution"] is False
    assert metrics["real_input_authorized_now"] is False
    assert metrics["real_judge_rows_used"] == 0
    assert metrics["real_ranker_rows_used"] == 0
    assert metrics["real_route_cards_materialized"] == 0
    assert metrics["route_cards_materialized_now"] is False
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


def test_stage9140_rejects_unsafe_template_mutations() -> None:
    card = build_ticket_template(registry())
    card["ticket_template"]["approved_for_execution"] = True
    assert "ticket_approved_for_execution" in validate_ticket_template(card, registry())

    card = build_ticket_template(registry())
    card["ticket_template"]["max_rows"] = 10
    assert "template_max_rows_not_zero" in validate_ticket_template(card, registry())

    card = build_ticket_template(registry())
    card["ticket_template"]["authority"]["model_execution_authorized_next"] = True
    assert "ticket_authority_open" in validate_ticket_template(card, registry())

    card = build_ticket_template(registry())
    card["metrics"]["dataset_rows_loaded"] = True
    assert "dataset_rows_loaded" in validate_ticket_template(card, registry())

    card = build_ticket_template(registry())
    assert "unexpected_registry_frontier:9999" in validate_ticket_template(card, registry(latest=9999))
