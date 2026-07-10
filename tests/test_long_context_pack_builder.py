from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from build_long_context_training_packs import build_long_context_packs  # noqa: E402
from build_stage8801_long_context_corpus_index import build_chunk_and_mention_shards  # noqa: E402


def _make_index(root: Path) -> Path:
    papers = root / 'papers'
    repos = root / 'repositories'
    datasets = root / 'datasets'
    (papers / 'paper_a').mkdir(parents=True)
    (repos / 'repo_a').mkdir(parents=True)
    (datasets / 'trace_a').mkdir(parents=True)
    (papers / 'paper_a' / 'method.txt').write_text(
        'online update improves convergence and keeps controller state stable\n' * 8,
        encoding='utf-8',
    )
    (repos / 'repo_a' / 'engine.py').write_text(
        'def online_update():\n    return "controller active"\n' * 12,
        encoding='utf-8',
    )
    (datasets / 'trace_a' / 'failure.txt').write_text(
        'runtime trace shows online update regression after patch\n' * 10,
        encoding='utf-8',
    )
    out = root / 'index'
    build_chunk_and_mention_shards(
        paper_roots=[papers],
        repo_roots=[repos],
        dataset_roots=[datasets],
        output_dir=out,
        paper_chunk_tokens=24,
        repo_chunk_tokens=24,
        trace_chunk_tokens=24,
        rows_per_shard=8,
    )
    return out


def test_build_long_context_packs_groups_examples_into_deduplicated_packs(tmp_path: Path) -> None:
    if importlib.util.find_spec('pyarrow') is None:
        pytest.skip('pyarrow not installed')
    index_dir = _make_index(tmp_path)
    import pyarrow.parquet as pq

    chunk_ids = []
    for shard in sorted((index_dir / 'chunks').glob('*.parquet')):
        for row in pq.read_table(shard).to_pylist():
            chunk_ids.append(str(row['chunk_id']))
    assert len(chunk_ids) >= 3

    examples = [
        {
            'example_id': 'ex1',
            'program_id': 'prog1',
            'context_token_count': 40,
            'rendered_chunk_ids': [chunk_ids[0], chunk_ids[1]],
            'query': {'text': 'q1'},
            'targets': {'final_answer': True, 'final_state': {'x': True}},
            'difficulty': {'level': 3},
            'quality': {'bucket': 'high'},
        },
        {
            'example_id': 'ex2',
            'program_id': 'prog2',
            'context_token_count': 36,
            'rendered_chunk_ids': [chunk_ids[1], chunk_ids[2]],
            'query': {'text': 'q2'},
            'targets': {'final_answer': False, 'final_state': {'y': False}},
            'difficulty': {'level': 4},
            'quality': {'bucket': 'high'},
        },
        {
            'example_id': 'ex3',
            'program_id': 'prog3',
            'context_token_count': 28,
            'rendered_chunk_ids': [chunk_ids[0]],
            'query': {'text': 'q3'},
            'targets': {'final_answer': True, 'final_state': {'z': True}},
            'difficulty': {'level': 2},
            'quality': {'bucket': 'medium'},
        },
    ]
    examples_path = tmp_path / 'examples.jsonl'
    examples_path.write_text(''.join(json.dumps(row) + '\n' for row in examples), encoding='utf-8')

    packs, pack_chunk_rows, training_rows, summary = build_long_context_packs(
        index_dir=index_dir,
        examples_path=examples_path,
        target_pack_tokens=120,
        min_pack_tokens=40,
    )

    assert packs
    assert summary['pack_count'] == len(packs)
    assert summary['total_examples_consumed'] == 3
    first_pack = packs[0]
    assert first_pack['pack_token_count'] >= 40
    assert first_pack['example_count'] >= 1
    assert len(first_pack['ordered_chunk_ids']) == len(set(first_pack['ordered_chunk_ids']))
    assert pack_chunk_rows
    assert all(row['pack_id'] for row in pack_chunk_rows)
    assert any(row['source_type'] == 'repo' for row in pack_chunk_rows)
    assert training_rows
    assert training_rows[0]['pack_id'] == first_pack['pack_id']
    assert training_rows[0]['context_rows']
    assert training_rows[0]['prompt_text']
    assert training_rows[0]['target_rows']
    assert any('text' in row and row['text'] for row in training_rows[0]['context_rows'])


