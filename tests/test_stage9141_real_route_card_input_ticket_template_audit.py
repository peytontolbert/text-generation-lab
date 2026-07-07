from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9141_real_route_card_input_ticket_template_audit import (  # noqa: E402
    NEGATIVE_CASES,
    build_audit,
    run_negative_cases,
)
from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # noqa: E402


def registry(latest: int = 9140) -> dict:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9141_audit_passes_base_template() -> None:
    audit = build_audit(registry())

    assert audit["passed"] is True
    assert audit["base_failures"] == []
    assert audit["checks"]["base_template_passes"] is True
    assert audit["checks"]["template_not_instance"] is True
    assert audit["checks"]["not_approved_for_execution"] is True
    assert audit["checks"]["max_rows_zero"] is True
    assert audit["checks"]["real_input_closed"] is True
    assert audit["checks"]["dataset_loading_closed"] is True
    assert audit["checks"]["authority_closed"] is True


def test_stage9141_rejects_negative_cases() -> None:
    negatives = run_negative_cases()

    assert set(NEGATIVE_CASES) == set(negatives)
    assert all(item["rejected"] for item in negatives.values())
    assert "ticket_approved_for_execution" in negatives["template_approved_for_execution"]["failures"]
    assert "template_max_rows_not_zero" in negatives["max_rows_nonzero"]["failures"]
    assert "ticket_instance_materialized" in negatives["ticket_instance_materialized"]["failures"]
    assert "real_input_authorized_now" in negatives["real_input_authorized"]["failures"]
    assert "dataset_rows_loaded" in negatives["dataset_rows_loaded"]["failures"]
    assert "route_cards_materialized_now" in negatives["route_cards_materialized"]["failures"]
    assert "training_authorized" in negatives["opens_training"]["failures"]
    assert "decoder_ce_authorized" in negatives["opens_decoder_ce"]["failures"]
    assert "runtime_authorized_flag" in negatives["opens_runtime"]["failures"]
    assert "ticket_authority_open" in negatives["ticket_authority_open"]["failures"]
    assert "authority_open" in negatives["summary_authority_open"]["failures"]
    assert "unexpected_registry_frontier:9999" in negatives["bad_registry_frontier"]["failures"]


def test_stage9141_keeps_real_input_and_execution_closed() -> None:
    audit = build_audit(registry())
    metrics = audit["metrics"]

    assert metrics["ticket_template_audited"] is True
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


def test_stage9141_bad_live_registry_fails() -> None:
    audit = build_audit(registry(latest=9999))

    assert audit["passed"] is False
    assert "registry_frontier_stage9140" in audit["failures"]
