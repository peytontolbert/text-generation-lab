from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9891_current_margin_locality_signal_lift_manifest.py"
    spec = importlib.util.spec_from_file_location("stage9891", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9891_lifts_locality_resolution_for_every_row():
    mod = _load()
    rows = mod.read_jsonl(mod.SOURCE_MANIFEST)
    out_rows, audit = mod.build_rows(rows)
    assert len(out_rows) == len(rows) == 48
    assert audit["all_rows_lifted"] is True
    sample = out_rows[0]
    assert "visible_locality_resolution" in sample["input_state"]
    assert sample["anti_cheat"]["stage9891_locality_signal_lifted"] is True
