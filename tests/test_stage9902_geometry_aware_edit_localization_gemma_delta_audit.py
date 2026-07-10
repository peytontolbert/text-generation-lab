from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9902_geometry_aware_edit_localization_gemma_delta_audit.py"
    spec = importlib.util.spec_from_file_location("stage9902", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9902_captures_narrow_100m_edge():
    mod = _load()
    audit = mod.build_audit()
    assert audit["passed"] is True
    assert audit["metrics"]["wins_100m"] == 1
    assert audit["metrics"]["wins_gemma"] == 0
    assert audit["metrics"]["ties"] == 7
    assert audit["metrics"]["comparison_delta"]["web_js_ts_html:eval"]["current_verdict"] == "100m_better"
