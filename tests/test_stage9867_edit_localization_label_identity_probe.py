from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9867_edit_localization_label_identity_probe.py"
    spec = importlib.util.spec_from_file_location("stage9867", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_remap_label_text_rewrites_option_prefix_only():
    mod = _load()
    assert mod.remap_label_text("option A: thing") == "option K: thing"
    assert mod.remap_label_text("option E: thing") == "option Z: thing"


def test_remap_row_rewrites_targets_and_choices():
    mod = _load()
    row = {
        "target": {"edit_localization": "B", "target_ref": "B", "decoder_text": "B"},
        "clean_state": {"edit_localization": "B", "edit_localization_target": "B"},
        "input_state": {"candidate_choices": ["option A: x", "option B: y", "option C: z", "option D: q", "option E: w"]},
    }
    out = mod.remap_row(row)
    assert out["target"]["edit_localization"] == "M"
    assert out["clean_state"]["edit_localization_target"] == "M"
    assert out["input_state"]["candidate_choices"][1].startswith("option M:")


def test_build_command_targets_stage9868():
    mod = _load()
    joined = " ".join(mod.build_command())
    assert "stage9868_edit_localization_label_identity_target_100m_probe" in joined
    assert "--mode edit_localization_probe" in joined
