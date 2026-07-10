from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9890_current_margin_position_debiased_probe_audit.py"
    spec = importlib.util.spec_from_file_location("stage9890", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9890_audit_captures_flat_eval_and_strict_regression():
    mod = _load()
    audit = mod.build_audit()
    assert audit["passed"] is True
    assert audit["metrics"]["eval_exact"] == 0.4375
    assert audit["metrics"]["strict_exact"] == 0.4375
    assert audit["metrics"]["delta_vs_prior_eval"] == 0.0
    assert audit["metrics"]["delta_vs_prior_strict"] == -0.0625
    assert audit["metrics"]["dominant_confusion_targets"]["K"] == "R"
    assert audit["metrics"]["per_cell_delta_vs_stage9886"]["web_js_ts_html::current_margin_edit_localization_counterfactual_guard::KEEP_STRUCTURED"] == -0.125
