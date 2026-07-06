from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8906_diagnostic_gate_ticket_integration import (  # noqa: E402
    AUTHORITY_CLOSED,
    FORBIDDEN_WITHOUT_DIAGNOSTICS,
    audit_ticket_template,
    build_future_ticket_template,
)


def passing_sources() -> list[dict[str, object]]:
    return [{"stage_name": "source", "passed": True, "authority": AUTHORITY_CLOSED} for _ in range(4)]


def registry() -> dict[str, object]:
    return {"metrics": {"latest_stage": 8905, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_future_ticket_requires_post_run_diagnostic_gate() -> None:
    ticket = build_future_ticket_template()
    audit = audit_ticket_template(ticket, passing_sources(), registry())
    assert audit["passed"] is True
    assert ticket["ticket_status"] == "TEMPLATE_ONLY_INACTIVE"
    assert ticket["execution_authorized_now"] is False
    assert ticket["allowed_operations_now"] == []
    assert ticket["post_run_diagnostic_gate_required"] is True
    assert ticket["post_run_diagnostic_gate_stage"] == "stage8902_diagnostic_promotion_gate"
    assert ticket["post_run_artifact_contract_stage"] == "stage8862_native_probe_interpretability_artifact_contract"
    assert ticket["promotion_blocked_until_diagnostics_pass"] is True
    assert ticket["metrics_interpretation_blocked_until_diagnostics_pass"] is True
    assert set(ticket["forbidden_without_passing_diagnostics"]) == set(FORBIDDEN_WITHOUT_DIAGNOSTICS)
    assert all(value is False for value in ticket["authority"].values())


def test_ticket_audit_rejects_missing_diagnostic_gate_requirement() -> None:
    ticket = build_future_ticket_template()
    ticket["post_run_diagnostic_gate_required"] = False
    audit = audit_ticket_template(ticket, passing_sources(), registry())
    assert audit["passed"] is False
    assert "post_run_diagnostic_gate_not_required" in audit["failures"]


def test_ticket_audit_rejects_open_authority() -> None:
    ticket = build_future_ticket_template()
    ticket["authority"] = copy.deepcopy(ticket["authority"])
    ticket["authority"]["model_execution_authorized_next"] = True
    audit = audit_ticket_template(ticket, passing_sources(), registry())
    assert audit["passed"] is False
    assert "ticket_authority_open" in audit["failures"]


def test_ticket_audit_rejects_metrics_interpretation_without_diagnostics_block() -> None:
    ticket = build_future_ticket_template()
    ticket["metrics_interpretation_blocked_until_diagnostics_pass"] = False
    audit = audit_ticket_template(ticket, passing_sources(), registry())
    assert audit["passed"] is False
    assert "metrics_interpretation_not_blocked_until_diagnostics" in audit["failures"]


def test_stage8906_summary_and_template_exist_after_builder_run() -> None:
    summary = ROOT / "runs/summaries/stage8906_diagnostic_gate_ticket_integration.json"
    template = ROOT / "runs/local/artifacts/stage8906_diagnostic_gate_ticket_integration/future_live_probe_ticket_diagnostic_gate_template.json"
    if not summary.exists() or not template.exists():
        return
    card = json.loads(summary.read_text(encoding="utf-8"))
    tpl = json.loads(template.read_text(encoding="utf-8"))
    assert card["passed"] is True
    assert tpl["post_run_diagnostic_gate_required"] is True
    assert card["metrics"]["model_execution_authorized_now"] is False
