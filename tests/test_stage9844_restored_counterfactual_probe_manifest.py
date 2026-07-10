from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'scripts'))
    path = root / 'scripts/build_stage9844_restored_counterfactual_probe_manifest.py'
    spec = importlib.util.spec_from_file_location('stage9844', path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9844_role_to_split_is_expected():
    mod = _load()
    assert mod.ROLE_TO_SPLIT['positive_original'] == 'train'
    assert mod.ROLE_TO_SPLIT['evidence_removed'] == 'eval'
    assert mod.ROLE_TO_SPLIT['contradictory_evidence'] == 'strict_eval'


def test_stage9844_permute_and_assign_remaps_target_and_split():
    mod = _load()
    row = {
        'split': 'strict_eval',
        'target': {'decoder_text': 'A', 'edit_localization': 'A', 'target_ref': 'A'},
        'clean_state': {'edit_localization': 'A', 'edit_localization_target': 'A'},
        'input_state': {
            'candidate_choices': [
                'option A: alpha',
                'option B: beta',
                'option C: gamma',
                'option D: delta',
                'option E: epsilon',
            ],
            'task_observation': 'note option A',
            'visible_locality_evidence': 'hint option B',
        },
    }
    out = mod._permute_and_assign(row, {'A': 'C', 'B': 'A', 'C': 'B', 'D': 'D', 'E': 'E'}, 'eval')
    assert out['split'] == 'eval'
    assert out['target']['decoder_text'] == 'C'
    assert out['clean_state']['edit_localization'] == 'C'
    assert out['input_state']['candidate_choices'][0] == 'option A: beta'