def test_build_long_context_packs_supports_direct_context_examples(tmp_path: Path) -> None:
    examples = [
        {
            'example_id': 'ep1',
            'program_id': 'repo_a',
            'context_token_count': 60,
            'context_rows': [
                {'chunk_id': 'c1', 'source_type': 'local_repo', 'source_id': 'repo_a', 'path': 'src/a.py', 'token_count': 30, 'text': 'def a():\n    return 1\n'},
                {'chunk_id': 'c2', 'source_type': 'local_repo', 'source_id': 'repo_a', 'path': 'tests/test_a.py', 'token_count': 30, 'text': 'def test_a():\n    assert a() == 1\n'},
            ],
            'query': {'text': 'repair function a'},
            'targets': {'final_answer': 'fix a', 'final_state': {'tests': 'green'}},
            'difficulty': {'level': 3},
            'quality': {'bucket': 'high'},
        },
        {
            'example_id': 'ep2',
            'program_id': 'repo_b',
            'context_token_count': 50,
            'context_rows': [
                {'chunk_id': 'c2', 'source_type': 'local_repo', 'source_id': 'repo_a', 'path': 'tests/test_a.py', 'token_count': 30, 'text': 'def test_a():\n    assert a() == 1\n'},
                {'chunk_id': 'c3', 'source_type': 'paper', 'source_id': 'paper_x', 'path': 'method.txt', 'token_count': 20, 'text': 'use stable update rule'},
            ],
            'query': {'text': 'connect repo fix to paper grounding'},
            'targets': {'final_answer': 'use stable update rule', 'final_state': {'paper_grounded': True}},
            'difficulty': {'level': 4},
            'quality': {'bucket': 'high'},
        },
    ]
    examples_path = tmp_path / 'direct_examples.jsonl'
    examples_path.write_text(''.join(json.dumps(row) + '\n' for row in examples), encoding='utf-8')

    packs, pack_chunk_rows, training_rows, summary = build_long_context_packs(
        index_dir=None,
        examples_path=examples_path,
        target_pack_tokens=100,
        min_pack_tokens=50,
    )

    assert packs
    assert summary['chunk_source_mode'] == 'direct_context_rows'
    assert summary['total_examples_consumed'] == 2
    assert len(packs[0]['ordered_chunk_ids']) == len(set(packs[0]['ordered_chunk_ids']))
    assert any(row['source_type'] == 'paper' for row in pack_chunk_rows)
    assert training_rows[0]['context_rows']


def test_build_long_context_packs_supports_family_aware_reuse(tmp_path: Path) -> None:
    examples = [
        {
            'example_id': 'a1',
            'program_id': 'family_a',
            'context_token_count': 70,
            'context_rows': [
                {'chunk_id': 'ca1', 'source_type': 'local_repo', 'source_id': 'family_a', 'path': 'src/a1.py', 'token_count': 40, 'text': 'def alpha():\n    return 1\n'},
                {'chunk_id': 'shared', 'source_type': 'paper', 'source_id': 'paper_s', 'path': 'paper/shared.txt', 'token_count': 30, 'text': 'shared grounding context'},
            ],
            'query': {'text': 'repair alpha'},
            'targets': {'final_answer': 'fix alpha', 'final_state': {'ok': True}},
            'difficulty': {'level': 3},
            'quality': {'bucket': 'high'},
        },
        {
            'example_id': 'a2',
            'program_id': 'family_a',
            'context_token_count': 60,
            'context_rows': [
                {'chunk_id': 'ca2', 'source_type': 'repo', 'source_id': 'repo_x', 'path': 'src/a2.py', 'token_count': 30, 'text': 'def alpha_two():\n    return 2\n'},
                {'chunk_id': 'shared', 'source_type': 'paper', 'source_id': 'paper_s', 'path': 'paper/shared.txt', 'token_count': 30, 'text': 'shared grounding context'},
            ],
            'query': {'text': 'repair alpha two'},
            'targets': {'final_answer': 'fix alpha two', 'final_state': {'ok': True}},
            'difficulty': {'level': 3},
            'quality': {'bucket': 'high'},
        },
        {
            'example_id': 'b1',
            'program_id': 'family_b',
            'context_token_count': 65,
            'context_rows': [
                {'chunk_id': 'cb1', 'source_type': 'local_repo', 'source_id': 'family_b', 'path': 'src/b1.py', 'token_count': 35, 'text': 'def beta():\n    return 1\n'},
                {'chunk_id': 'shared', 'source_type': 'paper', 'source_id': 'paper_s', 'path': 'paper/shared.txt', 'token_count': 30, 'text': 'shared grounding context'},
            ],
            'query': {'text': 'repair beta'},
            'targets': {'final_answer': 'fix beta', 'final_state': {'ok': True}},
            'difficulty': {'level': 3},
            'quality': {'bucket': 'high'},
        },
    ]
    examples_path = tmp_path / 'family_examples.jsonl'
    examples_path.write_text(''.join(json.dumps(row) + '\n' for row in examples), encoding='utf-8')

    packs, pack_chunk_rows, training_rows, summary = build_long_context_packs(
        index_dir=None,
        examples_path=examples_path,
        target_pack_tokens=100,
        min_pack_tokens=80,
        allow_example_reuse=True,
        family_key_field='program_id',
        max_packs=2,
    )

    assert len(packs) == 2
    assert summary['duplicate_pack_count'] == 0
    assert summary['allow_example_reuse'] is True
    assert summary['family_key_field'] == 'program_id'
    assert {pack['seed_family_key'] for pack in packs} == {'family_a', 'family_b'}
    assert all(pack['pack_token_count'] >= 80 for pack in packs)
    assert any(row['pack_id'] == packs[0]['pack_id'] for row in pack_chunk_rows)
    assert training_rows[0]['context_rows']



