from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from cost_budget_scheduler import schedule, schedule_rows


def test_retrieves_when_evidence_missing_and_budget_ok() -> None:
    record = schedule({"row_id": "r", "used": {"tokens": 100, "tool_calls": 1}, "has_evidence": False})
    assert record["budget_route"] == "RETRIEVE_MORE_WITHIN_BUDGET"


def test_stops_when_exhausted() -> None:
    record = schedule({"row_id": "r", "used": {"tokens": 20000}}, limits={"token_budget": 1000})
    assert record["budget_route"] == "STOP_BUDGET_EXHAUSTED"
    assert record["decoder_budget_ok"] is False


def test_holds_critical_budget_without_passed_tests() -> None:
    record = schedule({"row_id": "r", "used": {"tokens": 900}}, limits={"token_budget": 1000})
    assert record["budget_route"] == "HOLD_BUDGET_REVIEW"


def test_stops_verified_within_budget() -> None:
    record = schedule({"row_id": "r", "used": {"tokens": 200}, "has_evidence": True, "tests_passed": True})
    assert record["budget_route"] == "STOP_VERIFIED_WITHIN_BUDGET"


def test_retrieves_on_high_uncertainty_when_budget_ok() -> None:
    record = schedule({"row_id": "r", "used": {"tokens": 200}, "has_evidence": True, "uncertainty": 0.9})
    assert record["budget_route"] == "RETRIEVE_OR_INSPECT_MORE"


def test_manifest_counts() -> None:
    card = schedule_rows([
        {"row_id": "a", "used": {"tokens": 1}, "has_evidence": False},
        {"row_id": "b", "used": {"tokens": 20000}},
        {"row_id": "c", "used": {"tokens": 1}, "has_evidence": True, "tests_passed": True},
    ], limits={"token_budget": 1000})
    assert card["metrics"]["retrieve_rows"] == 1
    assert card["metrics"]["stop_rows"] == 2
