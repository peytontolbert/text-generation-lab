from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'scripts'))
    path = root / 'scripts/build_stage9841_permuted_choice_winner_review_packets.py'
    spec = importlib.util.spec_from_file_location('stage9841', path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9841_aggregate_bucket_rows_computes_exact():
    mod = _load()
    rows = [
        {'language_family': 'python', 'split': 'eval', 'correct': True},
        {'language_family': 'python', 'split': 'eval', 'correct': False},
        {'language_family': 'python', 'split': 'strict_eval', 'correct': True},
        {'language_family': 'rust', 'split': 'eval', 'correct': True},
    ]
    buckets = mod.aggregate_bucket_rows(rows, language_field='language_family')
    assert buckets['python:eval']['rows'] == 2
    assert buckets['python:eval']['correct'] == 1
    assert buckets['python:eval']['exact'] == 0.5
    assert buckets['python:strict_eval']['exact'] == 1.0
    assert buckets['rust:eval']['exact'] == 1.0


def test_stage9841_label_proxy_shortcuts_recommendation_is_provisional():
    mod = _load()
    recommendations = mod._challenge_recommendations(
        ['label_proxy_shortcuts', 'cross_model_surface_fairness'],
        language_row={
            'language_family': 'python',
            'hundred_m': {'eval': {'exact': 0.6}, 'strict_eval': {'exact': 0.6}},
            'gemma': {'eval': {'exact': 0.2}, 'strict_eval': {'exact': 0.6}},
            'comparisons': {'eval': {'verdict': '100m_win'}, 'strict_eval': {'verdict': 'tie'}},
            'row_counts': {'hundred_m': 10, 'gemma': 10},
        },
        audit_9833={
            'bucket_cards': {
                'python:eval': {'permutation_count': 5},
                'python:strict_eval': {'permutation_count': 5},
            }
        },
        contract_9833={'manifest_sha256': 'abc123'},
        gemma_rows_present=True,
    )
    label_proxy = next(row for row in recommendations if row['challenge_family'] == 'label_proxy_shortcuts')
    fairness = next(row for row in recommendations if row['challenge_family'] == 'cross_model_surface_fairness')
    assert label_proxy['recommended_pass'] is None
    assert label_proxy['confidence'] == 'medium'
    assert 'abc123' in ' '.join(label_proxy['reviewer_notes'])
    assert fairness['recommended_pass'] is True
