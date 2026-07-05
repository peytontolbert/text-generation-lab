from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_stage8900_verified_transition_record_validation_contract import (
    AUTHORITY_CLOSED,
    FORBIDDEN_VISIBLE_FIELDS,
    REQUIRED_FIELDS,
    REQUIRED_GATE_KEYS,
    example_record,
    validate_record,
)


def test_example_record_is_complete_closed_schema_only() -> None:
    record = example_record()
    assert set(REQUIRED_FIELDS).issubset(record)
    assert set(REQUIRED_GATE_KEYS).issubset(record["gate_status"])
    assert record["authority"] == AUTHORITY_CLOSED
    assert not any(record["loss_mask"].values())
    assert validate_record(record)["passed"] is True


def test_forbidden_visible_field_fails_validation() -> None:
    record = example_record()
    record["anti_cheat"][FORBIDDEN_VISIBLE_FIELDS[0]] = True
    audit = validate_record(record)
    assert audit["passed"] is False
    assert "forbidden_visible_fields" in audit["failures"]


def test_runtime_or_loss_open_fails_validation() -> None:
    record = example_record()
    record["verifier_result"]["runtime_executed"] = True
    record["loss_mask"]["decoder_ce"] = True
    audit = validate_record(record)
    assert audit["passed"] is False
    assert "runtime_open" in audit["failures"]
    assert "loss_open" in audit["failures"]
