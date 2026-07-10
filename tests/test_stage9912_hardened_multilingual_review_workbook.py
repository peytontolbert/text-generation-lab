from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9912_hardened_multilingual_review_workbook.py"
    spec = importlib.util.spec_from_file_location("stage9912", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["stage9912"] = module
    spec.loader.exec_module(module)
    return module


def test_stage9912_workbook_reads_hardened_packet_stubs():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / "scripts"))
    stage9911_path = root / "scripts/build_stage9911_hardened_multilingual_winner_review_packets.py"
    stage9911_spec = importlib.util.spec_from_file_location("stage9911_for_9912", stage9911_path)
    stage9911 = importlib.util.module_from_spec(stage9911_spec)
    assert stage9911_spec and stage9911_spec.loader
    stage9911_spec.loader.exec_module(stage9911)
    built_packets = stage9911.build_packets()
    stage9911.write_jsonl(stage9911.PACKETS, built_packets["rows"])
    mod = _load()
    built = mod.build_workbook()
    assert built["passed"] is True
    assert built["metrics"]["winning_review_tasks"] == 8
    assert built["metrics"]["unique_cells"] == 4
