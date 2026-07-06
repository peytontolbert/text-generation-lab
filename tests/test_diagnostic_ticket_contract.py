from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.diagnostic_ticket_contract import (
    AUTHORITY_CLOSED,
    apply_diagnostic_gate_fields,
    audit_diagnostic_ticket_fields,
    diagnostic_gate_fields,
)


def test_diagnostic_gate_fields_are_canonical() -> None:
    fields = diagnostic_gate_fields()
    assert fields["post_run_diagnostic_gate_required"] is True
    assert fields["post_run_diagnostic_gate_stage"] == "stage8902_diagnostic_promotion_gate"
    assert fields["post_run_artifact_contract_stage"] == "stage8862_native_probe_interpretability_artifact_contract"
    assert fields["diagnostic_closure_stage"] == "stage8903_diagnostics_closure_audit"
    assert fields["promotion_blocked_until_diagnostics_pass"] is True
    assert fields["metrics_interpretation_blocked_until_diagnostics_pass"] is True


def test_apply_diagnostic_gate_fields_makes_ticket_pass_contract() -> None:
    ticket = apply_diagnostic_gate_fields({
        "ticket_status": "TEMPLATE_ONLY_INACTIVE",
        "execution_authorized_now": False,
        "allowed_operations_now": [],
        "authority": AUTHORITY_CLOSED,
    })
    assert audit_diagnostic_ticket_fields(ticket) == []


def test_contract_rejects_ticket_missing_gate_fields() -> None:
    failures = audit_diagnostic_ticket_fields({"authority": AUTHORITY_CLOSED})
    assert "missing:post_run_diagnostic_gate_required" in failures
    assert "post_run_diagnostic_gate_not_required" in failures


def test_contract_rejects_open_authority() -> None:
    ticket = apply_diagnostic_gate_fields({"authority": {**AUTHORITY_CLOSED, "runtime_authorized": True}})
    failures = audit_diagnostic_ticket_fields(ticket)
    assert "authority_open" in failures
