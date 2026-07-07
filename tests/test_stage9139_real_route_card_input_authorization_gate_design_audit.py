from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9139_real_route_card_input_authorization_gate_design_audit import (  # noqa: E402
    NEGATIVE_CASES,
    build_audit,
    run_negative_cases,
)
from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # noqa: E402


def registry(latest: int = 9138) -> dict:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9139_audit_passes_base_design() -> None:
    audit = build_audit(registry())

    assert audit["passed"] is True
    assert audit["base_failures"] == []
    assert audit["checks"]["base_design_passes"] is True
    assert audit["checks"]["required_ticket_fields_complete"] is True
    assert audit["checks"]["required_preflight_checks_complete"] is True
    assert audit["checks"]["forbidden_input_fields_complete"] is True
    assert audit["checks"]["real_input_closed"] is True
    assert audit["checks"]["dataset_loading_closed"] is True
    assert audit["checks"]["authority_closed"] is True


def test_stage9139_rejects_negative_cases() -> None:
    negatives = run_negative_cases()

    assert set(NEGATIVE_CASES) == set(negatives)
    assert all(item["rejected"] for item in negatives.values())
    assert "missing_ticket_field:judge_rows_path" in negatives["missing_judge_ticket_field"]["failures"]
    assert "missing_ticket_field:junk_ranker_rows_path" in negatives["missing_ranker_ticket_field"]["failures"]
    assert "missing_preflight_check:no_arxiv_path_without_separate_authorization" in negatives["missing_arxiv_preflight"]["failures"]
    assert "missing_preflight_check:no_source_body_fields_present" in negatives["missing_source_body_preflight"]["failures"]
    assert "missing_forbidden_input_field:decoder_target" in negatives["missing_forbidden_decoder_target"]["failures"]
    assert "real_input_authorized_now" in negatives["authorizes_real_input"]["failures"]
    assert "dataset_rows_loaded" in negatives["loads_dataset_rows"]["failures"]
    assert "route_cards_materialized_now" in negatives["materializes_route_cards"]["failures"]
    assert "training_authorized" in negatives["opens_training"]["failures"]
    assert "runtime_authorized_flag" in negatives["opens_runtime"]["failures"]
    assert "authority_open" in negatives["opens_authority"]["failures"]
    assert "unexpected_registry_frontier:9999" in negatives["bad_registry_frontier"]["failures"]


def test_stage9139_keeps_real_input_and_execution_closed() -> None:
    audit = build_audit(registry())
    metrics = audit["metrics"]

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
    assert metrics["network_upload_performed"] is False
    assert metrics["cleanup_authorized_now"] is False


def test_stage9139_bad_live_registry_fails() -> None:
    audit = build_audit(registry(latest=9999))

    assert audit["passed"] is False
    assert "registry_frontier_stage9138" in audit["failures"]
