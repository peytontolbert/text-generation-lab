from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from augment_session_episode_context import augment_session_episode_context  # noqa: E402
from long_context_parquet import shard_path, write_parquet_shard  # noqa: E402


def test_augment_session_episode_context_adds_strict_grounding_and_doc_neighbors(tmp_path: Path) -> None:
    if importlib.util.find_spec('pyarrow') is None:
        pytest.skip('pyarrow not installed')

    index_dir = tmp_path / 'index'
    chunks_dir = index_dir / 'chunks'
    mentions_dir = index_dir / 'chunk_mentions'
    chunks_dir.mkdir(parents=True)
    mentions_dir.mkdir(parents=True)

    chunks = [
        {
            'chunk_id': 'repo_chunk_1',
            'source_type': 'repo',
            'source_id': 'other_repo',
            'doc_id': 'other_repo/src/loader.py',
            'chunk_index': 0,
            'modality': 'code',
            'token_count': 40,
            'text': 'def tensor_loader(shape_error):\n    return shape_error\n',
            'metadata_json': json.dumps({'path': 'other_repo/src/loader.py'}),
        },
        {
            'chunk_id': 'paper_chunk_1',
            'source_type': 'paper',
            'source_id': 'paper_a',
            'doc_id': 'paper_a/algorithm.txt',
            'chunk_index': 0,
            'modality': 'text',
            'token_count': 35,
            'text': 'Tensor loader algorithm and verification procedure under execution.',
            'metadata_json': json.dumps({'path': 'paper_a/algorithm.txt'}),
        },
        {
            'chunk_id': 'repo_chunk_2',
            'source_type': 'repo',
            'source_id': 'other_repo',
            'doc_id': 'other_repo/src/loader.py',
            'chunk_index': 1,
            'modality': 'code',
            'token_count': 24,
            'text': 'def tensor_loader_neighbor(runtime_trace):\n    return runtime_trace\n',
            'metadata_json': json.dumps({'path': 'other_repo/src/loader.py'}),
        },
        {
            'chunk_id': 'dataset_chunk_1',
            'source_type': 'dataset',
            'source_id': 'trace_a',
            'doc_id': 'trace_a/error_trace.txt',
            'chunk_index': 0,
            'modality': 'text',
            'token_count': 25,
            'text': 'Runtime error trace for loader shape mismatch in tensor pipeline.',
            'metadata_json': json.dumps({'path': 'trace_a/error_trace.txt'}),
        },
    ]
    mentions = [
        {'term': 'tensor', 'chunk_id': 'repo_chunk_1', 'source_type': 'repo', 'source_id': 'other_repo', 'doc_id': 'other_repo/src/loader.py'},
        {'term': 'loader', 'chunk_id': 'repo_chunk_1', 'source_type': 'repo', 'source_id': 'other_repo', 'doc_id': 'other_repo/src/loader.py'},
        {'term': 'shape_error', 'chunk_id': 'repo_chunk_1', 'source_type': 'repo', 'source_id': 'other_repo', 'doc_id': 'other_repo/src/loader.py'},
        {'term': 'tensor', 'chunk_id': 'paper_chunk_1', 'source_type': 'paper', 'source_id': 'paper_a', 'doc_id': 'paper_a/algorithm.txt'},
        {'term': 'loader', 'chunk_id': 'paper_chunk_1', 'source_type': 'paper', 'source_id': 'paper_a', 'doc_id': 'paper_a/algorithm.txt'},
        {'term': 'verification', 'chunk_id': 'paper_chunk_1', 'source_type': 'paper', 'source_id': 'paper_a', 'doc_id': 'paper_a/algorithm.txt'},
        {'term': 'loader', 'chunk_id': 'dataset_chunk_1', 'source_type': 'dataset', 'source_id': 'trace_a', 'doc_id': 'trace_a/error_trace.txt'},
        {'term': 'trace', 'chunk_id': 'dataset_chunk_1', 'source_type': 'dataset', 'source_id': 'trace_a', 'doc_id': 'trace_a/error_trace.txt'},
        {'term': 'tensor', 'chunk_id': 'dataset_chunk_1', 'source_type': 'dataset', 'source_id': 'trace_a', 'doc_id': 'trace_a/error_trace.txt'},
    ]
    write_parquet_shard(shard_path(chunks_dir, 'chunks', 0), chunks)
    write_parquet_shard(shard_path(mentions_dir, 'chunk_mentions', 0), mentions)

    episodes = tmp_path / 'episodes.jsonl'
    episodes.write_text(
        json.dumps(
            {
                'episode_id': 'ep1',
                'repo_id': 'local_repo',
                'goal': 'Modify repository files to preserve behavior under execution-backed maintenance.\nChanged files: src/loader.py\nVerification targets: tests/test_loader.py\nKey symbols: tensor_loader\nExecution route: PATCH_PLUS_EXEC',
                'seed_paths': ['src/loader.py'],
                'seed_symbols': ['tensor_loader', 'shape_error'],
                'selected_tests': ['tests/test_loader.py'],
                'context_token_count': 30,
                'context_rows': [
                    {
                        'chunk_id': 'local_seed_1',
                        'source_type': 'local_repo',
                        'source_id': 'local_repo',
                        'path': 'src/loader.py',
                        'chunk_index': 0,
                        'token_count': 30,
                        'text': 'def tensor_loader(x):\n    return x\n',
                        'role': 'seed_change',
                        'retrieval_reason': 'resolved_session_change',
                        'distance_from_seed': 0,
                        'retrieval_score': 1.0,
                    },
                    {
                        'chunk_id': 'local_test_1',
                        'source_type': 'local_repo',
                        'source_id': 'local_repo',
                        'path': 'tests/test_loader.py',
                        'chunk_index': 0,
                        'token_count': 20,
                        'text': 'def test_loader():\n    assert tensor_loader(1) == 1\n',
                        'role': 'verification_constraint',
                        'retrieval_reason': 'targeted_test_selection',
                        'distance_from_seed': 1,
                        'retrieval_score': 1.5,
                    }
                ],
                'context_role_counts': {'seed_change': 1, 'verification_constraint': 1},
                'source_metadata': {'route': 'PATCH_PLUS_EXEC'},
            }
        ) + '\n',
        encoding='utf-8',
    )

    rows, summary = augment_session_episode_context(
        episodes_path=episodes,
        index_dir=index_dir,
        external_token_budget=200,
        max_query_terms=16,
        max_term_docfreq=100,
        max_augmented_chunks=8,
        max_chunks_per_source_type=4,
        max_chunks_per_path=2,
        neighbor_window=1,
        max_neighbor_chunks_per_anchor=2,
        min_external_chunks=3,
    )

    assert summary['augmented_episode_count'] == 1
    row = rows[0]
    assert row['context_token_count'] > 50
    roles = {context_row['role'] for context_row in row['context_rows']}
    assert 'cross_repo_analogue' in roles
    assert 'algorithm_grounding' in roles
    assert 'trace_analogue' in roles
    assert row['augmentation_metadata']['augmented_chunk_count'] >= 3
    external_chunk_ids = {context_row['chunk_id'] for context_row in row['context_rows'] if context_row['source_type'] != 'local_repo'}
    assert {'repo_chunk_1', 'paper_chunk_1', 'dataset_chunk_1'}.issubset(external_chunk_ids)


