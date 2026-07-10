from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage10004_heldout_signoff_workbook():
    mod = _load(ROOT / "scripts/build_stage10004_heldout_multilingual_winner_signoff_workbook.py", "stage10004")
    built = mod.build_workbook()
    assert built["passed"] is True
    assert built["metrics"]["signoff_tasks"] == 8
    assert built["metrics"]["unique_cells"] == 4


def test_stage10005_blocker_ledger_after_heldout_win():
    mod = _load(ROOT / "scripts/build_stage10005_v27_current_blocker_ledger_after_heldout_win.py", "stage10005")
    built = mod.build_ledger()
    assert built["passed"] is True
    assert built["metrics"]["languages_with_standalone_win"] == 4
    assert built["metrics"]["languages_with_harness_handoff_ready"] == 4
    assert built["metrics"]["total_pending_human_signoff_tasks"] == 8


def test_stage10006_heldout_closeout_packet():
    mod = _load(ROOT / "scripts/build_stage10006_v27_heldout_closeout_packet.py", "stage10006")
    built = mod.build_packet()
    assert built["passed"] is True
    assert built["metrics"]["language_packets"] == 4
    assert built["metrics"]["languages_with_standalone_win"] == 4
    assert built["metrics"]["languages_with_external_harness_handoff"] == 4
