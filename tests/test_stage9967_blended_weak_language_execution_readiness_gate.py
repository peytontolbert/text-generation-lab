from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9967_blended_weak_language_execution_readiness_gate.py"
    spec = importlib.util.spec_from_file_location("stage9967", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_selected_surface_request_preserves_successor_counts():
    import build_stage9966_blended_weak_language_target100m_execution_request as stage9966
    stage9966.main()
    mod = _load()
    row = mod._selected_surface_request()
    assert row["surface"] == "edit_localization"
    assert row["rows"] == 120
    assert row["language_counts"]["python"] == 24
    assert row["language_counts"]["c_cpp"] == 30
    assert row["language_counts"]["web_js_ts_html"] == 45

