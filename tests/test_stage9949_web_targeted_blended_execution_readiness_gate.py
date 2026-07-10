from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9949_web_targeted_blended_execution_readiness_gate.py"
    spec = importlib.util.spec_from_file_location("stage9949", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_future_command_rewrites_request_namespace_to_execution_namespace():
    mod = _load()
    cmd = mod.future_command()
    text = " ".join(cmd)
    assert "stage9950_" in text
    assert "stage9948_" not in text
    assert "stage9949_" not in text
    assert "--execution-authorized-for-recovery-probe" in cmd


def test_selected_surface_request_is_edit_localization_with_web_rows():
    mod = _load()
    row = mod._selected_surface_request()
    assert row["surface"] == "edit_localization"
    assert row["rows"] == 72
    assert row["language_counts"]["web_js_ts_html"] == 27
