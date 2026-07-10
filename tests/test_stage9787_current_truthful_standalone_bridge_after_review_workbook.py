from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9787_current_truthful_standalone_bridge_after_review_workbook.py"
    spec = importlib.util.spec_from_file_location("stage9787", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9787_refreshes_truthful_bridge_with_review_workbook_support():
    mod = _load()
    built = mod.build_refresh()
    assert built["passed"] is True
    assert built["metrics"]["bridge_records"] == 72
    assert built["metrics"]["winning_cells_with_workbook_support"] == 4
    assert built["metrics"]["winning_cells_machine_complete_but_review_blocked"] == 4


def test_stage9787_python_winning_cell_is_machine_complete_but_review_blocked():
    mod = _load()
    built = mod.build_refresh()
    root = Path(__file__).resolve().parents[1]
    artifact = json.loads((root / "runs/local/artifacts/stage9787_current_truthful_standalone_bridge_after_review_workbook/current_truthful_standalone_bridge_after_review_workbook.json").read_text(encoding="utf-8"))
    row = next(item for item in artifact["records"] if item["cell_key"] == "standalone_100m_weights::python::edit_localization")

    assert row["claim_status"] == "blocked_pending_human_review_confirmation"
    assert row["review_execution_ready"] is True
    assert row["remaining_machine_gap"] is False
    assert row["review_workbook_path"].endswith(
        "stage9786_winning_edit_localization_review_workbook/winning_edit_localization_review_workbook.json"
    )
    assert any(item["kind"] == "winning_review_workbook_support" for item in row["attached_evidence"])
    assert "same_surface_100m_vs_gemma12b_evidence_missing" not in row["blockers"]
    assert "same_surface_win_present_but_review_confirmation_still_missing" in row["blockers"]
