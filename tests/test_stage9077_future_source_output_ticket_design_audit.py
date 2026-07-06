from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9077_future_source_output_ticket_design_audit import (  # noqa: E402
    build_audit,
    run_negative_cases,
)


def test_stage9077_base_audit_passes() -> None:
    audit = build_audit()
    assert audit["passed"] is True
    assert audit["base_failures"] == []
    assert audit["checks"]["arxiv_never_delete_recorded"] is True
    assert audit["checks"]["body_access_blocked"] is True


def test_stage9077_rejects_negative_cases() -> None:
    negatives = run_negative_cases()
    assert negatives
    assert all(item["rejected"] for item in negatives.values())
    assert "source_metadata_read_now" in negatives["source_metadata_read_now"]["failures"]
    assert "missing_never_delete_arxiv" in negatives["missing_never_delete_arxiv"]["failures"]
    assert "authority_open" in negatives["authority_open_model_execution"]["failures"]


def test_stage9077_keeps_all_access_closed() -> None:
    audit = build_audit()
    metrics = audit["metrics"]
    assert metrics["ticket_instantiated_now"] is False
    assert metrics["source_metadata_read_now"] is False
    assert metrics["route_cards_materialized_now"] is False
    assert metrics["candidate_rows_materialized"] == 0
    assert metrics["training_authorized"] is False
    assert not any(audit["authority"].values())
