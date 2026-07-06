from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9085_trainer_dry_run_input_completeness_audit import (  # noqa: E402
    build_audit,
    run_negative_cases,
)


def test_stage9085_base_audit_passes() -> None:
    audit = build_audit()
    assert audit["passed"] is True
    assert audit["base_failures"] == []
    assert audit["checks"]["additional_inputs_present"] is True
    assert audit["checks"]["blocking_assertions_present"] is True
    assert audit["checks"]["trainer_closed"] is True
    assert audit["checks"]["authority_closed"] is True


def test_stage9085_rejects_trainer_and_materialization_negative_cases() -> None:
    negatives = run_negative_cases()
    assert negatives
    assert all(item["rejected"] for item in negatives.values())
    assert "trainer_dry_run_ready_now" in negatives["trainer_dry_run_ready_now"]["failures"]
    assert "candidate_rows_materialized" in negatives["candidate_rows_materialized"]["failures"]
    assert "route_cards_materialized_now" in negatives["route_cards_materialized_now"]["failures"]
    assert "arxiv_read_authorized_for_compiler" in negatives["arxiv_read_authorized_for_compiler"]["failures"]


def test_stage9085_rejects_missing_controls_and_open_authority() -> None:
    negatives = run_negative_cases()
    assert "missing_additional_input:source_output_ticket_authorization_card.json" in negatives["missing_source_output_ticket_authorization"]["failures"]
    assert "missing_additional_input:route_card_materialization_audit_output.json" in negatives["missing_route_card_materialization_audit_output"]["failures"]
    assert "missing_blocking_assertion:trainer_dry_run_blocked_until_route_card_audit_passes" in negatives["missing_trainer_blocking_assertion"]["failures"]
    assert "authority_open" in negatives["authority_open_decoder_ce"]["failures"]
    assert "unexpected_registry_frontier:9999" in negatives["unexpected_registry_frontier"]["failures"]


def test_stage9085_keeps_all_current_execution_closed() -> None:
    audit = build_audit()
    metrics = audit["metrics"]
    assert metrics["trainer_dry_run_ready_now"] is False
    assert metrics["trainer_dry_run_executed_now"] is False
    assert metrics["route_cards_materialized_now"] is False
    assert metrics["candidate_rows_materialized"] == 0
    assert metrics["model_forward_attempted"] is False
    assert metrics["training_ready"] is False
    assert metrics["arxiv_read_authorized_for_compiler"] is False
    assert not any(audit["authority"].values())
