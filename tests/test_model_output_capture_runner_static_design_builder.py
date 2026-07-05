from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.model_output_capture_runner_static_design_builder import (
    REQUIRED_RUNNER_ASSERTIONS,
    REQUIRED_RUNNER_FLAGS,
    build_card,
    build_runner_design_rows,
)


def preflight_row() -> dict:
    return {
        "row_id": "preflight_a",
        "split": "eval",
        "capture_contract": {"writes_model_output_artifact_now": False},
    }


def test_runner_design_rows_are_static_and_closed() -> None:
    rows = build_runner_design_rows([preflight_row()])
    assert len(rows) == 1
    iface = rows[0]["runner_interface"]
    contract = rows[0]["runner_contract"]
    assert set(REQUIRED_RUNNER_FLAGS).issubset(iface["required_flags"])
    assert set(REQUIRED_RUNNER_ASSERTIONS).issubset(iface["required_assertions"])
    assert iface["default_mode"] == "dry_run_no_model_execution"
    assert not any(contract.values())
    assert not any(rows[0]["authority"].values())


def test_runner_design_card_rejects_execution_opening() -> None:
    rows = build_runner_design_rows([preflight_row()])
    rows[0]["runner_contract"]["runs_model_forward_now"] = True
    card = build_card(rows)
    assert card["passed"] is False
    assert card["execution_open_rows"] == 1