def test_augment_session_episode_context_filters_low_score_tail_chunks(tmp_path: Path) -> None:
    if importlib.util.find_spec('pyarrow') is None:
        pytest.skip('pyarrow not installed')

    index_dir = tmp_path / 'index'
    chunks_dir = index_dir / 'chunks'
    mentions_dir = index_dir / 'chunk_mentions'
    chunks_dir.mkdir(parents=True)
    mentions_dir.mkdir(parents=True)

    chunks = [
        {
            'chunk_id': 'repo_strong',
            'source_type': 'repo',
            'source_id': 'other_repo',
            'doc_id': 'other_repo/src/loader.py',
            'chunk_index': 0,
            'modality': 'code',
            'token_count': 40,
            'text': 'def tensor_loader(shape_error, verification, runtime, transition):\n    return shape_error\n',
            'metadata_json': json.dumps({'path': 'other_repo/src/loader.py'}),
        },
        {
            'chunk_id': 'repo_weak',
            'source_type': 'repo',
            'source_id': 'weak_repo',
            'doc_id': 'weak_repo/src/loader.py',
            'chunk_index': 0,
            'modality': 'code',
            'token_count': 20,
            'text': 'def loader(x):\n    return x\n',
            'metadata_json': json.dumps({'path': 'weak_repo/src/loader.py'}),
        },
        {
            'chunk_id': 'paper_strong',
            'source_type': 'paper',
            'source_id': 'paper_a',
            'doc_id': 'paper_a/algorithm.txt',
            'chunk_index': 0,
            'modality': 'text',
            'token_count': 35,
            'text': 'Tensor loader algorithm verification transition execution debugging semantics.',
            'metadata_json': json.dumps({'path': 'paper_a/algorithm.txt'}),
        },
        {
            'chunk_id': 'dataset_strong',
            'source_type': 'dataset',
            'source_id': 'trace_a',
            'doc_id': 'trace_a/error_trace.txt',
            'chunk_index': 0,
            'modality': 'text',
            'token_count': 25,
            'text': 'Runtime error trace for tensor loader verification failure and exception.',
            'metadata_json': json.dumps({'path': 'trace_a/error_trace.txt'}),
        },
    ]
    mentions = [
        {'term': 'tensor', 'chunk_id': 'repo_strong', 'source_type': 'repo', 'source_id': 'other_repo', 'doc_id': 'other_repo/src/loader.py'},
        {'term': 'loader', 'chunk_id': 'repo_strong', 'source_type': 'repo', 'source_id': 'other_repo', 'doc_id': 'other_repo/src/loader.py'},
        {'term': 'shape_error', 'chunk_id': 'repo_strong', 'source_type': 'repo', 'source_id': 'other_repo', 'doc_id': 'other_repo/src/loader.py'},
        {'term': 'verification', 'chunk_id': 'repo_strong', 'source_type': 'repo', 'source_id': 'other_repo', 'doc_id': 'other_repo/src/loader.py'},
        {'term': 'runtime', 'chunk_id': 'repo_strong', 'source_type': 'repo', 'source_id': 'other_repo', 'doc_id': 'other_repo/src/loader.py'},
        {'term': 'transition', 'chunk_id': 'repo_strong', 'source_type': 'repo', 'source_id': 'other_repo', 'doc_id': 'other_repo/src/loader.py'},
        {'term': 'loader', 'chunk_id': 'repo_weak', 'source_type': 'repo', 'source_id': 'weak_repo', 'doc_id': 'weak_repo/src/loader.py'},
        {'term': 'tensor', 'chunk_id': 'paper_strong', 'source_type': 'paper', 'source_id': 'paper_a', 'doc_id': 'paper_a/algorithm.txt'},
        {'term': 'loader', 'chunk_id': 'paper_strong', 'source_type': 'paper', 'source_id': 'paper_a', 'doc_id': 'paper_a/algorithm.txt'},
        {'term': 'verification', 'chunk_id': 'paper_strong', 'source_type': 'paper', 'source_id': 'paper_a', 'doc_id': 'paper_a/algorithm.txt'},
        {'term': 'transition', 'chunk_id': 'paper_strong', 'source_type': 'paper', 'source_id': 'paper_a', 'doc_id': 'paper_a/algorithm.txt'},
        {'term': 'trace', 'chunk_id': 'dataset_strong', 'source_type': 'dataset', 'source_id': 'trace_a', 'doc_id': 'trace_a/error_trace.txt'},
        {'term': 'runtime', 'chunk_id': 'dataset_strong', 'source_type': 'dataset', 'source_id': 'trace_a', 'doc_id': 'trace_a/error_trace.txt'},
        {'term': 'loader', 'chunk_id': 'dataset_strong', 'source_type': 'dataset', 'source_id': 'trace_a', 'doc_id': 'trace_a/error_trace.txt'},
        {'term': 'verification', 'chunk_id': 'dataset_strong', 'source_type': 'dataset', 'source_id': 'trace_a', 'doc_id': 'trace_a/error_trace.txt'},
    ]
    write_parquet_shard(shard_path(chunks_dir, 'chunks', 0), chunks)
    write_parquet_shard(shard_path(mentions_dir, 'chunk_mentions', 0), mentions)

    episodes = tmp_path / 'episodes.jsonl'
    episodes.write_text(
        json.dumps(
            {
                'episode_id': 'ep1',
                'repo_id': 'local_repo',
                'goal': 'Modify repository files to preserve behavior under execution-backed maintenance.\nChanged files: src/loader.py\nVerification targets: tests/test_loader.py\nKey symbols: tensor_loader\nExecution route: PATCH_PLUS_EXEC',
                'seed_paths': ['src/loader.py'],
                'seed_symbols': ['tensor_loader', 'shape_error', 'verification', 'runtime', 'transition'],
                'selected_tests': ['tests/test_loader.py'],
                'context_token_count': 30,
                'context_rows': [
                    {
                        'chunk_id': 'local_seed_1',
                        'source_type': 'local_repo',
                        'source_id': 'local_repo',
                        'path': 'src/loader.py',
                        'chunk_index': 0,
                        'token_count': 30,
                        'text': 'def tensor_loader(x):\n    return x\n',
                        'role': 'seed_change',
                        'retrieval_reason': 'resolved_session_change',
                        'distance_from_seed': 0,
                        'retrieval_score': 1.0,
                    },
                    {
                        'chunk_id': 'local_test_1',
                        'source_type': 'local_repo',
                        'source_id': 'local_repo',
                        'path': 'tests/test_loader.py',
                        'chunk_index': 0,
                        'token_count': 20,
                        'text': 'def test_loader():\n    assert tensor_loader(1) == 1\n',
                        'role': 'verification_constraint',
                        'retrieval_reason': 'targeted_test_selection',
                        'distance_from_seed': 1,
                        'retrieval_score': 1.5,
                    }
                ],
                'context_role_counts': {'seed_change': 1, 'verification_constraint': 1},
                'source_metadata': {'route': 'PATCH_PLUS_EXEC'},
            }
        ) + '\n',
        encoding='utf-8',
    )

    rows, _ = augment_session_episode_context(
        episodes_path=episodes,
        index_dir=index_dir,
        external_token_budget=200,
        max_query_terms=16,
        max_term_docfreq=100,
        max_augmented_chunks=8,
        max_chunks_per_source_type=4,
        max_chunks_per_path=2,
        neighbor_window=1,
        max_neighbor_chunks_per_anchor=1,
        min_external_chunks=3,
    )

    row = rows[0]
    chunk_ids = {context_row['chunk_id'] for context_row in row['context_rows']}
    assert 'repo_strong' in chunk_ids
    assert 'paper_strong' in chunk_ids
    assert 'dataset_strong' in chunk_ids
    assert 'repo_weak' not in chunk_ids


