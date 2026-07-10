from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9975_real_loss_successor_mix.py"
    spec = importlib.util.spec_from_file_location("stage9975", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_build_blend_appends_real_loss_rows():
    mod = _load()
    built = mod.build_blend()
    assert built["passed"] is True
    metrics = built["metrics"]
    assert metrics["blended_structured_rows"] == 484
    assert metrics["edit_localization_rows_after"] == 152
    assert metrics["python_edit_rows_after"] == 40
    assert metrics["c_cpp_edit_rows_after"] == 46