def test_build_long_context_packs_skips_duplicate_chunk_unions_under_family_reuse(tmp_path: Path) -> None:
    shared_text = 'def shared():\n    return 1\n'
    examples = [
        {
            'example_id': 'a1',
            'program_id': 'family_a',
            'context_token_count': 80,
            'context_rows': [
                {'chunk_id': 'shared_local', 'source_type': 'local_repo', 'source_id': 'family_a', 'path': 'src/shared.py', 'token_count': 40, 'text': shared_text},
                {'chunk_id': 'shared_paper', 'source_type': 'paper', 'source_id': 'paper_s', 'path': 'paper/shared.txt', 'token_count': 40, 'text': 'shared grounding context'},
            ],
            'query': {'text': 'repair shared alpha'},
            'targets': {'final_answer': 'fix alpha', 'final_state': {'ok': True}},
            'difficulty': {'level': 3},
            'quality': {'bucket': 'high'},
        },
        {
            'example_id': 'b1',
            'program_id': 'family_b',
            'context_token_count': 70,
            'context_rows': [
                {'chunk_id': 'shared_local', 'source_type': 'local_repo', 'source_id': 'family_a', 'path': 'src/shared.py', 'token_count': 40, 'text': shared_text},
                {'chunk_id': 'shared_paper', 'source_type': 'paper', 'source_id': 'paper_s', 'path': 'paper/shared.txt', 'token_count': 40, 'text': 'shared grounding context'},
            ],
            'query': {'text': 'repair shared beta'},
            'targets': {'final_answer': 'fix beta', 'final_state': {'ok': True}},
            'difficulty': {'level': 3},
            'quality': {'bucket': 'high'},
        },
    ]
    examples_path = tmp_path / 'duplicate_family_examples.jsonl'
    examples_path.write_text(''.join(json.dumps(row) + '\n' for row in examples), encoding='utf-8')

    packs, pack_chunk_rows, training_rows, summary = build_long_context_packs(
        index_dir=None,
        examples_path=examples_path,
        target_pack_tokens=500,
        min_pack_tokens=50,
        allow_example_reuse=True,
        family_key_field='program_id',
        max_packs=2,
    )

    assert len(packs) == 1
    assert summary['pack_count'] == 1
    assert summary['duplicate_pack_count'] == 1
    assert len(training_rows) == 1
    assert {row['chunk_id'] for row in pack_chunk_rows} == {'shared_local', 'shared_paper'}



