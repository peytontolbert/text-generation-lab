from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage9052_long_context_source_output_ticket_design import (  # noqa: E402
    DENIED_OPERATIONS,
    REQUIRED_CAPS,
    audit_ticket,
    build_inactive_ticket,
)
from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # noqa: E402


def registry() -> dict[str, object]:
    return {"metrics": {"latest_stage": 9051, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9052_inactive_ticket_denies_real_data_ops() -> None:
    ticket = build_inactive_ticket()
    audit = audit_ticket(ticket, registry())
    assert audit["passed"] is True
    assert ticket["ticket_status"] == "TEMPLATE_ONLY_INACTIVE"
    assert ticket["ticket_granted_now"] is False
    assert ticket["command_materialized"] is False
    assert ticket["allowed_operations_now"] == []
    assert set(DENIED_OPERATIONS).issubset(set(ticket["denied_operations"]))
    assert ticket["required_caps"] == REQUIRED_CAPS


def test_stage9052_rejects_opened_candidate_mining_or_caps() -> None:
    ticket = build_inactive_ticket()
    ticket["allowed_operations_now"] = ["run_candidate_mining"]
    assert "allowed_operations_now_not_empty" in audit_ticket(ticket, registry())["failures"]

    ticket = build_inactive_ticket()
    ticket["required_caps"]["max_candidates"] = 10
    assert "cap_mismatch:max_candidates" in audit_ticket(ticket, registry())["failures"]


def test_stage9052_builder_materializes_closed_summary() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/build_stage9052_long_context_source_output_ticket_design.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    summary = json.loads(result.stdout)
    assert summary["passed"] is True
    assert summary["metrics"]["corpus_scan_authorized_now"] is False
    assert summary["metrics"]["candidate_mining_authorized_now"] is False
    assert summary["metrics"]["arxiv_write_authorized"] is False
