from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'scripts'))
    path = root / 'scripts/build_stage9843_refresh_permuted_choice_review_cards.py'
    spec = importlib.util.spec_from_file_location('stage9843', path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9843_challenge_patch_label_proxy_stays_provisional():
    mod = _load()
    patch = mod._challenge_patch(
        'label_proxy_shortcuts',
        {
            'hundred_m': {'wrong_label_follow_rate_on_strict': 0.0},
            'gemma': {'wrong_label_follow_rate_on_strict': 0.2},
            'packet_structure': {'built_in_decoy_slice_present': True},
        },
    )
    assert patch['cell_specific_card_present'] is True
    assert patch['passed'] is False


def test_stage9843_challenge_patch_cross_model_surface_fairness_passes():
    mod = _load()
    patch = mod._challenge_patch(
        'cross_model_surface_fairness',
        {
            'packet_structure': {'built_in_decoy_slice_present': True},
        },
    )
    assert patch['cell_specific_card_present'] is True
    assert patch['passed'] is True
