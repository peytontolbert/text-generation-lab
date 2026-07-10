from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9982_gemma_advantage_review_packet.py"
    spec = importlib.util.spec_from_file_location("stage9982", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_build_packet_materializes_all_failed_gemma_advantage_rows():
    mod = _load()
    packet = mod.build_packet()
    assert packet["passed"] is True
    assert packet["metrics"]["rows"] == 11
    assert packet["metrics"]["language_counts"]["python"] == 6
    assert packet["metrics"]["language_counts"]["c_cpp"] == 5
    assert packet["metrics"]["incorrect_rows"] == 11
