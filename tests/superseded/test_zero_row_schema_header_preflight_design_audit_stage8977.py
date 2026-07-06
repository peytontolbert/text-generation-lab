from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8977_zero_row_schema_header_preflight_design_audit import (  # noqa: E402
    AUTHORITY_CLOSED,
    REQUIRED_FORBIDDEN_ACTIONS,
    build_audit,
    validate_audit,
)


def registry(latest: int = 8976) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage8977_audits_exact_stage8976_artifacts() -> None:
    card = build_audit(registry())
    assert card["source_stage_name"] == "stage8976_zero_row_schema_header_preflight_design"
    assert card["metrics"]["selected_rows"] >= 6
    assert "PARQUET_TABLE_CANDIDATE" in card["selected_routes"]
    assert ".parquet" in card["selected_extensions"]


def test_stage8977_forbidden_actions_cover_row_reads_and_training() -> None:
    card = build_audit(registry())
    for check in REQUIRED_FORBIDDEN_ACTIONS:
        assert check in card["checks"] or card["checks"]["forbidden_actions_cover_row_reads"] is True
    assert card["metrics"]["schema_probe_executed_now"] is False
    assert card["metrics"]["training_authorized"] is False


def test_stage8977_validation_rejects_open_authority_or_bad_frontier() -> None:
    card = build_audit(registry())
    assert validate_audit(card, registry()) == []
    bad = build_audit(registry())
    bad["metrics"]["header_probe_executed_now"] = True
    assert "header_probe_executed_now" in validate_audit(bad, registry())
    bad_authority = build_audit(registry())
    bad_authority["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_audit(bad_authority, registry())
    assert "unexpected_registry_frontier:9999" in validate_audit(card, registry(9999))
