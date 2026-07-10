from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9907_geometry_aware_opaque_choice_manifest.py"
    spec = importlib.util.spec_from_file_location("stage9907", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9907_build_rows_preserves_packet_shape_and_uses_abcd():
    mod = _load()
    rows = mod.build_rows()
    assert len(rows) == 48
    assert sorted({str(((row.get("target") or {}).get("decoder_text") or "")) for row in rows}) == ["A", "B", "C", "D"]
    assert rows[0]["anti_cheat"]["stage9907_opaque_choice_inventory"] == ["A", "B", "C", "D"]

