from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9920_hardened_weighted_edit_localization_shortcut_audit.py"
    spec = importlib.util.spec_from_file_location("stage9920", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9920_points_to_weighted_comparison_and_manifest():
    mod = _load()
    assert mod.MANIFEST.name == "edit_localization_tiny.jsonl"
    assert mod.COMPARISON.name == "hardened_weighted_edit_localization_gemma_comparison.json"
