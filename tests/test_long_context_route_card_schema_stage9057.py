from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage9057_long_context_route_card_schema_contract import (  # noqa: E402
    LOSS_KEYS,
    REQUIRED_FIELDS,
    REQUIRED_GATE_FIELDS,
    audit_contract,
    build_schema_contract,
)


def test_stage9057_schema_contract_is_closed_by_default() -> None:
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/build_stage9056_long_context_synthetic_route_card_audit.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    contract = build_schema_contract()
    assert audit_contract(contract) == []
    assert set(REQUIRED_FIELDS).issubset(set(contract["required_fields"]))
    assert set(REQUIRED_GATE_FIELDS).issubset(set(contract["required_gate_fields"]))
    assert set(contract["loss_keys"]) == set(LOSS_KEYS)
    assert all(value is False for value in contract["closed_default_loss_mask"].values())


def test_stage9057_rejects_open_default_loss() -> None:
    contract = build_schema_contract()
    contract["closed_default_loss_mask"]["decoder_ce"] = True
    assert "default_loss_open" in audit_contract(contract)


def test_stage9057_builder_materializes_schema_only_summary() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/build_stage9057_long_context_route_card_schema_contract.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    summary = json.loads(result.stdout)
    assert summary["passed"] is True
    assert summary["metrics"]["schema_only_no_rows"] is True
    assert summary["metrics"]["route_rows_materialized_now"] is False
    assert summary["metrics"]["training_authorized"] is False
