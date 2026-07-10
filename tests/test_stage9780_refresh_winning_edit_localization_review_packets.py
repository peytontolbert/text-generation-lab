from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9780_refresh_winning_edit_localization_review_packets.py"
    spec = importlib.util.spec_from_file_location("stage9780", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9780_refreshes_winning_edit_localization_packets():
    mod = _load()
    built = mod.build_refresh()
    assert built["passed"] is True
    assert built["metrics"]["refreshed_cells"] == 4
    assert built["metrics"]["same_surface_win_cells"] == 4

    root = Path(__file__).resolve().parents[1]
    row = next(item for item in built["rows"] if item["cell_key"] == "standalone_100m_weights::python::edit_localization")
    rubric = json.loads((root / row["rubric_path"]).read_text(encoding="utf-8"))
    anti = json.loads((root / row["anti_cheat_path"]).read_text(encoding="utf-8"))
    gemma = json.loads((root / row["gemma_path"]).read_text(encoding="utf-8"))
    checkpoint = (root / row["checkpoint_path"]).read_text(encoding="utf-8")

    assert rubric["same_surface_strict_exact"] == 1.0
    assert rubric["gemma_strict_exact"] == 0.2
    assert rubric["hundred_m_beats_gemma12b"] is True
    assert anti["same_surface_verified"] is True
    assert len(anti["challenge_families"]) == 6
    assert gemma["same_surface_verified"] is True
    assert gemma["score_100m"] == 1.0
    assert gemma["score_gemma12b"] == 0.2
    assert "checkpoint_exported=false" in checkpoint
