from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9879_current_margin_multilingual_winner_review_packets.py"
    spec = importlib.util.spec_from_file_location("stage9879", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9879_materializes_review_packets_for_current_margin_frontier():
    mod = _load()
    built = mod.build_packets()
    assert built["passed"] is True
    assert built["metrics"]["winning_cells"] == 4
    assert built["metrics"]["rubric_stub_files"] == 4
    assert built["metrics"]["anti_cheat_stub_files"] == 4
    assert built["metrics"]["rubric_recommendation_files"] == 4
    assert built["metrics"]["anti_cheat_recommendation_files"] == 4
    assert built["metrics"]["cells_with_label_proxy_shortcut_risk"] == 4
    assert built["metrics"]["cells_with_cross_model_fairness_support"] == 4


def test_stage9879_python_packet_tracks_strict_tie_and_shortcut_risk():
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
    assert rubric["strict_exact_100m"] == 0.5
    assert rubric["strict_exact_gemma"] == 0.5
    assert rubric["language_family_verdict"] == "100m_better"
    assert anti["status"] == "pending_cell_specific_review"
    assert anti["harder_counterfactual_strict_verdict"] == "tie"
    assert anti["abstention_counterfactual_strict_verdict"] == "gemma_win"
    assert rubric_draft["recommended_subskills"]["localizes_edit_scope"]["recommended_judgment"] is True
    label_proxy = next(item for item in anti_draft["recommended_challenge_judgments"] if item["challenge_family"] == "label_proxy_shortcuts")
    assert label_proxy["recommended_pass"] is False
    fairness = next(item for item in anti_draft["recommended_challenge_judgments"] if item["challenge_family"] == "cross_model_surface_fairness")
    assert fairness["recommended_pass"] is True
