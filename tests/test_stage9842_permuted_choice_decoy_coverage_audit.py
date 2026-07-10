from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'scripts'))
    path = root / 'scripts/build_stage9842_permuted_choice_decoy_coverage_audit.py'
    spec = importlib.util.spec_from_file_location('stage9842', path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9842_root_row_id_strips_suffix():
    mod = _load()
    assert mod.root_row_id('abc123::mixed_replay') == 'abc123'
    assert mod.root_row_id('abc123') == 'abc123'


def test_stage9842_build_language_record_scores_decoy_follow_rate():
    mod = _load()
    manifest_index = {
        ('python', 'eval', 'r1'): {'counterfactual_role': 'positive_original'},
        ('python', 'strict_eval', 'r1'): {'counterfactual_role': 'mixed_replay', 'counterfactual_wrong_label': 'E'},
        ('python', 'eval', 'r2'): {'counterfactual_role': 'positive_original'},
        ('python', 'strict_eval', 'r2'): {'counterfactual_role': 'mixed_replay', 'counterfactual_wrong_label': 'D'},
    }
    hundred_index = {
        ('python', 'eval', 'r1'): {'target': 'A', 'pred': 'A', 'correct': True},
        ('python', 'strict_eval', 'r1'): {'pred': 'E', 'correct': False},
        ('python', 'eval', 'r2'): {'target': 'B', 'pred': 'B', 'correct': True},
        ('python', 'strict_eval', 'r2'): {'pred': 'B', 'correct': True},
    }
    gemma_index = {
        ('python', 'eval', 'r1'): {'predicted_label': 'A', 'correct': True},
        ('python', 'strict_eval', 'r1'): {'predicted_label': 'A', 'correct': True},
        ('python', 'eval', 'r2'): {'predicted_label': 'C', 'correct': False},
        ('python', 'strict_eval', 'r2'): {'predicted_label': 'D', 'correct': False},
    }
    record = mod.build_language_record(
        'python',
        manifest_index=manifest_index,
        hundred_index=hundred_index,
        gemma_index=gemma_index,
        bucket_cards={
            'python:eval': {'permutation_count': 5},
            'python:strict_eval': {'permutation_count': 5},
        },
        comparison_9840={'comparisons': {'python:eval': {'verdict': '100m_win'}, 'python:strict_eval': {'verdict': 'tie'}}},
    )
    assert record['paired_root_count'] == 2
    assert record['hundred_m']['eval_exact'] == 1.0
    assert record['hundred_m']['strict_eval_exact'] == 0.5
    assert record['hundred_m']['wrong_label_follow_rate_on_strict'] == 0.5
    assert record['gemma']['wrong_label_follow_rate_on_strict'] == 0.5
    assert record['packet_structure']['built_in_ablation_slice_present'] is False
