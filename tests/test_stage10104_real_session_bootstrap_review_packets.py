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


def test_stage10104_review_packets_builds() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10104_real_session_bootstrap_review_packets.py",
        "stage10104",
    )
    built = mod.build()
    assert built["passed"] is True
    assert built["metrics"]["review_packet_rows"] == 33
    assert built["metrics"]["workbook_rows"] == 66
    assert built["metrics"]["rubric_tasks"] == 33
    assert built["metrics"]["anti_cheat_tasks"] == 33


def test_stage10104_packet_stubs_written() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10104_real_session_bootstrap_review_packets.py",
        "stage10104_written",
    )
    mod.main()
    packets = json.loads((mod.WORKBOOK).read_text(encoding="utf-8"))
    assert packets["row_count"] == 66
    first = packets["rows"][0]
    rubric = json.loads((mod.ROOT / first["review_file"]).read_text(encoding="utf-8"))
    assert rubric["status"] == "pending_human_review"
    assert "gold_label_slot" in rubric
