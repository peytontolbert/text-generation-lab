from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9989_filtered_same_manifest_gemma_queue.py"
    spec = importlib.util.spec_from_file_location("stage9989", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_build_queue_materializes_filtered_same_manifest_packet():
    mod = _load()
    built = mod.build_queue()
    assert built["passed"] is True
    assert built["metrics"]["rows"] == 117
    assert built["metrics"]["language_counts"]["python"] == 22
    assert built["metrics"]["language_counts"]["c_cpp"] == 29
