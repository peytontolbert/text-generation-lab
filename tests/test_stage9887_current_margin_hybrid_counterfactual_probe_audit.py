from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9887_current_margin_hybrid_counterfactual_probe_audit.py"
    spec = importlib.util.spec_from_file_location("stage9887", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9887_audit_captures_hybrid_stall_against_stage9883():
    mod = _load()
    audit = mod.build_audit()
    assert audit["passed"] is True
    assert audit["metrics"]["eval_exact"] == 0.4375
    assert audit["metrics"]["strict_exact"] == 0.5
    assert audit["metrics"]["delta_vs_prior_eval"] == 0.0
    assert audit["metrics"]["delta_vs_prior_strict"] == 0.0
    assert audit["metrics"]["confusion_identical_to_stage9883"] is True
    assert audit["metrics"]["per_cell_exact_identical_to_stage9883"] is True
