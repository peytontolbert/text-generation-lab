from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9978_selective_gemma_advantage_recovery_packet.py"
    spec = importlib.util.spec_from_file_location("stage9978", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_build_packet_targets_only_python_and_cpp_gemma_advantage_rows():
    mod = _load()
    built = mod.build_packet()
    assert built["passed"] is True
    assert built["metrics"]["rows"] == 11
    assert built["metrics"]["language_counts"]["python"] == 6
    assert built["metrics"]["language_counts"]["c_cpp"] == 5

