from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9986_filtered_positive_replay_successor_request.py"
    spec = importlib.util.spec_from_file_location("stage9986", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_build_request_removes_only_quarantine_rows():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    import build_stage9985_mixed_replay_quarantine_recommendation as stage9985

    stage9985.main()
    mod = _load()
    built = mod.build_request()
    assert built["passed"] is True
    assert built["metrics"]["rows"] == 117
    assert built["metrics"]["language_counts"]["python"] == 22
    assert built["metrics"]["language_counts"]["c_cpp"] == 29
    assert built["metrics"]["recovery_reason_counts"]["gemma_advantage_only"] == 4
