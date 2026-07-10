from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from build_strict_long_context_episode_packs import build_strict_long_context_episode_packs  # noqa: E402


def _write_jsonl(path: Path, rows: list[dict]) -> Path:
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')
    return path


def _example(*, example_id: str, repo_id: str, quality: float, repo_chunk: str, paper_chunk: str, test_chunk: str) -> dict:
    return {
        'example_id': example_id,
        'repo_id': repo_id,
        'program_id': repo_id,
        'context_token_count': 120,
        'context_rows': [
            {'chunk_id': repo_chunk, 'source_type': 'repo', 'source_id': repo_id, 'path': f'{repo_id}/src/main.py', 'token_count': 50, 'text': f'def solve_{repo_id}(): return 1', 'role': 'cross_repo_analogue'},
            {'chunk_id': paper_chunk, 'source_type': 'paper', 'source_id': f'paper_{repo_id}', 'path': f'{repo_id}/paper/method.txt', 'token_count': 30, 'text': 'algorithm grounding for stable verification', 'role': 'algorithm_grounding'},
            {'chunk_id': test_chunk, 'source_type': 'local_repo', 'source_id': repo_id, 'path': f'{repo_id}/tests/test_main.py', 'token_count': 40, 'text': 'assert solve() == 1', 'role': 'verification_constraint'},
        ],
        'query': {
            'text': f'Repository: {repo_id}\nChanged files: src/main.py\nVerification targets: tests/test_main.py\nKey symbols: solve_{repo_id}',
            'seed_paths': ['src/main.py'],
            'selected_tests': ['tests/test_main.py'],
            'seed_symbols': [f'solve_{repo_id}'],
        },
        'targets': {
            'final_answer': 'Patch intent: update src/main.py while keeping tests/test_main.py satisfied.',
            'final_state': {
                'expected_changed_files': ['src/main.py'],
                'verification_targets': ['tests/test_main.py'],
                'execution_route': 'COMMIT_PLUS_VERIFY',
            },
        },
        'quality': {
            'quality_score': quality,
            'quality_report': {'overall_score': quality},
        },
        'difficulty': {'level': 4},
    }


def test_build_strict_long_context_episode_packs_builds_high_quality_pack(tmp_path: Path) -> None:
    rows = [
        _example(example_id='ex1', repo_id='repo1', quality=0.97, repo_chunk='r1', paper_chunk='p1', test_chunk='t1'),
        _example(example_id='ex2', repo_id='repo2', quality=0.96, repo_chunk='r2', paper_chunk='p2', test_chunk='t2'),
        _example(example_id='ex3', repo_id='repo3', quality=0.98, repo_chunk='r3', paper_chunk='p3', test_chunk='t3'),
        _example(example_id='ex4', repo_id='repo4', quality=0.95, repo_chunk='r4', paper_chunk='p4', test_chunk='t4'),
    ]
    examples = _write_jsonl(tmp_path / 'examples.jsonl', rows)

    packs, pack_chunk_rows, training_rows, reports, summary = build_strict_long_context_episode_packs(
        example_paths=[examples],
        output_dir=tmp_path / 'out',
        target_pack_tokens=1000,
        min_pack_tokens=200,
        min_example_quality=0.94,
        min_avg_example_quality=0.95,
        min_distinct_repos=4,
        min_verification_rows=4,
        min_locality_ready_fraction=0.0,
        min_retrieval_ready_fraction=0.0,
        min_long_range_join_ready_fraction=0.0,
        min_target_rows_for_lost_state_probe=4,
        min_programs_for_lost_state_probe=4,
    )

    assert len(packs) == 1
    assert reports[0]['distinct_repo_count'] == 4
    assert reports[0]['avg_example_quality'] >= 0.95
    assert reports[0]['fatal_reasons'] == []
    assert summary['pack_count'] == 1
    assert any(row['source_type'] == 'paper' for row in pack_chunk_rows)
    assert training_rows[0]['context_rows']


def test_build_strict_long_context_episode_packs_fails_when_pack_quality_is_weak(tmp_path: Path) -> None:
    rows = [
        _example(example_id='ex1', repo_id='repo1', quality=0.97, repo_chunk='r1', paper_chunk='p1', test_chunk='t1'),
        _example(example_id='ex2', repo_id='repo2', quality=0.96, repo_chunk='r2', paper_chunk='p2', test_chunk='t2'),
        _example(example_id='ex3', repo_id='repo3', quality=0.98, repo_chunk='r3', paper_chunk='p3', test_chunk='t3'),
    ]
    examples = _write_jsonl(tmp_path / 'examples.jsonl', rows)

    with pytest.raises(ValueError, match='strict_pack_quality_failure'):
        build_strict_long_context_episode_packs(
            example_paths=[examples],
            output_dir=tmp_path / 'out',
            target_pack_tokens=300,
            min_pack_tokens=200,
            min_example_quality=0.94,
            min_avg_example_quality=0.95,
            min_distinct_repos=4,
            min_verification_rows=4,
            min_target_rows_for_lost_state_probe=4,
            min_programs_for_lost_state_probe=4,
        )


def test_build_strict_long_context_episode_packs_fails_underfilled_tail_pack(tmp_path: Path) -> None:
    rows = [
        _example(example_id='ex1', repo_id='repo1', quality=0.97, repo_chunk='r1', paper_chunk='p1', test_chunk='t1'),
        _example(example_id='ex2', repo_id='repo2', quality=0.96, repo_chunk='r2', paper_chunk='p2', test_chunk='t2'),
        _example(example_id='ex3', repo_id='repo3', quality=0.98, repo_chunk='r3', paper_chunk='p3', test_chunk='t3'),
        _example(example_id='ex4', repo_id='repo4', quality=0.95, repo_chunk='r4', paper_chunk='p4', test_chunk='t4'),
    ]
    examples = _write_jsonl(tmp_path / 'examples.jsonl', rows)

    with pytest.raises(ValueError, match='underfilled_pack'):
        build_strict_long_context_episode_packs(
            example_paths=[examples],
            output_dir=tmp_path / 'out',
            target_pack_tokens=300,
            min_pack_tokens=250,
            min_example_quality=0.94,
            min_avg_example_quality=0.95,
            min_distinct_repos=2,
            min_verification_rows=2,
            min_target_rows_for_lost_state_probe=4,
            min_programs_for_lost_state_probe=2,
        )


def test_build_strict_long_context_episode_packs_fails_when_training_signal_probe_coverage_is_missing(tmp_path: Path) -> None:
    rows = [
        _example(example_id='ex1', repo_id='repo1', quality=0.97, repo_chunk='r1', paper_chunk='p1', test_chunk='t1'),
        _example(example_id='ex2', repo_id='repo2', quality=0.96, repo_chunk='r2', paper_chunk='p2', test_chunk='t2'),
        _example(example_id='ex3', repo_id='repo3', quality=0.98, repo_chunk='r3', paper_chunk='p3', test_chunk='t3'),
        _example(example_id='ex4', repo_id='repo4', quality=0.95, repo_chunk='r4', paper_chunk='p4', test_chunk='t4'),
    ]
    examples = _write_jsonl(tmp_path / 'examples.jsonl', rows)

    with pytest.raises(ValueError, match='insufficient_lost_state_probe_coverage'):
        build_strict_long_context_episode_packs(
            example_paths=[examples],
            output_dir=tmp_path / 'out',
            target_pack_tokens=1000,
            min_pack_tokens=200,
            min_example_quality=0.94,
            min_avg_example_quality=0.95,
            min_distinct_repos=4,
            min_verification_rows=4,
        )
