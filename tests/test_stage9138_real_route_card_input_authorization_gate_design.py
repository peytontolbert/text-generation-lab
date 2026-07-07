from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9138_real_route_card_input_authorization_gate_design import (  # noqa: E402
    FORBIDDEN_INPUT_FIELDS,
    REQUIRED_PREFLIGHT_CHECKS,
    REQUIRED_TICKET_FIELDS,
    build_design,
    validate_design,
)
from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # noqa: E402


def registry(latest: int = 9137) -> dict:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9138_design_passes_with_closed_authority() -> None:
    design = build_design(registry())

    assert validate_design(design, registry()) == []
    assert all(design["checks"].values())
    assert not any(design["authority"].values())


def test_stage9138_records_ticket_fields_preflights_and_forbidden_fields() -> None:
    design = build_design(registry())

    assert set(REQUIRED_TICKET_FIELDS).issubset(set(design["required_ticket_fields"]))
    assert set(REQUIRED_PREFLIGHT_CHECKS).issubset(set(design["required_preflight_checks"]))
    assert set(FORBIDDEN_INPUT_FIELDS).issubset(set(design["forbidden_input_fields"]))
    assert "judge_rows_path" in design["required_ticket_fields"]
    assert "junk_ranker_rows_path" in design["required_ticket_fields"]
    assert "no_arxiv_path_without_separate_authorization" in design["required_preflight_checks"]
    assert "no_source_body_fields_present" in design["required_preflight_checks"]
    assert "decoder_target" in design["forbidden_input_fields"]
    assert "hidden_reference" in design["forbidden_input_fields"]


def test_stage9138_does_not_authorize_or_load_real_inputs() -> None:
    design = build_design(registry())
    metrics = design["metrics"]

    assert metrics["real_input_authorized_now"] is False
    assert metrics["real_judge_rows_used"] == 0
    assert metrics["real_ranker_rows_used"] == 0
    assert metrics["real_route_cards_materialized"] == 0
    assert metrics["route_cards_materialized_now"] is False
    assert metrics["route_to_loss_translation_ready_now"] is False
    assert metrics["loss_mask_cards_materialized_now"] is False
    assert metrics["compiler_handoff_ready_now"] is False
    assert metrics["dataset_rows_loaded"] is False
    assert metrics["repository_source_bodies_loaded"] is False
    assert metrics["trainer_executed_now"] is False
    assert metrics["model_forward_attempted"] is False
    assert metrics["training_authorized"] is False
    assert metrics["decoder_ce_authorized"] is False
    assert metrics["denoise_ce_authorized"] is False
    assert metrics["runtime_authorized_flag"] is False
    assert metrics["cleanup_authorized_now"] is False


def test_stage9138_rejects_missing_fields_authority_and_bad_frontier() -> None:
    design = build_design(registry())
    design["required_ticket_fields"].remove("judge_rows_path")
    assert "missing_ticket_field:judge_rows_path" in validate_design(design, registry())

    design = build_design(registry())
    design["required_preflight_checks"].remove("no_arxiv_path_without_separate_authorization")
    assert "missing_preflight_check:no_arxiv_path_without_separate_authorization" in validate_design(design, registry())

    design = build_design(registry())
    design["forbidden_input_fields"].remove("source_body")
    assert "missing_forbidden_input_field:source_body" in validate_design(design, registry())

    design = build_design(registry())
    design["authority"]["model_execution_authorized_next"] = True
    assert "authority_open" in validate_design(design, registry())

    design = build_design(registry())
    assert "unexpected_registry_frontier:9999" in validate_design(design, registry(latest=9999))
