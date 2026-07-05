from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from latency_resource_observability import observability_card, observe_resource_row


def test_passes_low_resource_row() -> None:
    record = observe_resource_row({"row_id": "ok", "usage": {"latency_ms": 100, "memory_peak_mb": 64, "token_count": 100, "tool_cost": 1}})
    assert record["resource_route"] == "PASS_RESOURCE_OBSERVABILITY"
    assert record["authority"]["runtime_authorized"] is False


def test_warns_near_budget() -> None:
    record = observe_resource_row({"row_id": "warn", "usage": {"latency_ms": 900}}, limits={"latency_ms": 1000})
    assert record["resource_route"] == "HOLD_RESOURCE_BUDGET_WARNING"
    assert record["warnings"] == ["latency_ms"]


def test_blocks_budget_violation() -> None:
    record = observe_resource_row({"row_id": "block", "usage": {"token_count": 1200}}, limits={"token_count": 1000})
    assert record["resource_route"] == "BLOCK_RESOURCE_BUDGET_VIOLATION"
    assert record["budget_violation"] is True
    assert record["violations"] == ["token_count"]


def test_observability_card_counts_routes_and_aggregates() -> None:
    card = observability_card(
        [
            {"row_id": "ok", "usage": {"latency_ms": 100, "token_count": 100}},
            {"row_id": "warn", "usage": {"latency_ms": 900, "token_count": 100}},
            {"row_id": "block", "usage": {"latency_ms": 1100, "token_count": 1200}},
        ],
        limits={"latency_ms": 1000, "token_count": 1000},
    )
    assert card["metrics"]["pass_rows"] == 1
    assert card["metrics"]["warning_rows"] == 1
    assert card["metrics"]["blocked_rows"] == 1
    assert card["metrics"]["budget_violation_rows"] == 1
    assert card["metrics"]["authority_rows"] == 0
    assert card["metrics"]["max_token_count"] == 1200
