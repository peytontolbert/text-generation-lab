from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9827_current_multilingual_winner_review_packets.py"
    spec = importlib.util.spec_from_file_location("stage9827", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9827_materializes_review_packets_and_recommendations_for_current_winner():
    mod = _load()
    built = mod.build_packets()
    assert built["passed"] is True
    assert built["metrics"]["winning_cells"] == 4
    assert built["metrics"]["rubric_stub_files"] == 4
    assert built["metrics"]["anti_cheat_stub_files"] == 4
    assert built["metrics"]["rubric_recommendation_files"] == 4
    assert built["metrics"]["anti_cheat_recommendation_files"] == 4
    assert built["metrics"]["cells_with_label_proxy_shortcut_risk"] == 4


def test_stage9827_python_packet_flags_shortcut_risk_and_pending_human_review():
    mod = _load()
    built = mod.build_packets()
    root = Path(__file__).resolve().parents[1]
    row = next(item for item in built["rows"] if item["language_family"] == "python")
    rubric = json.loads((root / row["review_packet_paths"]["expert_maintainer_rubric_scores"]).read_text(encoding="utf-8"))
    anti = json.loads((root / row["review_packet_paths"]["anti_cheat_cards"]).read_text(encoding="utf-8"))
    rubric_draft = json.loads((root / row["review_packet_paths"]["rubric_recommendation_draft"]).read_text(encoding="utf-8"))
    anti_draft = json.loads((root / row["review_packet_paths"]["anti_cheat_recommendation_draft"]).read_text(encoding="utf-8"))

    assert rubric["status"] == "pending_human_review"
    assert rubric["passed"] is False
    assert len(rubric["subskills"]) == 16
    assert anti["status"] == "pending_cell_specific_review"
    assert anti["global_stage9717_gate_passed"] is True
    assert len(anti["challenge_families"]) == 6
    assert rubric_draft["recommended_subskills"]["localizes_edit_scope"]["recommended_judgment"] is True
    assert rubric_draft["recommended_subskills"]["predicts_verifier_command"]["recommended_judgment"] is None
    label_proxy = next(item for item in anti_draft["recommended_challenge_judgments"] if item["challenge_family"] == "label_proxy_shortcuts")
    assert label_proxy["recommended_pass"] is False
