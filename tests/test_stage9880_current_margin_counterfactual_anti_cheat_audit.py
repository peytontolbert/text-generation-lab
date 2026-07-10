from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9880_current_margin_counterfactual_anti_cheat_audit.py"
    spec = importlib.util.spec_from_file_location("stage9880", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9880_builds_current_margin_counterfactual_cards():
    mod = _load()
    built = mod.build_audit()
    assert built["passed"] is True
    assert built["metrics"]["validated_cells"] == 4
    assert built["metrics"]["language_family_wins_100m"] == 4
    assert built["metrics"]["strict_language_wins_100m"] == 3
    assert built["metrics"]["strict_language_ties"] == 1
    assert built["metrics"]["cells_with_label_proxy_shortcut_risk"] == 4
    assert built["metrics"]["cells_with_cross_model_fairness_support"] == 4
    assert built["metrics"]["cells_where_harder_counterfactual_keeps_100m_edge"] == 1
    assert built["metrics"]["cells_where_harder_counterfactual_erases_or_reverses_edge"] == 3


def test_stage9880_python_card_tracks_current_counterfactual_regression():
    mod = _load()
    built = mod.build_audit()
    python = next(row for row in built["records"] if row["language_family"] == "python")
    assert python["strict_exact_100m"] == 0.5
    assert python["strict_exact_gemma"] == 0.5
    assert python["strict_verdict"] == "tie"
    assert python["language_family_verdict"] == "100m_better"
    assert python["harder_counterfactual_strict_verdict"] == "tie"
    assert python["abstention_counterfactual_strict_verdict"] == "gemma_win"
    assert python["label_proxy_shortcut_risk"]["recommended_pass"] is False
    assert python["cross_model_surface_fairness"]["recommended_pass"] is True
