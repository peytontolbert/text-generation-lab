from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_stage8894_registry_frontier_collision_guard import AUTHORITY_CLOSED, frontier_collision_audit


def registry(rows: list[dict], latest: int = 8893) -> dict:
    return {"rows": rows, "metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_frontier_collision_audit_accepts_unique_recent_stages() -> None:
    card = frontier_collision_audit(
        registry([
            {"stage": 8888, "stage_name": "stage8888_a"},
            {"stage": 8889, "stage_name": "stage8889_b"},
            {"stage": 8891, "stage_name": "stage8891_c"},
            {"stage": 8893, "stage_name": "stage8893_d"},
        ]),
        current_stage=8894,
    )
    assert card["passed"] is True
    assert card["duplicate_stage_numbers"] == {}
    assert card["reserved_stage_rows"] == {}


def test_frontier_collision_audit_catches_duplicate_recent_stage() -> None:
    card = frontier_collision_audit(
        registry([
            {"stage": 8892, "stage_name": "stage8892_a"},
            {"stage": 8892, "stage_name": "stage8892_b"},
            {"stage": 8893, "stage_name": "stage8893_c"},
        ]),
        current_stage=8894,
    )
    assert card["passed"] is False
    assert "duplicate_protected_stage_numbers" in card["failures"]


def test_frontier_collision_audit_keeps_reserved_8890_empty() -> None:
    card = frontier_collision_audit(
        registry([
            {"stage": 8890, "stage_name": "stage8890_live_run"},
            {"stage": 8893, "stage_name": "stage8893_c"},
        ]),
        current_stage=8894,
    )
    assert card["passed"] is False
    assert "reserved_unrun_stage_materialized" in card["failures"]
