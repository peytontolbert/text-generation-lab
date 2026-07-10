from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9884_current_margin_counterfactual_probe_audit.py"
    spec = importlib.util.spec_from_file_location("stage9884", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9884_summarizes_stage9883_regression_against_broader_baseline():
    mod = _load()
    audit = mod.build_audit()
    assert audit["passed"] is True
    assert audit["metrics"]["eval_exact"] == 0.4375
    assert audit["metrics"]["strict_exact"] == 0.5
    assert audit["metrics"]["broader_eval_exact_baseline"] == 0.4375
    assert audit["metrics"]["broader_strict_exact_baseline"] == 0.5625
    assert audit["metrics"]["delta_vs_broader_eval"] == 0.0
    assert audit["metrics"]["delta_vs_broader_strict"] == -0.0625


def test_stage9884_confusion_summary_captures_k_to_r_collapse():
    mod = _load()
    audit = mod.build_audit()
    assert audit["metrics"]["dominant_confusion_targets"]["K"] == "R"
    assert audit["metrics"]["dominant_confusion_targets"]["T"] == "T"
