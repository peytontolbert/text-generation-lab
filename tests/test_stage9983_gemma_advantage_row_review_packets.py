from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9983_gemma_advantage_row_review_packets.py"
    spec = importlib.util.spec_from_file_location("stage9983", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_build_packets_materializes_row_level_review_packets():
    mod = _load()
    built = mod.build_packets()
    assert built["passed"] is True
    assert built["metrics"]["review_rows"] == 11
    assert built["metrics"]["python_rows"] == 6
    assert built["metrics"]["c_cpp_rows"] == 5
    assert built["metrics"]["all_rows_incorrect"] is True