def test_augment_session_episode_context_rejects_generic_trace_only_overlap(tmp_path: Path) -> None:
    if importlib.util.find_spec('pyarrow') is None:
        pytest.skip('pyarrow not installed')

    index_dir = tmp_path / 'index'
    chunks_dir = index_dir / 'chunks'
    mentions_dir = index_dir / 'chunk_mentions'
    chunks_dir.mkdir(parents=True)
    mentions_dir.mkdir(parents=True)

    chunks = [
        {
            'chunk_id': 'dataset_generic',
            'source_type': 'dataset',
            'source_id': 'trace_a',
            'doc_id': 'trace_a/runtime_error.txt',
            'chunk_index': 0,
            'modality': 'text',
            'token_count': 20,
            'text': 'runtime error trace exception failure stack',
            'metadata_json': json.dumps({'path': 'trace_a/runtime_error.txt'}),
        },
        {
            'chunk_id': 'repo_strong',
            'source_type': 'repo',
            'source_id': 'other_repo',
            'doc_id': 'other_repo/src/loader.py',
            'chunk_index': 0,
            'modality': 'code',
            'token_count': 24,
            'text': 'def tensor_loader(shape_error):\n    return shape_error\n',
            'metadata_json': json.dumps({'path': 'other_repo/src/loader.py'}),
        },
        {
            'chunk_id': 'paper_strong',
            'source_type': 'paper',
            'source_id': 'paper_a',
            'doc_id': 'paper_a/algorithm.txt',
            'chunk_index': 0,
            'modality': 'text',
            'token_count': 24,
            'text': 'Tensor loader algorithm under execution.',
            'metadata_json': json.dumps({'path': 'paper_a/algorithm.txt'}),
        },
    ]
    mentions = [
        {'term': 'runtime', 'chunk_id': 'dataset_generic', 'source_type': 'dataset', 'source_id': 'trace_a', 'doc_id': 'trace_a/runtime_error.txt'},
        {'term': 'error', 'chunk_id': 'dataset_generic', 'source_type': 'dataset', 'source_id': 'trace_a', 'doc_id': 'trace_a/runtime_error.txt'},
        {'term': 'trace', 'chunk_id': 'dataset_generic', 'source_type': 'dataset', 'source_id': 'trace_a', 'doc_id': 'trace_a/runtime_error.txt'},
        {'term': 'tensor', 'chunk_id': 'repo_strong', 'source_type': 'repo', 'source_id': 'other_repo', 'doc_id': 'other_repo/src/loader.py'},
        {'term': 'loader', 'chunk_id': 'repo_strong', 'source_type': 'repo', 'source_id': 'other_repo', 'doc_id': 'other_repo/src/loader.py'},
        {'term': 'shape_error', 'chunk_id': 'repo_strong', 'source_type': 'repo', 'source_id': 'other_repo', 'doc_id': 'other_repo/src/loader.py'},
        {'term': 'tensor', 'chunk_id': 'paper_strong', 'source_type': 'paper', 'source_id': 'paper_a', 'doc_id': 'paper_a/algorithm.txt'},
        {'term': 'loader', 'chunk_id': 'paper_strong', 'source_type': 'paper', 'source_id': 'paper_a', 'doc_id': 'paper_a/algorithm.txt'},
        {'term': 'algorithm', 'chunk_id': 'paper_strong', 'source_type': 'paper', 'source_id': 'paper_a', 'doc_id': 'paper_a/algorithm.txt'},
    ]
    write_parquet_shard(shard_path(chunks_dir, 'chunks', 0), chunks)
    write_parquet_shard(shard_path(mentions_dir, 'chunk_mentions', 0), mentions)

    episodes = tmp_path / 'episodes.jsonl'
    episodes.write_text(
        json.dumps(
            {
                'episode_id': 'ep1',
                'repo_id': 'local_repo',
                'goal': 'Modify repository files to preserve behavior under execution-backed maintenance.\nChanged files: src/loader.py\nVerification targets: tests/test_loader.py\nKey symbols: tensor_loader\nExecution route: PATCH_PLUS_EXEC',
                'seed_paths': ['src/loader.py'],
                'seed_symbols': ['tensor_loader', 'shape_error'],
                'selected_tests': ['tests/test_loader.py'],
                'context_token_count': 30,
                'context_rows': [
                    {'chunk_id': 'local_seed_1', 'source_type': 'local_repo', 'source_id': 'local_repo', 'path': 'src/loader.py', 'chunk_index': 0, 'token_count': 30, 'text': 'def tensor_loader(x): return x', 'role': 'seed_change', 'retrieval_reason': 'resolved_session_change', 'distance_from_seed': 0, 'retrieval_score': 1.0},
                    {'chunk_id': 'local_test_1', 'source_type': 'local_repo', 'source_id': 'local_repo', 'path': 'tests/test_loader.py', 'chunk_index': 0, 'token_count': 20, 'text': 'assert tensor_loader(1) == 1', 'role': 'verification_constraint', 'retrieval_reason': 'targeted_test_selection', 'distance_from_seed': 1, 'retrieval_score': 1.5},
                ],
                'context_role_counts': {'seed_change': 1, 'verification_constraint': 1},
                'source_metadata': {'route': 'PATCH_PLUS_EXEC'},
            }
        ) + '\n',
        encoding='utf-8',
    )

    rows, _ = augment_session_episode_context(
        episodes_path=episodes,
        index_dir=index_dir,
        external_token_budget=120,
        max_query_terms=16,
        max_term_docfreq=100,
        max_augmented_chunks=6,
        max_chunks_per_source_type=4,
        max_chunks_per_path=2,
        neighbor_window=1,
        max_neighbor_chunks_per_anchor=1,
        min_external_chunks=2,
    )

    chunk_ids = {context_row['chunk_id'] for context_row in rows[0]['context_rows']}
    assert 'repo_strong' in chunk_ids
    assert 'paper_strong' in chunk_ids
    assert 'dataset_generic' not in chunk_ids


