from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9878_current_margin_multilingual_frontier_bridge.py"
    spec = importlib.util.spec_from_file_location("stage9878", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9878_bridges_current_margin_multilingual_frontier_truthfully():
    mod = _load()
    bridge = mod.build_bridge()
    assert bridge["passed"] is True
    assert bridge["metrics"]["language_family_wins_100m"] == 4
    assert bridge["metrics"]["strict_language_wins_100m"] == 3
    assert bridge["metrics"]["strict_language_ties"] == 1
    assert bridge["metrics"]["wins_100m"] == 7
    assert bridge["metrics"]["wins_gemma"] == 0
    assert bridge["metrics"]["ties"] == 1
    assert bridge["metrics"]["same_surface_frontier"] is True
    assert bridge["metrics"]["mixed_surface_frontier"] is False
    assert bridge["metrics"]["broader_edit_localization_strict_exact_100m"] == 0.5625
    assert bridge["metrics"]["broader_edit_localization_selected_step"] == 24
    assert bridge["metrics"]["harder_counterfactual_macro_strict_delta"] == 0.0
    assert bridge["metrics"]["abstention_counterfactual_macro_strict_delta"] == 0.25


def test_stage9878_python_is_language_family_win_but_strict_tie():
    mod = _load()
    bridge = mod.build_bridge()
    python = next(row for row in bridge["records"] if row["language_family"] == "python")
    assert python["eval_exact_100m"] == 0.5
    assert python["eval_exact_gemma"] == 0.25
    assert python["strict_exact_100m"] == 0.5
    assert python["strict_exact_gemma"] == 0.5
    assert python["strict_verdict"] == "tie"
    assert python["language_family_verdict"] == "100m_better"
    assert python["harder_counterfactual_strict_verdict"] == "tie"
    assert python["abstention_counterfactual_strict_verdict"] == "gemma_win"
