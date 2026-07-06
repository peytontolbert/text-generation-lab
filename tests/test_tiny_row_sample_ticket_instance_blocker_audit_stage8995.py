from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8995_tiny_row_sample_ticket_instance_blocker_audit import (  # noqa: E402
    AUTHORITY_CLOSED,
    REQUIRED_PREREQUISITES,
    build_audit,
    validate_audit,
)


def registry() -> dict[str, object]:
    return {"metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage8995_records_blocked_row_sample_instance() -> None:
    card = build_audit(registry())
    assert len(REQUIRED_PREREQUISITES) >= 8
    assert card["metrics"]["row_sample_ticket_instance_ready"] is False
    assert card["metrics"]["row_sample_authorized_now"] is False
    assert card["metrics"]["dataset_rows_loaded"] is False
    assert card["metrics"]["missing_prerequisites"] > 0


def test_stage8995_validation_requires_blocker_and_closed_authority() -> None:
    card = build_audit(registry())
    assert validate_audit(card) == []
    no_block = build_audit(registry())
    no_block["metrics"]["missing_prerequisites"] = 0
    assert "missing_prerequisites_not_recorded" in validate_audit(no_block)
    opened = build_audit(registry())
    opened["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_audit(opened)


def test_stage8995_validation_rejects_any_row_sampling_or_training() -> None:
    card = build_audit(registry())
    card["metrics"]["row_sample_executed_now"] = True
    assert "row_sample_executed_now" in validate_audit(card)
    train = build_audit(registry())
    train["metrics"]["training_authorized"] = True
    assert "training_authorized" in validate_audit(train)
