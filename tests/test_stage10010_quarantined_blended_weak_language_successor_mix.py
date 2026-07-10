from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage10010_quarantined_blended_weak_language_successor_mix.py"
    spec = importlib.util.spec_from_file_location("stage10010", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_build_quarantined_weak_language_blend_matches_expected_counts():
    mod = _load()
    built = mod.build_blend()
    assert built["passed"] is True
    assert built["metrics"]["base_structured_rows"] == 396
    assert built["metrics"]["recovery_rows_added"] == 48
    assert built["metrics"]["blended_structured_rows"] == 444
    assert built["metrics"]["edit_localization_rows_before"] == 64
    assert built["metrics"]["edit_localization_rows_after"] == 112
    assert built["metrics"]["python_edit_rows_after"] == 19
    assert built["metrics"]["c_cpp_edit_rows_after"] == 27
    assert built["metrics"]["rust_edit_rows_after"] == 21
    assert built["metrics"]["web_edit_rows_after"] == 45
    assert built["metrics"]["base_rows_removed_from_stale_blend"] == 8
