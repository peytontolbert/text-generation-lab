from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9927_full_product_harness_weighted_proxy_refresh.py"
    spec = importlib.util.spec_from_file_location("stage9927", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9927_targets_four_edit_localization_proxies():
    mod = _load()
    assert len(mod.WINNER_PROXIES) == 4
    assert mod.SOURCE_STANDALONE.name == "supported_standalone_weighted_frontier_packets.jsonl"
