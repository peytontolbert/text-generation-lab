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


def test_stage10046_expanded_python_gap_collapse_audit():
    mod = _load(ROOT / "scripts/build_stage10046_expanded_python_gap_collapse_audit.py", "stage10046")
    built = mod.build_audit()
    assert built["passed"] is True
    assert built["metrics"]["python_rows"] == 11
    assert built["metrics"]["python_fresh_rows"] == 6
    assert built["metrics"]["hundred_m_pred_counts"] == {"A": 1, "C": 9, "E": 1}
    assert built["metrics"]["hundred_m_label_collapse_detected"] is True
    assert built["metrics"]["target_family_accuracy"]["TARGET_SYMBOL"]["gemma_exact"] == 0.5
    assert built["metrics"]["target_family_accuracy"]["TARGET_TEST"]["hundred_m_exact"] == 0.0
