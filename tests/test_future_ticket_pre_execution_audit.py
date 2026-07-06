from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8913_future_live_ticket_builder_skeleton import build_inactive_future_ticket  # noqa: E402
from scripts.build_stage8915_future_ticket_pre_execution_audit import (  # noqa: E402
    AUTHORITY_CLOSED,
    audit_pre_execution_ticket,
    run_negative_mutation_checks,
)


def test_pre_execution_audit_accepts_inactive_ticket_template() -> None:
    ticket = build_inactive_future_ticket()
    assert audit_pre_execution_ticket(ticket) == []


def test_pre_execution_audit_rejects_all_negative_mutations() -> None:
    ticket = build_inactive_future_ticket()
    results = run_negative_mutation_checks(ticket)
    assert results
    assert all(result["rejected"] for result in results.values())


def test_pre_execution_audit_rejects_command_materialization() -> None:
    ticket = build_inactive_future_ticket()
    ticket["command_materialized"] = True
    failures = audit_pre_execution_ticket(ticket)
    assert "command_materialized_not_false" in failures


def test_pre_execution_audit_rejects_missing_denied_operation() -> None:
    ticket = build_inactive_future_ticket()
    ticket["denied_operations"] = [op for op in ticket["denied_operations"] if op != "run_forward"]
    failures = audit_pre_execution_ticket(ticket)
    assert any(failure.startswith("missing_denied_operations") for failure in failures)


def test_stage8915_summary_if_present_keeps_authority_closed() -> None:
    summary = ROOT / "runs/summaries/stage8915_future_ticket_pre_execution_audit.json"
    if not summary.exists():
        return
    card = json.loads(summary.read_text(encoding="utf-8"))
    assert card["passed"] is True
    assert card["authority"] == AUTHORITY_CLOSED
    assert card["metrics"]["negative_mutations_rejected"] == card["metrics"]["negative_mutations"]
