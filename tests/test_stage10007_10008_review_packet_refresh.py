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


def test_stage10007_attach_heldout_evidence():
    mod = _load(ROOT / "scripts/build_stage10007_attach_heldout_evidence_to_active_review_cards.py", "stage10007")
    built = mod.build_refresh()
    assert built["passed"] is True
    assert built["metrics"]["winner_cells_enriched"] == 4


def test_stage10008_heldout_signoff_sheets():
    mod = _load(ROOT / "scripts/build_stage10008_heldout_winner_signoff_sheets.py", "stage10008")
    built = mod.build_sheets()
    assert built["passed"] is True
    assert built["metrics"]["signoff_sheets_written"] == 4
