from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9925_supported_standalone_weighted_frontier_refresh.py"
    spec = importlib.util.spec_from_file_location("stage9925", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9925_knows_weighted_winner_cells():
    mod = _load()
    assert len(mod.WINNER_CELLS) == 4
    assert mod.FRONTIER.name == "current_weighted_hardened_multilingual_frontier_bridge.json"
