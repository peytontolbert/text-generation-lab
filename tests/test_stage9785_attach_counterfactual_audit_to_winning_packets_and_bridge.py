from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9785_attach_counterfactual_audit_to_winning_packets_and_bridge.py"
    spec = importlib.util.spec_from_file_location("stage9785", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9785_attaches_stage9784_evidence_to_winning_packets_and_bridge():
    mod = _load()
    built = mod.build_refresh()
    assert built["passed"] is True
    assert built["metrics"]["refreshed_cells"] == 4

    root = Path(__file__).resolve().parents[1]
    rubric = json.loads((root / 'runs/local/artifacts/stage9752_supported_standalone_review_packets/review_packets/standalone_100m_weights__python__edit_localization/expert_maintainer_rubric_review.json').read_text(encoding='utf-8'))
    anti = json.loads((root / 'runs/local/artifacts/stage9752_supported_standalone_review_packets/review_packets/standalone_100m_weights__python__edit_localization/anti_cheat_review_card.json').read_text(encoding='utf-8'))
    refresh = json.loads((root / 'runs/local/artifacts/stage9785_attach_counterfactual_audit_to_winning_packets_and_bridge/attach_counterfactual_audit_to_winning_packets_and_bridge.json').read_text(encoding='utf-8'))
    bridge_row = next(row for row in refresh['records'] if row['cell_key'] == 'standalone_100m_weights::python::edit_localization')

    assert rubric['evidence_draft_path'].endswith('stage9784_winning_edit_localization_counterfactual_anti_cheat_audit/winning_edit_localization_counterfactual_anti_cheat_audit.json')
    assert rubric['counterfactual_audit_summary']['state_hash'] == '174f1f24aefe3e7405178393af9f1a59be0575330632067f85c1c6c3502af436'
    assert anti['counterfactual_audit_summary']['metadata_only_baseline'] == 0.0
    assert anti['counterfactual_audit_summary']['same_surface_verified'] is True
    assert any(item['kind'] == 'counterfactual_anti_cheat_audit_support' for item in bridge_row['attached_evidence'])
    assert any(item['kind'] == 'local_same_surface_gemma_rerun_support' for item in bridge_row['attached_evidence'])
    assert 'same_surface_win_present_but_review_confirmation_still_missing' in bridge_row['blockers']
