from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9825_same_surface_two_phase_multilingual_frontier_bridge.py"
    spec = importlib.util.spec_from_file_location("stage9825", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9825_bridges_same_surface_two_phase_multilingual_frontier():
    mod = _load()
    bridge = mod.build_bridge()
    assert bridge["passed"] is True
    assert bridge["metrics"]["wins_100m"] == 4
    assert bridge["metrics"]["wins_gemma"] == 0
    assert bridge["metrics"]["ties"] == 0
    assert bridge["metrics"]["same_surface_frontier"] is True
    assert bridge["metrics"]["mixed_surface_frontier"] is False
    assert bridge["metrics"]["mixed_checkpoint_frontier"] is False
    assert bridge["metrics"]["continued_in_memory_model"] is True
    assert bridge["metrics"]["phase1_macro_strict_exact_100m"] == 0.45
    assert bridge["metrics"]["phase2_macro_strict_exact_100m"] == 0.5
    assert bridge["metrics"]["improved_languages_from_phase2"] == 1

    cpp = next(row for row in bridge["records"] if row["language_family"] == "c_cpp")
    assert cpp["phase1_strict_exact_100m"] == 0.4
    assert cpp["phase2_strict_exact_100m"] == 0.6
    assert cpp["gemma_strict_exact"] == 0.2
    assert cpp["delta_phase2_vs_phase1"] == 0.2
    assert cpp["verdict"] == "100m_better"

    web = next(row for row in bridge["records"] if row["language_family"] == "web_js_ts_html")
    assert web["phase2_strict_exact_100m"] == 0.6
    assert web["gemma_strict_exact"] == 0.2
    assert web["same_surface_packet"] is True
