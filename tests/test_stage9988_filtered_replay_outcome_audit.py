from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9988_filtered_replay_outcome_audit.py"
    spec = importlib.util.spec_from_file_location("stage9988", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_build_audit_confirms_filtered_frontier_improvement():
    mod = _load()
    built = mod.build_audit()
    assert built["passed"] is True
    assert built["aggregate"]["stage9987"]["strict_exact"] > built["aggregate"]["stage9965"]["strict_exact"]
    assert built["aggregate"]["stage9987"]["strict_exact"] > built["aggregate"]["stage9980"]["strict_exact"]
    assert built["per_language"]["python"]["delta_vs_stage9965"] > 0.0
    assert built["per_language"]["c_cpp"]["delta_vs_stage9965"] > 0.0
    assert built["remaining_positive_gemma_advantage_rows"]["python|eval"]["exact"] == 0.0
    assert built["remaining_positive_gemma_advantage_rows"]["c_cpp|eval"]["exact"] == 0.0
