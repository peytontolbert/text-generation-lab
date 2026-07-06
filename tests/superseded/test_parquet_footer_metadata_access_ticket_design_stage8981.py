from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8981_parquet_footer_metadata_access_ticket_design import (  # noqa: E402
    ALLOWED_PROBE_TYPES,
    AUTHORITY_CLOSED,
    FORBIDDEN_OPERATIONS,
    REQUIRED_TICKET_FIELDS,
    build_design,
    ticket_design,
    validate_design,
)


def registry(latest: int = 8980) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage8981_ticket_schema_is_explicit_but_not_granted() -> None:
    ticket = ticket_design()
    for field in REQUIRED_TICKET_FIELDS:
        assert field in ticket
    assert ALLOWED_PROBE_TYPES == ["PARQUET_FOOTER_SCHEMA_METADATA_ONLY"]
    assert ticket["ticket_granted_now"] is False
    assert ticket["footer_access_authorized_now"] is False


def test_stage8981_forbids_row_body_write_training_and_runtime_paths() -> None:
    for item in ["DATASET_ROW_SCAN", "REPOSITORY_SOURCE_BODY_READ", "ARXIV_WRITE", "TRAINING", "MINING", "MODEL_EXECUTION"]:
        assert item in FORBIDDEN_OPERATIONS
    card = build_design(registry())
    assert card["metrics"]["parquet_footer_read_performed"] is False
    assert card["metrics"]["dataset_rows_loaded"] is False
    assert card["metrics"]["training_authorized"] is False
    assert all(value is False for value in card["authority"].values())


def test_stage8981_validation_rejects_granted_ticket_or_bad_frontier() -> None:
    card = build_design(registry())
    assert validate_design(card, registry()) == []
    bad = build_design(registry())
    bad["metrics"]["footer_access_authorized_now"] = True
    assert "footer_access_authorized_now" in validate_design(bad, registry())
    bad_authority = build_design(registry())
    bad_authority["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_design(bad_authority, registry())
    assert "unexpected_registry_frontier:9999" in validate_design(card, registry(9999))
