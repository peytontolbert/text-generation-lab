from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8956_bounded_decoder_future_one_run_authorization_schema import (  # noqa: E402
    AUTHORITY_CLOSED,
    DENIED_NOW_OPERATIONS,
    FUTURE_AUTHORIZATION_REQUIREMENTS,
    REQUIRED_LIMITS,
    audit_ticket,
    build_inactive_ticket,
)


def registry(latest: int = 8955) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage8956_ticket_is_inactive_and_diagnostic_gated() -> None:
    ticket = build_inactive_ticket()
    audit = audit_ticket(ticket, registry())
    assert audit["passed"] is True
    assert ticket["ticket_status"] == "TEMPLATE_ONLY_INACTIVE"
    assert ticket["requested_capability"] == "tiny_bounded_decoder_ce_probe"
    assert ticket["execution_authorized_now"] is False
    assert ticket["command_materialized"] is False
    assert ticket["allowed_operations_now"] == []
    assert ticket["post_run_diagnostic_gate_required"] is True
    assert ticket["authority"] == AUTHORITY_CLOSED


def test_stage8956_ticket_records_bounded_decoder_ce_caps_without_granting_execution() -> None:
    ticket = build_inactive_ticket()
    assert ticket["required_limits"] == REQUIRED_LIMITS
    assert ticket["required_limits"]["mode"] == "bounded_decoder_ce_probe"
    assert ticket["required_limits"]["max_train_rows"] == 32
    assert ticket["required_limits"]["max_eval_rows"] == 16
    assert ticket["required_limits"]["max_strict_rows"] == 16
    assert ticket["required_limits"]["decoder_ce_weight"] == 1.0
    assert ticket["required_limits"]["denoise_weight"] == 0.0


def test_stage8956_ticket_denies_all_operations_now_and_requires_future_gates() -> None:
    ticket = build_inactive_ticket()
    for operation in DENIED_NOW_OPERATIONS:
        assert operation in ticket["denied_operations_now"]
    for requirement in FUTURE_AUTHORIZATION_REQUIREMENTS:
        assert requirement in ticket["future_authorization_requirements"]
    assert "telemetry_gate_stage8955_required" in ticket["future_authorization_requirements"]
    assert "post_run_stage8902_diagnostics_required" in ticket["future_authorization_requirements"]


def test_stage8956_audit_rejects_execution_or_limit_drift() -> None:
    ticket = build_inactive_ticket()
    ticket["execution_authorized_now"] = True
    audit = audit_ticket(ticket, registry())
    assert audit["passed"] is False
    assert "execution_authorized_now_not_false" in audit["failures"]
    bad = build_inactive_ticket()
    bad["required_limits"]["max_steps"] = 200
    bad_audit = audit_ticket(bad, registry())
    assert bad_audit["passed"] is False
    assert "limit_mismatch:max_steps" in bad_audit["failures"]
    assert "unexpected_registry_frontier:9999" in audit_ticket(build_inactive_ticket(), registry(latest=9999))["failures"]
