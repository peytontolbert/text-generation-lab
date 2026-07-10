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


def test_stage10043_expanded_source_heldout_signoff_workbook():
    mod = _load(ROOT / "scripts/build_stage10043_expanded_source_heldout_signoff_workbook.py", "stage10043")
    built = mod.build_workbook()
    assert built["passed"] is True
    assert built["metrics"]["signoff_tasks"] == 8
    assert built["metrics"]["expanded_manifest_rows"] == 95
    assert built["metrics"]["expanded_compare_rows"] == 55
    assert built["metrics"]["fresh_review_rows"] == 18