def test_augment_session_episode_context_rejects_generated_paper_and_dataset_readme_noise(tmp_path: Path) -> None:
    if importlib.util.find_spec('pyarrow') is None:
        pytest.skip('pyarrow not installed')

    index_dir = tmp_path / 'index'
    chunks_dir = index_dir / 'chunks'
    mentions_dir = index_dir / 'chunk_mentions'
    chunks_dir.mkdir(parents=True)
    mentions_dir.mkdir(parents=True)

    chunks = [
        {
            'chunk_id': 'paper_noise',
            'source_type': 'paper',
            'source_id': 'noise_paper',
            'doc_id': 'noise/structured/repo_skills_miner.skills.jsonl',
            'chunk_index': 0,
            'modality': 'text',
            'token_count': 24,
            'text': 'tensor loader model output return size',
            'metadata_json': json.dumps({'path': 'noise/structured/repo_skills_miner.skills.jsonl'}),
        },
        {
            'chunk_id': 'dataset_noise',
            'source_type': 'dataset',
            'source_id': 'noise_dataset',
            'doc_id': 'noise/README.md',
            'chunk_index': 0,
            'modality': 'text',
            'token_count': 24,
            'text': 'runtime error trace tensor loader',
            'metadata_json': json.dumps({'path': 'noise/README.md'}),
        },
        {
            'chunk_id': 'repo_strong',
            'source_type': 'repo',
            'source_id': 'other_repo',
            'doc_id': 'other_repo/src/loader.py',
            'chunk_index': 0,
            'modality': 'code',
            'token_count': 24,
            'text': 'def tensor_loader(shape_error):\n    return shape_error\n',
            'metadata_json': json.dumps({'path': 'other_repo/src/loader.py'}),
        },
        {
            'chunk_id': 'paper_strong',
            'source_type': 'paper',
            'source_id': 'paper_a',
            'doc_id': 'paper_a/algorithm.txt',
            'chunk_index': 0,
            'modality': 'text',
            'token_count': 24,
            'text': 'Tensor loader algorithm under execution.',
            'metadata_json': json.dumps({'path': 'paper_a/algorithm.txt'}),
        },
    ]
    mentions = [
        {'term': 'tensor', 'chunk_id': 'paper_noise', 'source_type': 'paper', 'source_id': 'noise_paper', 'doc_id': 'noise/structured/repo_skills_miner.skills.jsonl'},
        {'term': 'loader', 'chunk_id': 'paper_noise', 'source_type': 'paper', 'source_id': 'noise_paper', 'doc_id': 'noise/structured/repo_skills_miner.skills.jsonl'},
        {'term': 'runtime', 'chunk_id': 'dataset_noise', 'source_type': 'dataset', 'source_id': 'noise_dataset', 'doc_id': 'noise/README.md'},
        {'term': 'trace', 'chunk_id': 'dataset_noise', 'source_type': 'dataset', 'source_id': 'noise_dataset', 'doc_id': 'noise/README.md'},
        {'term': 'tensor', 'chunk_id': 'repo_strong', 'source_type': 'repo', 'source_id': 'other_repo', 'doc_id': 'other_repo/src/loader.py'},
        {'term': 'loader', 'chunk_id': 'repo_strong', 'source_type': 'repo', 'source_id': 'other_repo', 'doc_id': 'other_repo/src/loader.py'},
        {'term': 'shape_error', 'chunk_id': 'repo_strong', 'source_type': 'repo', 'source_id': 'other_repo', 'doc_id': 'other_repo/src/loader.py'},
        {'term': 'tensor', 'chunk_id': 'paper_strong', 'source_type': 'paper', 'source_id': 'paper_a', 'doc_id': 'paper_a/algorithm.txt'},
        {'term': 'loader', 'chunk_id': 'paper_strong', 'source_type': 'paper', 'source_id': 'paper_a', 'doc_id': 'paper_a/algorithm.txt'},
        {'term': 'algorithm', 'chunk_id': 'paper_strong', 'source_type': 'paper', 'source_id': 'paper_a', 'doc_id': 'paper_a/algorithm.txt'},
    ]
    write_parquet_shard(shard_path(chunks_dir, 'chunks', 0), chunks)
    write_parquet_shard(shard_path(mentions_dir, 'chunk_mentions', 0), mentions)

    episodes = tmp_path / 'episodes.jsonl'
    episodes.write_text(
        json.dumps(
            {
                'episode_id': 'ep1',
                'repo_id': 'local_repo',
                'goal': 'Modify repository files to preserve behavior under execution-backed maintenance.\nChanged files: src/loader.py\nVerification targets: tests/test_loader.py\nKey symbols: tensor_loader\nExecution route: PATCH_PLUS_EXEC',
                'seed_paths': ['src/loader.py'],
                'seed_symbols': ['tensor_loader', 'shape_error'],
                'selected_tests': ['tests/test_loader.py'],
                'context_token_count': 30,
                'context_rows': [
                    {'chunk_id': 'local_seed_1', 'source_type': 'local_repo', 'source_id': 'local_repo', 'path': 'src/loader.py', 'chunk_index': 0, 'token_count': 30, 'text': 'def tensor_loader(x): return x', 'role': 'seed_change', 'retrieval_reason': 'resolved_session_change', 'distance_from_seed': 0, 'retrieval_score': 1.0},
                    {'chunk_id': 'local_test_1', 'source_type': 'local_repo', 'source_id': 'local_repo', 'path': 'tests/test_loader.py', 'chunk_index': 0, 'token_count': 20, 'text': 'assert tensor_loader(1) == 1', 'role': 'verification_constraint', 'retrieval_reason': 'targeted_test_selection', 'distance_from_seed': 1, 'retrieval_score': 1.5},
                ],
                'context_role_counts': {'seed_change': 1, 'verification_constraint': 1},
                'source_metadata': {'route': 'PATCH_PLUS_EXEC'},
            }
        ) + '\n',
        encoding='utf-8',
    )

    rows, _ = augment_session_episode_context(
        episodes_path=episodes,
        index_dir=index_dir,
        external_token_budget=120,
        max_query_terms=16,
        max_term_docfreq=100,
        max_augmented_chunks=6,
        max_chunks_per_source_type=4,
        max_chunks_per_path=2,
        neighbor_window=1,
        max_neighbor_chunks_per_anchor=1,
        min_external_chunks=2,
    )

    chunk_ids = {context_row['chunk_id'] for context_row in rows[0]['context_rows']}
    assert 'repo_strong' in chunk_ids
    assert 'paper_strong' in chunk_ids
    assert 'paper_noise' not in chunk_ids
    assert 'dataset_noise' not in chunk_ids