def test_build_long_context_packs_fast_fill_prefers_novel_tokens(tmp_path: Path) -> None:
    examples = [
        {
            'example_id': 'seed',
            'program_id': 'seed_family',
            'context_token_count': 600000,
            'context_rows': [
                {'chunk_id': 'seed_a', 'source_type': 'local_repo', 'source_id': 'seed_family', 'path': 'src/seed_a.py', 'token_count': 100, 'text': 'seed a'},
                {'chunk_id': 'seed_b', 'source_type': 'paper', 'source_id': 'paper_seed', 'path': 'paper/seed.txt', 'token_count': 100, 'text': 'seed b'},
            ],
            'query': {'text': 'seed query'},
            'targets': {'final_answer': 'seed answer', 'final_state': {'ok': True}},
            'difficulty': {'level': 3},
            'quality': {'bucket': 'high'},
        },
        {
            'example_id': 'overlap_big',
            'program_id': 'other_family',
            'context_token_count': 900000,
            'context_rows': [
                {'chunk_id': 'seed_a', 'source_type': 'local_repo', 'source_id': 'seed_family', 'path': 'src/seed_a.py', 'token_count': 100, 'text': 'seed a'},
                {'chunk_id': 'overlap_only', 'source_type': 'repo', 'source_id': 'repo_overlap', 'path': 'src/overlap.py', 'token_count': 50, 'text': 'overlap only'},
            ],
            'query': {'text': 'overlap query'},
            'targets': {'final_answer': 'overlap answer', 'final_state': {'ok': True}},
            'difficulty': {'level': 3},
            'quality': {'bucket': 'high'},
        },
        {
            'example_id': 'novel_smaller',
            'program_id': 'third_family',
            'context_token_count': 700000,
            'context_rows': [
                {'chunk_id': 'novel_a', 'source_type': 'repo', 'source_id': 'repo_novel', 'path': 'src/novel_a.py', 'token_count': 90, 'text': 'novel a'},
                {'chunk_id': 'novel_b', 'source_type': 'paper', 'source_id': 'paper_novel', 'path': 'paper/novel.txt', 'token_count': 90, 'text': 'novel b'},
            ],
            'query': {'text': 'novel query'},
            'targets': {'final_answer': 'novel answer', 'final_state': {'ok': True}},
            'difficulty': {'level': 3},
            'quality': {'bucket': 'high'},
        },
    ]
    examples_path = tmp_path / 'fast_fill_examples.jsonl'
    examples_path.write_text(''.join(json.dumps(row) + '\n' for row in examples), encoding='utf-8')

    packs, _, _, summary = build_long_context_packs(
        index_dir=None,
        examples_path=examples_path,
        target_pack_tokens=1_000_000,
        min_pack_tokens=100,
        allow_example_reuse=False,
    )

    assert summary['pack_count'] >= 1
    first_ids = packs[0]['example_ids']
    assert 'seed' in first_ids
    assert 'novel_smaller' in first_ids
    assert first_ids.index('novel_smaller') < len(first_ids)



def test_build_long_context_packs_prioritizes_grounded_context_rows(tmp_path: Path) -> None:
    examples = [
        {
            'example_id': 'ep1',
            'program_id': 'repo_a',
            'context_token_count': 100,
            'context_rows': [
                {'chunk_id': 'd1', 'source_type': 'dataset', 'source_id': 'trace_a', 'path': 'trace/error.txt', 'token_count': 20, 'text': 'runtime trace around tensor_loader', 'role': 'trace_analogue'},
                {'chunk_id': 'p1', 'source_type': 'paper', 'source_id': 'paper_x', 'path': 'paper/method.txt', 'token_count': 20, 'text': 'stable tensor loader verification', 'role': 'algorithm_grounding'},
                {'chunk_id': 'r1', 'source_type': 'local_repo', 'source_id': 'repo_a', 'path': 'src/loader.py', 'token_count': 30, 'text': 'def tensor_loader(x): return x', 'role': 'seed_change'},
                {'chunk_id': 't1', 'source_type': 'local_repo', 'source_id': 'repo_a', 'path': 'tests/test_loader.py', 'token_count': 30, 'text': 'assert tensor_loader(1) == 1', 'role': 'verification_constraint'},
            ],
            'query': {'text': 'repair tensor loader'},
            'targets': {'final_answer': 'fix tensor loader', 'final_state': {'tests': 'green'}},
            'difficulty': {'level': 3},
            'quality': {'bucket': 'high'},
        }
    ]
    examples_path = tmp_path / 'ordered_examples.jsonl'
    examples_path.write_text(''.join(json.dumps(row) + '\n' for row in examples), encoding='utf-8')

    _, _, training_rows, _ = build_long_context_packs(
        index_dir=None,
        examples_path=examples_path,
        target_pack_tokens=100,
        min_pack_tokens=50,
    )

    ordered = training_rows[0]['context_rows']
    assert [row['chunk_id'] for row in ordered[:4]] == ['t1', 'r1', 'p1', 'd1']
    assert [row['role'] for row in ordered[:4]] == [
        'verification_constraint',
        'seed_change',
        'algorithm_grounding',
        'trace_analogue',
    ]
    assert ordered[0]['source_id'] == 'repo_a'
