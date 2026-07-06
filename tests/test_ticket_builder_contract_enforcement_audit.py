from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8911_ticket_builder_contract_enforcement_audit import build_audit  # noqa: E402
from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # noqa: E402


def registry(latest: int = 8909) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_builder_contract_enforcement_audit_passes_with_current_surfaces() -> None:
    audit = build_audit(registry())
    assert audit["passed"] is True
    assert audit["failures"] == []
    canonical = [s for s in audit["surface_statuses"] if s["allowed_future_use"] == "canonical"]
    assert len(canonical) == 1
    assert canonical[0]["contract_compliant_for_future_use"] is True


def test_builder_contract_enforcement_audit_rejects_bad_registry_frontier() -> None:
    audit = build_audit(registry(1))
    assert audit["passed"] is False
    assert "unexpected_registry_frontier:1" in audit["failures"]


def test_legacy_builders_are_historical_only() -> None:
    audit = build_audit(registry())
    legacy = [s for s in audit["surface_statuses"] if s["allowed_future_use"] == "historical_reference_only"]
    assert legacy
    assert all(s["contract_compliant_for_future_use"] is False for s in legacy)