def test_augment_session_episode_context_filters_generic_symbol_query_terms(tmp_path: Path) -> None:
    if importlib.util.find_spec('pyarrow') is None:
        pytest.skip('pyarrow not installed')

    index_dir = tmp_path / 'index'
    chunks_dir = index_dir / 'chunks'
    mentions_dir = index_dir / 'chunk_mentions'
    chunks_dir.mkdir(parents=True)
    mentions_dir.mkdir(parents=True)

    chunks = [
        {
            'chunk_id': 'repo_anchor', 'source_type': 'repo', 'source_id': 'other_repo', 'doc_id': 'other_repo/src/training_loop.py',
            'chunk_index': 0, 'modality': 'code', 'token_count': 40,
            'text': 'def probe_contract_error_guard(loss_keys):\n    return loss_keys\n',
            'metadata_json': json.dumps({'path': 'other_repo/src/training_loop.py'}),
        },
        {
            'chunk_id': 'repo_generic', 'source_type': 'repo', 'source_id': 'broad_repo', 'doc_id': 'broad_repo/src/train.py',
            'chunk_index': 0, 'modality': 'code', 'token_count': 40,
            'text': 'def train(any_value):\n    return str(int(bool(any_value)))\n',
            'metadata_json': json.dumps({'path': 'broad_repo/src/train.py'}),
        },
        {
            'chunk_id': 'paper_anchor', 'source_type': 'paper', 'source_id': 'paper_a', 'doc_id': 'paper_a/probe_contract.txt',
            'chunk_index': 0, 'modality': 'text', 'token_count': 30,
            'text': 'probe contract error guard explains loss key routing for bounded decoder packages',
            'metadata_json': json.dumps({'path': 'paper_a/probe_contract.txt'}),
        },
        {
            'chunk_id': 'dataset_anchor', 'source_type': 'dataset', 'source_id': 'trace_a', 'doc_id': 'trace_a/probe_contract_trace.txt',
            'chunk_index': 0, 'modality': 'text', 'token_count': 20,
            'text': 'probe contract error trace for bounded decoder package route mismatch',
            'metadata_json': json.dumps({'path': 'trace_a/probe_contract_trace.txt'}),
        },
    ]
    mentions = [
        {'term': 'probecontracterror', 'chunk_id': 'repo_anchor', 'source_type': 'repo', 'source_id': 'other_repo', 'doc_id': 'other_repo/src/training_loop.py'},
        {'term': 'loss_keys', 'chunk_id': 'repo_anchor', 'source_type': 'repo', 'source_id': 'other_repo', 'doc_id': 'other_repo/src/training_loop.py'},
        {'term': 'training_loop', 'chunk_id': 'repo_anchor', 'source_type': 'repo', 'source_id': 'other_repo', 'doc_id': 'other_repo/src/training_loop.py'},
        {'term': 'train', 'chunk_id': 'repo_generic', 'source_type': 'repo', 'source_id': 'broad_repo', 'doc_id': 'broad_repo/src/train.py'},
        {'term': 'any', 'chunk_id': 'repo_generic', 'source_type': 'repo', 'source_id': 'broad_repo', 'doc_id': 'broad_repo/src/train.py'},
        {'term': 'str', 'chunk_id': 'repo_generic', 'source_type': 'repo', 'source_id': 'broad_repo', 'doc_id': 'broad_repo/src/train.py'},
        {'term': 'int', 'chunk_id': 'repo_generic', 'source_type': 'repo', 'source_id': 'broad_repo', 'doc_id': 'broad_repo/src/train.py'},
        {'term': 'probecontracterror', 'chunk_id': 'paper_anchor', 'source_type': 'paper', 'source_id': 'paper_a', 'doc_id': 'paper_a/probe_contract.txt'},
        {'term': 'loss_keys', 'chunk_id': 'paper_anchor', 'source_type': 'paper', 'source_id': 'paper_a', 'doc_id': 'paper_a/probe_contract.txt'},
        {'term': 'trace', 'chunk_id': 'dataset_anchor', 'source_type': 'dataset', 'source_id': 'trace_a', 'doc_id': 'trace_a/probe_contract_trace.txt'},
        {'term': 'probecontracterror', 'chunk_id': 'dataset_anchor', 'source_type': 'dataset', 'source_id': 'trace_a', 'doc_id': 'trace_a/probe_contract_trace.txt'},
    ]
    write_parquet_shard(shard_path(chunks_dir, 'chunks', 0), chunks)
    write_parquet_shard(shard_path(mentions_dir, 'chunk_mentions', 0), mentions)

    episodes = tmp_path / 'episodes.jsonl'
    episodes.write_text(
        json.dumps(
            {
                'episode_id': 'ep1',
                'repo_id': 'local_repo',
                'goal': 'Modify repository files to preserve behavior under execution-backed maintenance.\nChanged files: legacy_src/training_loop.py\nVerification targets: tests/test_probe_contract.py\nKey symbols: ProbeContractError, LOSS_KEYS, Any, get, str, int, train\nExecution route: PATCH_PLUS_EXEC',
                'seed_paths': ['legacy_src/training_loop.py'],
                'seed_symbols': ['ProbeContractError', 'LOSS_KEYS', 'Any', 'get', 'str', 'int', 'train'],
                'selected_tests': ['tests/test_probe_contract.py'],
                'context_token_count': 40,
                'context_rows': [
                    {
                        'chunk_id': 'local_seed_1', 'source_type': 'local_repo', 'source_id': 'local_repo', 'path': 'legacy_src/training_loop.py',
                        'chunk_index': 0, 'token_count': 20, 'text': 'class ProbeContractError(Exception):\n    pass\nLOSS_KEYS = []\n',
                        'role': 'seed_change', 'retrieval_reason': 'resolved_session_change', 'distance_from_seed': 0, 'retrieval_score': 1.0,
                    },
                    {
                        'chunk_id': 'local_test_1', 'source_type': 'local_repo', 'source_id': 'local_repo', 'path': 'tests/test_probe_contract.py',
                        'chunk_index': 0, 'token_count': 20, 'text': 'def test_probe_contract():\n    assert LOSS_KEYS == []\n',
                        'role': 'verification_constraint', 'retrieval_reason': 'targeted_test_selection', 'distance_from_seed': 1, 'retrieval_score': 1.0,
                    },
                ],
                'context_role_counts': {'seed_change': 1, 'verification_constraint': 1},
                'source_metadata': {'route': 'PATCH_PLUS_EXEC'},
            }
        ) + '\n',
        encoding='utf-8',
    )

    rows, _ = augment_session_episode_context(
        episodes_path=episodes,
        index_dir=index_dir,
        external_token_budget=200,
        max_query_terms=12,
        max_term_docfreq=100,
        max_augmented_chunks=6,
        max_chunks_per_source_type=3,
        max_chunks_per_path=2,
        neighbor_window=1,
        max_neighbor_chunks_per_anchor=1,
        min_external_chunks=3,
    )

    row = rows[0]
    query_terms = row['augmentation_metadata']['query_terms']
    assert 'any' not in query_terms
    assert 'get' not in query_terms
    assert 'str' not in query_terms
    assert 'int' not in query_terms
    assert 'train' not in query_terms
    external_ids = {context_row['chunk_id'] for context_row in row['context_rows'] if context_row['source_type'] != 'local_repo'}
    assert 'repo_anchor' in external_ids
    assert 'paper_anchor' in external_ids
    assert 'dataset_anchor' in external_ids
    assert 'repo_generic' not in external_ids


