from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from curriculum_compiler import REQUIRED_RECOVERED_GATE_REFERENCES
from gate_status_contract import default_gate_status, failed_gate_names, gate_status_card, passed_gate_status


def test_default_gate_status_is_complete_and_blocking() -> None:
    status = default_gate_status()
    assert set(status) == set(REQUIRED_RECOVERED_GATE_REFERENCES)
    assert all(value is False for value in status.values())
    assert failed_gate_names(status) == REQUIRED_RECOVERED_GATE_REFERENCES


def test_passed_gate_status_can_override_known_gate() -> None:
    status = passed_gate_status(schema_drift_detector=False)
    assert status["source_inventory_lineage"] is True
    assert status["schema_drift_detector"] is False
    assert failed_gate_names(status) == ["schema_drift_detector"]


def test_unknown_gate_override_fails_closed() -> None:
    with pytest.raises(KeyError):
        default_gate_status(not_a_real_gate=True)


def test_gate_status_card_reports_incomplete_rows() -> None:
    card = gate_status_card(
        [
            {"row_id": "clean", "gate_status": passed_gate_status()},
            {"row_id": "missing"},
            {"row_id": "schema_block", "gate_status": passed_gate_status(schema_drift_detector=False)},
        ]
    )
    assert card["rows"] == 3
    assert card["complete_gate_status_rows"] == 2
    assert card["incomplete_gate_status_rows"] == 1
    assert card["failed_gate_counts"]["schema_drift_detector"] == 2
