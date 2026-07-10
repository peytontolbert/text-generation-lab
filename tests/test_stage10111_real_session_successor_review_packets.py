from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_stage10111_review_packets_build() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10111_real_session_successor_review_packets.py",
        "stage10111",
    )
    built = mod.build()
    assert built["passed"] is True
    assert built["metrics"]["review_packet_rows"] == 41
    assert built["metrics"]["workbook_rows"] == 82
    assert built["metrics"]["rubric_tasks"] == 41
    assert built["metrics"]["anti_cheat_tasks"] == 41


def test_stage10111_packet_stubs_written() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10111_real_session_successor_review_packets.py",
        "stage10111_written",
    )
    mod.main()
    workbook = json.loads(mod.WORKBOOK.read_text(encoding="utf-8"))
    assert workbook["row_count"] == 82
    first = workbook["rows"][0]
    rubric = json.loads((mod.ROOT / first["review_file"]).read_text(encoding="utf-8"))
    assert rubric["status"] == "pending_human_review"
    assert "gold_label_slot" in rubric
