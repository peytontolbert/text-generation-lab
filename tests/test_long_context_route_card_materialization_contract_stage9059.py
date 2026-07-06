from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage9059_long_context_route_card_materialization_audit_contract import (  # noqa: E402
    audit_route_card,
    build_audit,
    run_negative_cases,
    sample_closed_card,
)


def test_stage9059_closed_sample_passes_and_negative_cases_reject() -> None:
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/build_stage9058_long_context_route_card_schema_graph_attachment.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    assert audit_route_card(sample_closed_card()) == []
    negatives = run_negative_cases()
    assert all(item["rejected"] for item in negatives.values())
    assert "loss_open" in negatives["open_decoder_ce"]["failures"]
    assert "compiler_ready_without_all_gates" in negatives["compiler_ready_without_gates"]["failures"]


def test_stage9059_build_audit_is_no_materialization() -> None:
    audit = build_audit()
    assert audit["passed"] is True
    assert audit["checks"]["route_rows_not_materialized"] is True
    assert audit["metrics"]["route_rows_materialized_now"] is False
    assert audit["metrics"]["training_authorized"] is False


def test_stage9059_builder_materializes_closed_summary() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/build_stage9059_long_context_route_card_materialization_audit_contract.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    summary = json.loads(result.stdout)
    assert summary["passed"] is True
    assert summary["metrics"]["route_rows_materialized_now"] is False
    assert summary["metrics"]["training_authorized"] is False
