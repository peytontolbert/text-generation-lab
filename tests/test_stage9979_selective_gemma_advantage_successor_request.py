from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9979_selective_gemma_advantage_successor_request.py"
    spec = importlib.util.spec_from_file_location("stage9979", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_build_request_materializes_131_row_selective_manifest():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    import build_stage9978_selective_gemma_advantage_recovery_packet as stage9978

    stage9978.main()
    mod = _load()
    built = mod.build_request()
    assert built["passed"] is True
    assert built["metrics"]["rows"] == 131
    assert built["metrics"]["language_counts"]["python"] == 30
    assert built["metrics"]["language_counts"]["c_cpp"] == 35
