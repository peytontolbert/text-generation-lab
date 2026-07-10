from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9922_current_weighted_hardened_multilingual_frontier_bridge.py"
    spec = importlib.util.spec_from_file_location("stage9922", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9922_points_to_weighted_comparison_and_shortcut_chain():
    mod = _load()
    assert mod.STAGE9919.name == "hardened_weighted_edit_localization_gemma_comparison.json"
    assert mod.STAGE9920.name == "hardened_weighted_edit_localization_shortcut_audit.json"
    assert mod.STAGE9918.name == "hardened_weighted_v27_execution_delta_audit.json"
