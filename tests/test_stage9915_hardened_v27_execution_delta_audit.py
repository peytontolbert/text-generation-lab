from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9915_hardened_v27_execution_delta_audit.py"
    spec = importlib.util.spec_from_file_location("stage9915", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9915_delta_shows_hardened_package_preserves_tiny_review_scores():
    mod = _load()
    audit = mod.build_audit()
    assert audit["passed"] is True
    assert audit["metrics"]["surface_delta"]["edit_localization"]["delta_eval_exact"] == 0.0
    assert audit["metrics"]["surface_delta"]["symbol_binding"]["delta_strict_exact"] == 0.0
