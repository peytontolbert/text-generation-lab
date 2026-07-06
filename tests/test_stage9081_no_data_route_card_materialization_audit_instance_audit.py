from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9081_no_data_route_card_materialization_audit_instance_audit import (  # noqa: E402
    build_audit,
    run_negative_cases,
)


def test_stage9081_base_audit_passes() -> None:
    audit = build_audit()
    assert audit["passed"] is True
    assert audit["base_failures"] == []
    assert audit["checks"]["instance_closed_now"] is True
    assert audit["checks"]["authority_closed"] is True


def test_stage9081_rejects_negative_cases() -> None:
    negatives = run_negative_cases()
    assert negatives
    assert all(item["rejected"] for item in negatives.values())
    assert "route_cards_materialized_now" in negatives["route_cards_materialized_now"]["failures"]
    assert "compiler_handoff_ready_now" in negatives["compiler_handoff_ready_now"]["failures"]
    assert "template_opened_current_operation" in negatives["template_closed_now_open"]["failures"]
    assert "authority_open" in negatives["authority_open_model_execution"]["failures"]


def test_stage9081_keeps_current_operations_closed() -> None:
    audit = build_audit()
    metrics = audit["metrics"]
    assert metrics["instance_instantiated_now"] is False
    assert metrics["source_output_ticket_instantiated_now"] is False
    assert metrics["source_metadata_read_now"] is False
    assert metrics["route_cards_materialized_now"] is False
    assert metrics["candidate_rows_materialized"] == 0
    assert metrics["training_authorized"] is False
    assert not any(audit["authority"].values())
