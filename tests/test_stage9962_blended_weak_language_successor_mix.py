from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9962_blended_weak_language_successor_mix.py"
    spec = importlib.util.spec_from_file_location("stage9962", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_build_blend_reflects_weak_language_recovery_growth():
    mod = _load()
    built = mod.build_blend()
    assert built["passed"] is True
    metrics = built["metrics"]
    assert metrics["base_structured_rows"] == 404
    assert metrics["recovery_rows_added"] == 48
    assert metrics["blended_structured_rows"] == 452
    assert metrics["edit_localization_rows_after"] == 120
    assert metrics["python_edit_rows_after"] == 24
    assert metrics["c_cpp_edit_rows_after"] == 30
    assert metrics["rust_edit_rows_after"] == 21
    assert metrics["web_edit_rows_after"] == 45
    assert metrics["recovery_rows_present"] == 48
    assert metrics["recovery_weight_sum"] == 147

