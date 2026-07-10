from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9923_hardened_weighted_multilingual_review_workbook.py"
    spec = importlib.util.spec_from_file_location("stage9923", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9923_reads_weighted_review_packets():
    mod = _load()
    assert mod.PACKETS.name == "hardened_weighted_multilingual_winner_review_packets.jsonl"
