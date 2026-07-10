from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9812_best_observed_multilingual_frontier_bridge.py"
    spec = importlib.util.spec_from_file_location("stage9812", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9812_bridges_best_observed_multilingual_frontier():
    mod = _load()
    bridge = mod.build_bridge()
    assert bridge["passed"] is True
    assert bridge["metrics"]["wins_100m"] == 4
    assert bridge["metrics"]["wins_gemma"] == 0
    assert bridge["metrics"]["ties"] == 0
    assert bridge["metrics"]["mixed_surface_frontier"] is True
    assert bridge["metrics"]["mixed_checkpoint_frontier"] is True

    web = next(row for row in bridge["records"] if row["language_family"] == "web_js_ts_html")
    assert web["model_execution_stage"] == 9809
    assert web["comparison_stage"] == 9810
    assert web["anti_cheat_stage"] == 9811
    assert web["model_strict_exact_100m"] == 0.6
    assert web["gemma_strict_exact"] == 0.2
    assert web["verdict"] == "100m_better"