def test_augment_session_episode_context_source_catalog_blocks_uncurated_external_datasets(tmp_path: Path) -> None:
    if importlib.util.find_spec('pyarrow') is None:
        pytest.skip('pyarrow not installed')

    index_dir = tmp_path / 'index'
    chunks_dir = index_dir / 'chunks'
    mentions_dir = index_dir / 'chunk_mentions'
    chunks_dir.mkdir(parents=True)
    mentions_dir.mkdir(parents=True)

    chunks = [
        {
            'chunk_id': 'repo_chunk_1',
            'source_type': 'repo',
            'source_id': 'other_repo',
            'doc_id': 'other_repo/src/loader.py',
            'chunk_index': 0,
            'modality': 'code',
            'token_count': 40,
            'text': 'def tensor_loader(shape_error):\n    return shape_error\n',
            'metadata_json': json.dumps({'path': 'other_repo/src/loader.py'}),
        },
        {
            'chunk_id': 'paper_chunk_1',
            'source_type': 'paper',
            'source_id': 'paper_a',
            'doc_id': 'paper_a/algorithm.txt',
            'chunk_index': 0,
            'modality': 'text',
            'token_count': 35,
            'text': 'Tensor loader algorithm and verification procedure under execution.',
            'metadata_json': json.dumps({'path': 'paper_a/algorithm.txt'}),
        },
        {
            'chunk_id': 'dataset_chunk_1',
            'source_type': 'dataset',
            'source_id': 'trace_a',
            'doc_id': 'trace_a/error_trace.txt',
            'chunk_index': 0,
            'modality': 'text',
            'token_count': 25,
            'text': 'Runtime error trace for loader shape mismatch in tensor pipeline.',
            'metadata_json': json.dumps({'path': 'trace_a/error_trace.txt'}),
        },
        {
            'chunk_id': 'dataset_chunk_rogue',
            'source_type': 'dataset',
            'source_id': 'rogue_ds',
            'doc_id': 'rogue_ds/error_trace.txt',
            'chunk_index': 0,
            'modality': 'text',
            'token_count': 26,
            'text': 'Runtime error trace for loader shape mismatch in tensor pipeline.',
            'metadata_json': json.dumps({'path': 'rogue_ds/error_trace.txt'}),
        },
    ]
    mentions = [
        {'term': 'tensor', 'chunk_id': 'repo_chunk_1', 'source_type': 'repo', 'source_id': 'other_repo', 'doc_id': 'other_repo/src/loader.py'},
        {'term': 'loader', 'chunk_id': 'repo_chunk_1', 'source_type': 'repo', 'source_id': 'other_repo', 'doc_id': 'other_repo/src/loader.py'},
        {'term': 'shape_error', 'chunk_id': 'repo_chunk_1', 'source_type': 'repo', 'source_id': 'other_repo', 'doc_id': 'other_repo/src/loader.py'},
        {'term': 'tensor', 'chunk_id': 'paper_chunk_1', 'source_type': 'paper', 'source_id': 'paper_a', 'doc_id': 'paper_a/algorithm.txt'},
        {'term': 'loader', 'chunk_id': 'paper_chunk_1', 'source_type': 'paper', 'source_id': 'paper_a', 'doc_id': 'paper_a/algorithm.txt'},
        {'term': 'verification', 'chunk_id': 'paper_chunk_1', 'source_type': 'paper', 'source_id': 'paper_a', 'doc_id': 'paper_a/algorithm.txt'},
        {'term': 'loader', 'chunk_id': 'dataset_chunk_1', 'source_type': 'dataset', 'source_id': 'trace_a', 'doc_id': 'trace_a/error_trace.txt'},
        {'term': 'trace', 'chunk_id': 'dataset_chunk_1', 'source_type': 'dataset', 'source_id': 'trace_a', 'doc_id': 'trace_a/error_trace.txt'},
        {'term': 'tensor', 'chunk_id': 'dataset_chunk_1', 'source_type': 'dataset', 'source_id': 'trace_a', 'doc_id': 'trace_a/error_trace.txt'},
        {'term': 'loader', 'chunk_id': 'dataset_chunk_rogue', 'source_type': 'dataset', 'source_id': 'rogue_ds', 'doc_id': 'rogue_ds/error_trace.txt'},
        {'term': 'trace', 'chunk_id': 'dataset_chunk_rogue', 'source_type': 'dataset', 'source_id': 'rogue_ds', 'doc_id': 'rogue_ds/error_trace.txt'},
        {'term': 'tensor', 'chunk_id': 'dataset_chunk_rogue', 'source_type': 'dataset', 'source_id': 'rogue_ds', 'doc_id': 'rogue_ds/error_trace.txt'},
    ]
    write_parquet_shard(shard_path(chunks_dir, 'chunks', 0), chunks)
    write_parquet_shard(shard_path(mentions_dir, 'chunk_mentions', 0), mentions)

    episodes = tmp_path / 'episodes.jsonl'
    episodes.write_text(
        json.dumps(
            {
                'episode_id': 'ep1',
                'repo_id': 'local_repo',
                'goal': 'Modify repository files to preserve behavior under execution-backed maintenance.\nChanged files: src/loader.py\nVerification targets: tests/test_loader.py\nKey symbols: tensor_loader\nExecution route: PATCH_PLUS_EXEC',
                'seed_paths': ['src/loader.py'],
                'seed_symbols': ['tensor_loader', 'shape_error'],
                'selected_tests': ['tests/test_loader.py'],
                'context_token_count': 30,
                'context_rows': [
                    {
                        'chunk_id': 'local_seed_1',
                        'source_type': 'local_repo',
                        'source_id': 'local_repo',
                        'path': 'src/loader.py',
                        'chunk_index': 0,
                        'token_count': 30,
                        'text': 'def tensor_loader(x):\n    return x\n',
                        'role': 'seed_change',
                        'retrieval_reason': 'resolved_session_change',
                        'distance_from_seed': 0,
                        'retrieval_score': 1.0,
                    },
                    {
                        'chunk_id': 'local_test_1',
                        'source_type': 'local_repo',
                        'source_id': 'local_repo',
                        'path': 'tests/test_loader.py',
                        'chunk_index': 0,
                        'token_count': 20,
                        'text': 'def test_loader():\n    assert tensor_loader(1) == 1\n',
                        'role': 'verification_constraint',
                        'retrieval_reason': 'targeted_test_selection',
                        'distance_from_seed': 1,
                        'retrieval_score': 1.5,
                    }
                ],
                'context_role_counts': {'seed_change': 1, 'verification_constraint': 1},
                'source_metadata': {'route': 'PATCH_PLUS_EXEC'},
            }
        ) + '\n',
        encoding='utf-8',
    )

    source_catalog = tmp_path / 'source_catalog.json'
    source_catalog.write_text(
        json.dumps(
            {
                'source_type_defaults': {
                    'repo': {'allow_uncataloged': True},
                    'paper': {'allow_uncataloged': False},
                    'dataset': {'allow_uncataloged': False},
                },
                'sources': [
                    {
                        'name': 'paper_support',
                        'source_type': 'paper',
                        'source_id_equals': ['paper_a'],
                        'allow_augmentation': True,
                        'role_override': 'algorithm_grounding',
                        'provenance_tier': 'grounded_paper',
                        'quality_tier': 'high',
                    },
                    {
                        'name': 'trace_support',
                        'source_type': 'dataset',
                        'source_id_equals': ['trace_a'],
                        'allow_augmentation': True,
                        'role_override': 'trace_analogue',
                        'provenance_tier': 'grounded_trace',
                        'quality_tier': 'high',
                    },
                ],
            },
            sort_keys=True,
        ),
        encoding='utf-8',
    )

    rows, summary = augment_session_episode_context(
        episodes_path=episodes,
        index_dir=index_dir,
        external_token_budget=200,
        max_query_terms=16,
        max_term_docfreq=100,
        max_augmented_chunks=8,
        max_chunks_per_source_type=4,
        max_chunks_per_path=2,
        neighbor_window=1,
        max_neighbor_chunks_per_anchor=2,
        min_external_chunks=3,
        source_catalog_path=source_catalog,
    )

    row = rows[0]
    external_rows = [context_row for context_row in row['context_rows'] if context_row['source_type'] != 'local_repo']
    external_ids = {context_row['chunk_id'] for context_row in external_rows}
    assert 'dataset_chunk_rogue' not in external_ids
    assert {'repo_chunk_1', 'paper_chunk_1', 'dataset_chunk_1'}.issubset(external_ids)
    paper_row = next(context_row for context_row in external_rows if context_row['chunk_id'] == 'paper_chunk_1')
    dataset_row = next(context_row for context_row in external_rows if context_row['chunk_id'] == 'dataset_chunk_1')
    assert paper_row['source_catalog']['name'] == 'paper_support'
    assert dataset_row['source_catalog']['name'] == 'trace_support'
    assert summary['catalog_source_counts'] == {'paper_support': 1, 'trace_support': 1}
