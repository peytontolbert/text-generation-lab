from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from filter_packable_examples_by_novelty import filter_packable_examples_by_novelty  # noqa: E402


def _write_examples(path: Path, rows: list[dict]) -> None:
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')


def test_filter_packable_examples_by_novelty_keeps_one_per_group(tmp_path: Path) -> None:
    path = tmp_path / 'examples.jsonl'
    rows = [
        {
            'example_id': 'a1',
            'program_id': 'family_a',
            'context_token_count': 100,
            'rendered_chunk_ids': ['c1', 'c2', 'c3'],
            'quality': {'quality_score': 0.99},
        },
        {
            'example_id': 'a2',
            'program_id': 'family_a',
            'context_token_count': 90,
            'rendered_chunk_ids': ['c1', 'c2', 'c3'],
            'quality': {'quality_score': 0.98},
        },
        {
            'example_id': 'b1',
            'program_id': 'family_b',
            'context_token_count': 80,
            'rendered_chunk_ids': ['d1', 'd2', 'd3'],
            'quality': {'quality_score': 0.97},
        },
    ]
    _write_examples(path, rows)

    kept, reports, summary = filter_packable_examples_by_novelty(
        examples_path=path,
        min_keep_per_group=1,
        min_global_novel_ratio=0.9,
        min_global_novel_chunks=10,
        min_group_novel_ratio=0.9,
        min_group_novel_chunks=10,
    )

    assert [row['example_id'] for row in kept] == ['a1', 'b1']
    assert summary['kept_example_count'] == 2
    assert summary['rejected_example_count'] == 1
    rejected = [row for row in reports if row['decision'] == 'reject']
    assert rejected[0]['example_id'] == 'a2'
    assert rejected[0]['reason'] == 'low_global_novelty'


def test_filter_packable_examples_by_novelty_caps_verification_family_reuse(tmp_path: Path) -> None:
    path = tmp_path / 'examples.jsonl'
    rows = [
        {
            'example_id': 'a1',
            'program_id': 'family_a',
            'context_token_count': 100,
            'rendered_chunk_ids': ['c1', 'c2', 'c3', 'c4'],
            'quality': {'quality_score': 0.99},
            'query': {'selected_tests': ['parameter-golf/data/analyze_spectral_sidecar.py', 'parameter-golf/data/profile_validation_reproducibility.py', 'parameter-golf/data/tokenizer_specs.json']},
        },
        {
            'example_id': 'a2',
            'program_id': 'family_a',
            'context_token_count': 95,
            'rendered_chunk_ids': ['n1', 'n2', 'n3', 'n4'],
            'quality': {'quality_score': 0.98},
            'query': {'selected_tests': ['parameter-golf/data/profile_validation_reproducibility.py', 'parameter-golf/data/analyze_spectral_sidecar.py', 'peytontolbert-parameter-golf/data/tokenizer_specs.json']},
        },
        {
            'example_id': 'b1',
            'program_id': 'family_b',
            'context_token_count': 90,
            'rendered_chunk_ids': ['m1', 'm2', 'm3', 'm4'],
            'quality': {'quality_score': 0.97},
            'query': {'selected_tests': ['tests/test_engine.py']},
        },
    ]
    _write_examples(path, rows)

    kept, reports, summary = filter_packable_examples_by_novelty(
        examples_path=path,
        min_keep_per_group=1,
        min_global_novel_ratio=0.5,
        min_global_novel_chunks=3,
        min_group_novel_ratio=0.5,
        min_group_novel_chunks=3,
        max_examples_per_verification_family=1,
    )

    assert [row['example_id'] for row in kept] == ['a1', 'b1']
    rejected = [row for row in reports if row['decision'] == 'reject']
    assert rejected[0]['example_id'] == 'a2'
    assert rejected[0]['reason'] == 'verification_family_saturated'
    assert summary['kept_verification_family_counts']['analyze_spectral_sidecar|profile_validation_reproducibility|tokenizer_specs'] == 1


def test_filter_packable_examples_by_novelty_caps_group_reuse(tmp_path: Path) -> None:
    path = tmp_path / 'examples.jsonl'
    rows = [
        {
            'example_id': 'a1',
            'program_id': 'family_a',
            'context_token_count': 100,
            'rendered_chunk_ids': ['c1', 'c2', 'c3', 'c4'],
            'quality': {'quality_score': 0.99},
            'query': {'selected_tests': ['tests/test_alpha.py']},
        },
        {
            'example_id': 'a2',
            'program_id': 'family_a',
            'context_token_count': 99,
            'rendered_chunk_ids': ['n1', 'n2', 'n3', 'n4'],
            'quality': {'quality_score': 0.98},
            'query': {'selected_tests': ['tests/test_beta.py']},
        },
        {
            'example_id': 'b1',
            'program_id': 'family_b',
            'context_token_count': 90,
            'rendered_chunk_ids': ['m1', 'm2', 'm3', 'm4'],
            'quality': {'quality_score': 0.97},
            'query': {'selected_tests': ['tests/test_gamma.py']},
        },
    ]
    _write_examples(path, rows)

    kept, reports, summary = filter_packable_examples_by_novelty(
        examples_path=path,
        min_keep_per_group=1,
        min_global_novel_ratio=0.5,
        min_global_novel_chunks=3,
        min_group_novel_ratio=0.5,
        min_group_novel_chunks=3,
        max_keep_per_group=1,
    )

    assert [row['example_id'] for row in kept] == ['a1', 'b1']
    rejected = [row for row in reports if row['decision'] == 'reject']
    assert rejected[0]['example_id'] == 'a2'
    assert rejected[0]['reason'] == 'group_saturated'
    assert summary['max_keep_per_group'] == 1


def test_filter_packable_examples_by_novelty_allows_novel_follow_on_example(tmp_path: Path) -> None:
    path = tmp_path / 'examples.jsonl'
    rows = [
        {
            'example_id': 'a1',
            'program_id': 'family_a',
            'context_token_count': 100,
            'rendered_chunk_ids': ['c1', 'c2', 'c3', 'c4'],
            'quality': {'quality_score': 0.99},
        },
        {
            'example_id': 'a2',
            'program_id': 'family_a',
            'context_token_count': 95,
            'rendered_chunk_ids': ['c1', 'c2', 'n1', 'n2', 'n3', 'n4'],
            'quality': {'quality_score': 0.98},
        },
    ]
    _write_examples(path, rows)

    kept, reports, summary = filter_packable_examples_by_novelty(
        examples_path=path,
        min_keep_per_group=1,
        min_global_novel_ratio=0.5,
        min_global_novel_chunks=3,
        min_group_novel_ratio=0.5,
        min_group_novel_chunks=3,
    )

    assert [row['example_id'] for row in kept] == ['a1', 'a2']
    kept_reports = [row for row in reports if row['decision'] == 'keep']
    assert kept_reports[1]['reason'] == 'novel_global_and_group'
    assert summary['unique_kept_chunk_count'] == 8
