from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9924_current_truthful_weighted_hardened_bridge_after_review_workbook.py"
    spec = importlib.util.spec_from_file_location("stage9924", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9924_points_to_weighted_bridge_and_workbook():
    mod = _load()
    assert mod.SOURCE_BRIDGE.name == "current_weighted_hardened_multilingual_frontier_bridge.json"
    assert mod.WORKBOOK.name == "hardened_weighted_multilingual_review_workbook.json"
