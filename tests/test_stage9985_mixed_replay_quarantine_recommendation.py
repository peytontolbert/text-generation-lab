from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9985_mixed_replay_quarantine_recommendation.py"
    spec = importlib.util.spec_from_file_location("stage9985", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_build_recommendation_targets_only_mixed_replay_rows():
    mod = _load()
    built = mod.build_recommendation()
    assert built["passed"] is True
    assert built["metrics"]["recommended_quarantine_rows"] == 7
    assert built["metrics"]["language_counts"]["python"] == 4
    assert built["metrics"]["language_counts"]["c_cpp"] == 3
