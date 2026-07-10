from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9805_opaque_choice_review_recommendation_drafts.py"
    spec = importlib.util.spec_from_file_location("stage9805", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9805_builds_four_corrected_recommendation_rows():
    mod = _load()
    built = mod.build_drafts()
    assert built["passed"] is True
    assert built["metrics"]["recommendation_rows"] == 4
    assert built["metrics"]["rubric_recommendation_files"] == 4
    assert built["metrics"]["anti_cheat_recommendation_files"] == 4
    assert built["metrics"]["cells_with_shortcut_risk_flagged"] == 4


def test_stage9805_python_recommendations_are_conservative_and_flag_shortcut_risk():
    mod = _load()
    built = mod.build_drafts()
    row = next(r for r in built["rows"] if r["language_family"] == "python")
    rubric = json.loads((mod.ROOT / row["rubric_recommendation_path"]).read_text(encoding="utf-8"))
    anti = json.loads((mod.ROOT / row["anti_cheat_recommendation_path"]).read_text(encoding="utf-8"))
    assert rubric["recommended_subskills"]["localizes_edit_scope"]["recommended_judgment"] is None
    anti_index = {r["challenge_family"]: r for r in anti["recommended_challenge_judgments"]}
    assert anti_index["label_proxy_shortcuts"]["recommended_pass"] is False
    assert anti_index["target_and_teacher_leakage"]["recommended_pass"] is True
