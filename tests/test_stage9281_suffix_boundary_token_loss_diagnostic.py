from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9281_suffix_boundary_token_loss_diagnostic.py"
    spec = importlib.util.spec_from_file_location("stage9281", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9281_maps_token_loss_to_suffix_boundary():
    mod = _load()
    diagnostic, rows = mod.build_diagnostic()
    assert diagnostic["passed"] is True
    assert diagnostic["rows"] > 0
    assert diagnostic["missing_boundary_rows"] == 0
    assert diagnostic["first_unforced_mean_loss"] is not None
    assert diagnostic["suffix_mean_loss"] is not None
    assert diagnostic["eos_mean_loss"] is not None
    assert diagnostic["worst_first_unforced_rows"]
    assert all(row["boundary_position"] >= 0 for row in rows)


def test_stage9281_boundary_helper_finds_exact_prefix_end():
    mod = _load()
    positions = [
        {"position": 0, "token_text": "Return"},
        {"position": 1, "token_text": " the"},
        {"position": 2, "token_text": " value"},
        {"position": 3, "token_text": "."},
    ]
    boundary, reconstructed = mod.token_prefix_boundary(positions, "Return the value")
    assert boundary == 3
    assert reconstructed == "Return the value"
