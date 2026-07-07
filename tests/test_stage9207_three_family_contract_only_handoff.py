from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9207_three_family_contract_only_handoff.py"
    spec = importlib.util.spec_from_file_location("stage9207_handoff", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_select_rows_for_denoise_mode_filters_loss_mask():
    mod = _load()
    rows = [
        {"row_id": "a", "loss_mask": {"denoise_ce": True, "decoder_ce": False}},
        {"row_id": "b", "loss_mask": {"denoise_ce": False, "decoder_ce": True}},
    ]
    selected = mod.select_rows_for_mode(rows, "denoise_repair_probe")
    assert [row["row_id"] for row in selected] == ["a"]
    assert selected[0]["loss_mask"]["denoise_ce"] is True
    assert selected[0]["loss_mask"]["decoder_ce"] is False
