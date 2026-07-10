from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'scripts'))
    path = root / 'scripts/build_stage9833_permuted_choice_execution_manifest.py'
    spec = importlib.util.spec_from_file_location('stage9833', path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9833_builds_permuted_manifest_with_five_permutations_per_bucket():
    mod = _load()
    rows = mod.build_rows()
    audit = mod.build_audit(rows)
    assert audit['passed'] is True
    assert audit['rows'] == 60
    assert audit['split_counts'] == {'eval': 20, 'strict_eval': 20, 'train': 20}
    for lang in mod.LANGS:
        for split in mod.SPLITS:
            card = audit['bucket_cards'][f'{lang}:{split}']
            assert card['rows'] == 5
            assert card['label_count'] == 5
            assert card['safe_signature_unique_count'] == 5
            assert card['permutation_count'] == 5
            assert card['choice_list_unique_count'] == 5


def test_stage9833_remaps_labels_and_visible_option_mentions_consistently():
    mod = _load()
    rows = mod.build_rows()
    mixed = next(row for row in rows if row.get('split') == 'strict_eval' and row.get('obligation_type') == 'MIXED_REPLAY')
    mapping = mixed['choice_permutation_map']
    target = (mixed.get('target') or {}).get('decoder_text')
    assert target in mod.LABELS
    obs = (mixed.get('input_state') or {}).get('task_observation') or ''
    wrong = mixed.get('counterfactual_wrong_label')
    assert f'option {wrong}' in obs
    choices = (mixed.get('input_state') or {}).get('candidate_choices') or []
    assert len(choices) == 5
    assert any(choice.startswith('option A:') for choice in choices)
    assert mapping != {label: label for label in mod.LABELS}
