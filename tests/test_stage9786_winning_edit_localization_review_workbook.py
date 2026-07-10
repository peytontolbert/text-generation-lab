from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9786_winning_edit_localization_review_workbook.py"
    spec = importlib.util.spec_from_file_location("stage9786", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9786_workbook_tracks_only_four_winning_cells():
    mod = _load()
    built = mod.build_workbook()

    assert built["failures"] == []
    assert built["metrics"]["winning_review_tasks"] == 8
    assert built["metrics"]["unique_cells"] == 4
    assert built["metrics"]["rubric_tasks"] == 4
    assert built["metrics"]["anti_cheat_tasks"] == 4
    assert built["metrics"]["same_surface_verified_tasks"] == 8
    assert built["metrics"]["top_queue_entry"] == (
        "standalone_100m_weights::python::edit_localization::expert_maintainer_rubric_review"
    )


def test_stage9786_first_row_carries_hashes_and_human_review_blocker():
    mod = _load()
    built = mod.build_workbook()
    first = built["rows"][0]

    assert first["task"] == "expert_maintainer_rubric_review"
    assert first["review_stub_path"].endswith("expert_maintainer_rubric_review.json")
    assert first["counterfactual_audit_path"].endswith(
        "stage9784_winning_edit_localization_counterfactual_anti_cheat_audit/winning_edit_localization_counterfactual_anti_cheat_audit.json"
    )
    assert first["state_hash"] == "174f1f24aefe3e7405178393af9f1a59be0575330632067f85c1c6c3502af436"
    assert first["manifest_hash"] == "4f6560c4ee7f92861f2c7f5cde1c689af724097883fde3a362ced16f0fa4f115"
    assert "same_surface_win_present_but_review_confirmation_still_missing" in first["remaining_bridge_blockers"]
    assert "counterfactual_anti_cheat_audit_support" in first["attached_bridge_evidence_kinds"]
