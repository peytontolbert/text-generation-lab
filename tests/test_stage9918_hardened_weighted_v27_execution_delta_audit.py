from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9918_hardened_weighted_v27_execution_delta_audit.py"
    spec = importlib.util.spec_from_file_location("stage9918", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9918_uses_weighted_review_as_current_and_hardened_review_as_baseline():
    mod = _load()
    assert mod.CURRENT.name == "stage9917_hardened_weighted_structured_execution_review.json"
    assert mod.BASELINE.name == "stage9914_hardened_structured_tiny_execution_review.json"
