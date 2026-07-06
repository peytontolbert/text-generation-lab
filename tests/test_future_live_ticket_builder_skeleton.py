from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8913_future_live_ticket_builder_skeleton import (  # noqa: E402
    AUTHORITY_CLOSED,
    REQUIRED_LIMITS,
    audit_ticket,
    build_inactive_future_ticket,
)


def registry(latest: int = 8911) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_future_live_ticket_skeleton_is_inactive_and_diagnostic_gated() -> None:
    ticket = build_inactive_future_ticket()
    audit = audit_ticket(ticket, registry())
    assert audit["passed"] is True
    assert ticket["ticket_status"] == "TEMPLATE_ONLY_INACTIVE"
    assert ticket["execution_authorized_now"] is False
    assert ticket["allowed_operations_now"] == []
    assert ticket["command_materialized"] is False
    assert ticket["post_run_diagnostic_gate_required"] is True
    assert ticket["required_limits"] == REQUIRED_LIMITS
    assert ticket["authority"] == AUTHORITY_CLOSED


def test_future_live_ticket_skeleton_rejects_open_execution() -> None:
    ticket = build_inactive_future_ticket()
    ticket["execution_authorized_now"] = True
    audit = audit_ticket(ticket, registry())
    assert audit["passed"] is False
    assert "execution_authorized_now_not_false" in audit["failures"]


def test_future_live_ticket_skeleton_rejects_decoder_ce_limit_change() -> None:
    ticket = build_inactive_future_ticket()
    ticket["required_limits"]["decoder_ce_weight"] = 1.0
    audit = audit_ticket(ticket, registry())
    assert audit["passed"] is False
    assert "limit_mismatch:decoder_ce_weight" in audit["failures"]
