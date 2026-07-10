from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9993_python_gap_successor_request.py"
    spec = importlib.util.spec_from_file_location("stage9993", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_build_request_adds_only_two_python_gap_replay_rows():
    mod = _load()
    built = mod.build_request()
    assert built["passed"] is True
    assert built["metrics"]["rows"] == 119
    assert built["metrics"]["split_counts"]["train"] == 42
    assert built["metrics"]["language_counts"]["python"] == 24
    assert built["metrics"]["gap_replay_rows"] == 2
