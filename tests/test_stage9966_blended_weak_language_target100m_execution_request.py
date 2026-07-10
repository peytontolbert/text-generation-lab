from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9966_blended_weak_language_target100m_execution_request.py"
    spec = importlib.util.spec_from_file_location("stage9966", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_build_request_reflects_successor_edit_localization_counts():
    mod = _load()
    built = mod.build_request()
    assert built["passed"] is True
    metrics = built["metrics"]
    assert metrics["surface_requests"] == 4
    assert metrics["edit_localization_rows"] == 120
    assert metrics["edit_localization_python_rows"] == 24
    assert metrics["edit_localization_c_cpp_rows"] == 30
    assert metrics["edit_localization_web_rows"] == 45

