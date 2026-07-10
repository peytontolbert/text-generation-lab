from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9981_selective_replay_outcome_audit.py"
    spec = importlib.util.spec_from_file_location("stage9981", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_build_audit_captures_selective_replay_tradeoff():
    mod = _load()
    audit = mod.build_audit()
    assert audit["passed"] is True
    assert audit["aggregate"]["selective_minus_broad"]["eval_exact"] > 0.0
    assert audit["aggregate"]["selective_minus_broad"]["strict_exact"] > 0.0
    assert audit["aggregate"]["selective_minus_baseline"]["eval_exact"] < 0.0
    assert audit["aggregate"]["selective_minus_baseline"]["strict_exact"] < 0.0
    assert audit["recovery_row_breakdown"]["python|gemma_advantage_only|eval"]["exact"] == 0.0
    assert audit["recovery_row_breakdown"]["python|gemma_advantage_only|strict_eval"]["exact"] == 0.0
    assert audit["recovery_row_breakdown"]["c_cpp|gemma_advantage_only|eval"]["exact"] == 0.0
    assert audit["recovery_row_breakdown"]["c_cpp|gemma_advantage_only|strict_eval"]["exact"] == 0.0
