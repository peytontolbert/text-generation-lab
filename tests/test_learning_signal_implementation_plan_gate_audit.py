from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.learning_signal_contract_builder import build_learning_signal_rows
from scripts.learning_signal_implementation_plan_builder import build_plan_rows
from scripts.learning_signal_implementation_plan_gate_audit import audit_plan_rows


def test_plan_gate_passes_complete_closed_plan() -> None:
    rows = build_plan_rows(build_learning_signal_rows())
    audit = audit_plan_rows(rows)
    assert audit["passed"] is True
    assert audit["missing_plan_id_count"] == 0
    assert audit["missing_file_count"] == 0
    assert audit["training_authorized"] is False


def test_plan_gate_catches_missing_acceptance_checks() -> None:
    rows = build_plan_rows(build_learning_signal_rows())
    rows[0]["acceptance_checks"] = []
    audit = audit_plan_rows(rows)
    assert audit["passed"] is False
    assert audit["missing_acceptance_rows"] == 1
