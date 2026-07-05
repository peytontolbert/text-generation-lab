from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_stage8896_next_stage_allocation_preflight import AUTHORITY_CLOSED, allocation_preflight, next_free_stage


def registry(rows: list[dict], latest: int) -> dict:
    return {"rows": rows, "metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_next_free_stage_skips_used_and_reserved() -> None:
    assert next_free_stage({8890, 8891, 8892}, start=8890) == 8893


def test_allocation_preflight_allocates_after_current_stage() -> None:
    card = allocation_preflight(
        registry([
            {"stage": 8894, "stage_name": "stage8894_a"},
            {"stage": 8895, "stage_name": "stage8895_b"},
        ], latest=8895),
        current_stage=8896,
    )
    assert card["passed"] is True
    assert card["allocated_next_free_stage"] == 8897
    assert card["occupied_reserved_stages"] == []


def test_allocation_preflight_rejects_reserved_stage_occupancy() -> None:
    card = allocation_preflight(
        registry([
            {"stage": 8890, "stage_name": "stage8890_live"},
            {"stage": 8895, "stage_name": "stage8895_b"},
        ], latest=8895),
        current_stage=8896,
    )
    assert card["passed"] is False
    assert "reserved_stage_occupied:8890" in card["failures"]
