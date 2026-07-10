from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9779_current_truthful_standalone_claim_bridge.py"
    spec = importlib.util.spec_from_file_location("stage9779", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9779_refreshes_current_truthful_claim_front():
    mod = _load()
    bridge = mod.build_bridge()
    assert bridge["passed"] is True
    assert bridge["metrics"]["standalone_cells_with_current_truthful_support"] == 5
    assert bridge["metrics"]["support_by_skill"] == {"edit_localization": 4, "symbol_binding": 1}
    assert bridge["metrics"]["same_surface_win_cells"] == 4
    assert bridge["metrics"]["blocked_rebuild_cells"] == 8

    records = bridge["records"]
    edit_python = next(
        row for row in records
        if row["cell_key"] == "standalone_100m_weights::python::edit_localization"
    )
    assert "same_surface_100m_vs_gemma12b_evidence_missing" not in edit_python["blockers"]
    assert edit_python["missing_required_evidence"] == [
        "frozen_export_or_checkpoint_hash",
        "expert_maintainer_rubric_scores",
        "anti_cheat_cards",
    ]

    patch_python = next(
        row for row in records
        if row["cell_key"] == "standalone_100m_weights::python::patch_operator_selection"
    )
    assert patch_python["attached_evidence"] == []
    assert "blocked_upstream_evidence_rebuild_required" in patch_python["blockers"]
