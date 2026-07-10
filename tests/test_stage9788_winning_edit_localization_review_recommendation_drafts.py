from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9788_winning_edit_localization_review_recommendation_drafts.py"
    spec = importlib.util.spec_from_file_location("stage9788", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9788_builds_recommendation_drafts_for_four_winning_cells():
    mod = _load()
    built = mod.build_drafts()
    assert built["passed"] is True
    assert built["metrics"]["winning_cells"] == 4
    assert built["metrics"]["cells_with_label_proxy_shortcut_risk"] == 4
    assert built["metrics"]["rubric_recommendation_files"] == 4
    assert built["metrics"]["anti_cheat_recommendation_files"] == 4


def test_stage9788_python_recommendations_capture_rubric_and_shortcut_risk():
    mod = _load()
    built = mod.build_drafts()
    root = Path(__file__).resolve().parents[1]
    row = next(item for item in built["rows"] if item["cell_key"] == "standalone_100m_weights::python::edit_localization")
    rubric = json.loads((root / row["rubric_recommendation_path"]).read_text(encoding="utf-8"))
    anti = json.loads((root / row["anti_cheat_recommendation_path"]).read_text(encoding="utf-8"))

    assert rubric["recommended_subskills"]["localizes_edit_scope"]["recommended_judgment"] is True
    assert rubric["recommended_subskills"]["predicts_verifier_command"]["recommended_judgment"] is None
    label_proxy = next(item for item in anti["recommended_challenge_judgments"] if item["challenge_family"] == "label_proxy_shortcuts")
    assert label_proxy["recommended_pass"] is False
    assert anti["same_surface_verified"] is True
