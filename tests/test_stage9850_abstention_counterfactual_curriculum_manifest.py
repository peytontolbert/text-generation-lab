from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'scripts'))
    path = root / 'scripts/build_stage9850_abstention_counterfactual_curriculum_manifest.py'
    spec = importlib.util.spec_from_file_location('stage9850', path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9850_abstain_label_constant():
    mod = _load()
    assert mod.ABSTAIN_LABEL == 'ABSTAIN_INSUFFICIENT_EVIDENCE'


def test_stage9850_rewrite_target_for_evidence_removed():
    mod = _load()
    row = {
        'counterfactual_role': 'evidence_removed',
        'clean_state': {'edit_localization': 'A', 'edit_localization_target': 'A'},
        'target': {'decoder_text': 'A', 'edit_localization': 'A', 'target_ref': 'A'},
    }
    mod._rewrite_target_for_role(row, 'evidence_removed')
    assert row['clean_state']['edit_localization'] == mod.ABSTAIN_LABEL
    assert row['target']['decoder_text'] == mod.ABSTAIN_LABEL
