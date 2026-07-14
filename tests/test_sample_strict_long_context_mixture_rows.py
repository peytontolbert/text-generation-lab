from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from sample_strict_long_context_mixture_rows import sample_strict_long_context_mixture_rows  # noqa: E402


def test_sample_strict_long_context_mixture_rows_preserves_all_without_caps(tmp_path: Path) -> None:
    rows_path = tmp_path / 'rows.jsonl'
    rows = [
        {'mixture_row_id': 'a', 'mixture_surface': 'full_context_rows', 'mixture_weight': 1.0, 'effective_split': 'train'},
        {'mixture_row_id': 'b', 'mixture_surface': 'retrieval_rows', 'mixture_weight': 2.0, 'effective_split': 'eval'},
        {'mixture_row_id': 'c', 'mixture_surface': 'memory_rows', 'mixture_weight': 0.5, 'effective_split': 'strict_eval'},
    ]
    rows_path.write_text('\n'.join(json.dumps(row, sort_keys=True) for row in rows) + '\n', encoding='utf-8')

    result = sample_strict_long_context_mixture_rows(
        rows_path=rows_path,
        output_dir=tmp_path / 'out',
    )
    sampled = [json.loads(line) for line in Path(result['manifest_path']).read_text(encoding='utf-8').splitlines() if line.strip()]
    assert result['row_count'] == 3
    assert [row['mixture_row_id'] for row in sampled] == ['a', 'b', 'c']
    assert result['split_cards']['train']['selected'] == 1
    assert result['split_cards']['eval']['selected'] == 1
    assert result['split_cards']['strict_eval']['selected'] == 1


def test_sample_strict_long_context_mixture_rows_applies_caps(tmp_path: Path) -> None:
    rows_path = tmp_path / 'rows.jsonl'
    rows = [
        {'mixture_row_id': 'a', 'mixture_surface': 'full_context_rows', 'mixture_weight': 1.0, 'effective_split': 'train'},
        {'mixture_row_id': 'b', 'mixture_surface': 'retrieval_rows', 'mixture_weight': 2.0, 'effective_split': 'train'},
        {'mixture_row_id': 'c', 'mixture_surface': 'memory_rows', 'mixture_weight': 0.5, 'effective_split': 'train'},
    ]
    rows_path.write_text('\n'.join(json.dumps(row, sort_keys=True) for row in rows) + '\n', encoding='utf-8')

    result = sample_strict_long_context_mixture_rows(
        rows_path=rows_path,
        output_dir=tmp_path / 'out',
        seed=7,
        max_train_rows=2,
    )
    sampled = [json.loads(line) for line in Path(result['manifest_path']).read_text(encoding='utf-8').splitlines() if line.strip()]
    assert result['row_count'] == 2
    assert result['split_cards']['train']['selected'] == 2
    assert len({row['mixture_row_id'] for row in sampled}) == 2


def test_sample_strict_long_context_mixture_rows_applies_quality_thresholds_and_filter_expr(tmp_path: Path) -> None:
    rows_path = tmp_path / 'rows.jsonl'
    rows = [
        {
            'mixture_row_id': 'a',
            'mixture_surface': 'full_context_rows',
            'mixture_weight': 1.0,
            'effective_split': 'train',
            'mixture_min_state_delta_ready_fraction': 0.86,
            'mixture_min_evidence_anchor_ready_fraction': 0.84,
            'join_type': 'multi_repo',
        },
        {
            'mixture_row_id': 'b',
            'mixture_surface': 'retrieval_rows',
            'mixture_weight': 2.0,
            'effective_split': 'train',
            'mixture_min_state_delta_ready_fraction': 0.79,
            'mixture_min_evidence_anchor_ready_fraction': 0.9,
            'join_type': 'multi_repo',
        },
        {
            'mixture_row_id': 'c',
            'mixture_surface': 'memory_rows',
            'mixture_weight': 0.5,
            'effective_split': 'train',
            'mixture_min_state_delta_ready_fraction': 0.91,
            'mixture_min_evidence_anchor_ready_fraction': 0.88,
            'join_type': 'single_repo',
        },
    ]
    rows_path.write_text('\n'.join(json.dumps(row, sort_keys=True) for row in rows) + '\n', encoding='utf-8')

    config_path = tmp_path / 'sampler.json'
    config_path.write_text(
        json.dumps(
            {
                'sampler_defaults': {
                    'seed': 0,
                    'max_train_rows': None,
                    'max_eval_rows': None,
                    'max_strict_rows': None,
                    'min_state_delta_ready_fraction': 0.8,
                    'min_evidence_anchor_ready_fraction': 0.8,
                    'filter_expr': 'join_type==multi_repo',
                }
            },
            sort_keys=True,
        ),
        encoding='utf-8',
    )

    result = sample_strict_long_context_mixture_rows(
        rows_path=rows_path,
        output_dir=tmp_path / 'out',
        config_path=config_path,
    )
    sampled = [json.loads(line) for line in Path(result['manifest_path']).read_text(encoding='utf-8').splitlines() if line.strip()]
    assert result['row_count'] == 1
    assert result['filtered_row_count'] == 1
    assert [row['mixture_row_id'] for row in sampled] == ['a']
