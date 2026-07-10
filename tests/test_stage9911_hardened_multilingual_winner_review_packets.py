from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9911_hardened_multilingual_winner_review_packets.py"
    spec = importlib.util.spec_from_file_location("stage9911", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["stage9911"] = module
    spec.loader.exec_module(module)
    return module


def test_stage9911_builds_four_hardened_review_cells():
    mod = _load()
    built = mod.build_packets()
    assert built["passed"] is True
    assert built["metrics"]["review_cells"] == 4
    assert built["metrics"]["hardened_same_surface_win_cells"] == 4

