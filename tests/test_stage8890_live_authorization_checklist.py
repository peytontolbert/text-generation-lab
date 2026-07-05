from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_stage8895_stage8890_live_authorization_checklist import (
    AUTHORITY_CLOSED,
    FORBIDDEN_AT_LIVE_STAGE,
    REQUIRED_AFTER_RUN_ARTIFACTS,
    REQUIRED_STAGE8890_LIMITS,
    SOURCE_SUMMARIES,
    build_checklist,
)


def closed_source_cards() -> dict[str, dict]:
    return {key: {"passed": True, "authority": dict(AUTHORITY_CLOSED)} for key in SOURCE_SUMMARIES}


def registry(latest: int = 8894, rows: list[dict] | None = None) -> dict:
    return {
        "rows": rows or [{"stage": 8894, "stage_name": "stage8894_registry_frontier_collision_guard"}],
        "metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}},
    }


def test_checklist_records_no_live_authority_and_required_limits() -> None:
    built = build_checklist(registry(), closed_source_cards())
    assert built["failures"] == []
    checklist = built["checklist"]
    assert checklist["status"] == "NO_LIVE_AUTHORITY_CHECKLIST_ONLY"
    assert checklist["live_authorization_created_now"] is False
    assert checklist["required_stage8890_limits"] == REQUIRED_STAGE8890_LIMITS
    assert checklist["required_stage8890_limits"]["decoder_ce_weight"] == 0.0
    assert checklist["required_stage8890_limits"]["denoise_weight"] == 0.0
    assert checklist["required_stage8890_limits"]["runtime"] is False
    assert "module_delta_norms.json" in checklist["required_after_run_artifacts"]
    assert set(REQUIRED_AFTER_RUN_ARTIFACTS).issubset(set(checklist["required_after_run_artifacts"]))
    assert set(FORBIDDEN_AT_LIVE_STAGE).issubset(set(checklist["forbidden_at_live_stage"]))


def test_checklist_fails_if_stage8890_is_already_materialized() -> None:
    built = build_checklist(registry(rows=[{"stage": 8890, "stage_name": "stage8890_live_run"}]), closed_source_cards())
    assert "stage8890_already_materialized" in built["failures"]


def test_checklist_fails_if_source_authority_opens() -> None:
    cards = closed_source_cards()
    cards["inactive_ticket_gate"]["authority"]["model_execution_authorized_next"] = True
    built = build_checklist(registry(), cards)
    assert "source_authority_open:inactive_ticket_gate" in built["failures"]
