from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage9038_long_context_no_data_scan_ticket import (  # noqa: E402
    AUTHORITY_CLOSED,
    FORBIDDEN_ROOTS_BY_DEFAULT,
    REQUIRED_OUTPUTS,
    build_ticket,
    validate_ticket,
)


def registry() -> dict[str, object]:
    return {"metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9038_forbids_corpus_roots_by_default() -> None:
    card = build_ticket(registry())
    ticket = card["ticket_template"]
    for root in ["/arxiv", "/arxiv/datasets", "/arxiv/repositories", "/data/repository_library"]:
        assert root in FORBIDDEN_ROOTS_BY_DEFAULT
        assert root in ticket["forbidden_roots"]
    assert ticket["mode"] == "synthetic_fixture_only_by_default"


def test_stage9038_records_required_outputs_and_quality_gates() -> None:
    card = build_ticket(registry())
    assert set(REQUIRED_OUTPUTS).issubset(set(card["ticket_template"]["required_outputs"]))
    assert "source_inventory_exists" in card["ticket_template"]["quality_gates"]
    assert "single_chunk_shortcut_audited" in card["ticket_template"]["quality_gates"]
    assert "no_training_rows_exported" in card["ticket_template"]["quality_gates"]
    assert validate_ticket(card) == []


def test_stage9038_keeps_pipeline_execution_and_training_closed() -> None:
    card = build_ticket(registry())
    assert card["metrics"]["ticket_contract_only"] is True
    assert card["metrics"]["long_context_pipeline_executed_now"] is False
    assert card["metrics"]["arxiv_scan_authorized_now"] is False
    assert card["metrics"]["repository_library_scan_authorized_now"] is False
    assert card["metrics"]["training_rows_materialized_now"] is False
    assert card["metrics"]["training_authorized"] is False
    assert card["metrics"]["data_mining_authorized"] is False
    assert all(value is False for value in card["authority"].values())
    assert all(value is False for value in card["ticket_template"]["authority"].values())


def test_stage9038_validation_rejects_open_ticket_authority_or_execution() -> None:
    opened = build_ticket(registry())
    opened["ticket_template"]["authority"]["runtime_authorized"] = True
    assert "ticket_authority_open" in validate_ticket(opened)
    unsafe = build_ticket(registry())
    unsafe["metrics"]["long_context_pipeline_executed_now"] = True
    assert "long_context_pipeline_executed_now" in validate_ticket(unsafe)
