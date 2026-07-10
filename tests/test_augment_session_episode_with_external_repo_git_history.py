from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from augment_session_episode_with_external_repo_git_history import augment_session_episode_with_external_repo_git_history  # noqa: E402
from long_context_parquet import shard_path, write_parquet_shard  # noqa: E402


def _git(repo: Path, *args: str) -> None:
    subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True, text=True)


def test_augment_session_episode_with_external_repo_git_history_adds_rows(tmp_path: Path) -> None:
    if importlib.util.find_spec('pyarrow') is None:
        pytest.skip('pyarrow not installed')

    ext_root = tmp_path / 'external_repos'
    repo = ext_root / 'repo_alpha'
    repo.mkdir(parents=True)
    _git(repo, 'init')
    _git(repo, 'config', 'user.email', 'test@example.com')
    _git(repo, 'config', 'user.name', 'Test User')
    src = repo / 'src'
    src.mkdir()
    target = src / 'loader.py'
    target.write_text('def tensor_loader(x):\n    return x\n', encoding='utf-8')
    _git(repo, 'add', 'src/loader.py')
    _git(repo, 'commit', '-m', 'add tensor loader')
    target.write_text('def tensor_loader(x):\n    return x + 1\n', encoding='utf-8')
    _git(repo, 'add', 'src/loader.py')
    _git(repo, 'commit', '-m', 'fix tensor loader shape')

    index_dir = tmp_path / 'index'
    chunks_dir = index_dir / 'chunks'
    mentions_dir = index_dir / 'chunk_mentions'
    chunks_dir.mkdir(parents=True)
    mentions_dir.mkdir(parents=True)
    chunks = [
        {
            'chunk_id': 'repo_chunk_1',
            'source_type': 'repo',
            'source_id': 'repo_alpha',
            'doc_id': 'repo_alpha/src/loader.py',
            'chunk_index': 0,
            'modality': 'code',
            'token_count': 20,
            'text': 'def tensor_loader(shape_error):\n    return shape_error\n',
            'metadata_json': json.dumps({'path': 'src/loader.py'}),
        },
    ]
    mentions = [
        {'term': 'tensor_loader', 'chunk_id': 'repo_chunk_1', 'source_type': 'repo', 'source_id': 'repo_alpha', 'doc_id': 'repo_alpha/src/loader.py'},
        {'term': 'shape_error', 'chunk_id': 'repo_chunk_1', 'source_type': 'repo', 'source_id': 'repo_alpha', 'doc_id': 'repo_alpha/src/loader.py'},
        {'term': 'loader', 'chunk_id': 'repo_chunk_1', 'source_type': 'repo', 'source_id': 'repo_alpha', 'doc_id': 'repo_alpha/src/loader.py'},
    ]
    write_parquet_shard(shard_path(chunks_dir, 'chunks', 0), chunks)
    write_parquet_shard(shard_path(mentions_dir, 'chunk_mentions', 0), mentions)

    episodes = tmp_path / 'episodes.jsonl'
    episodes.write_text(
        json.dumps(
            {
                'episode_id': 'ep1',
                'repo_id': 'local_repo',
                'goal': 'repair tensor loader shape bug',
                'seed_paths': ['src/loader.py'],
                'seed_symbols': ['tensor_loader', 'shape_error'],
                'selected_tests': ['tests/test_loader.py'],
                'context_token_count': 10,
                'context_rows': [
                    {
                        'chunk_id': 'seed1',
                        'source_type': 'local_repo',
                        'source_id': 'local_repo',
                        'path': 'src/loader.py',
                        'chunk_index': 0,
                        'token_count': 10,
                        'text': 'def tensor_loader(x): return x',
                        'role': 'seed_change',
                        'retrieval_reason': 'seed',
                        'distance_from_seed': 0,
                        'retrieval_score': 1.0,
                    }
                ],
                'context_role_counts': {'seed_change': 1},
            }
        ) + '\n',
        encoding='utf-8',
    )

    rows, summary = augment_session_episode_with_external_repo_git_history(
        episodes_path=episodes,
        index_dir=index_dir,
        external_repo_root=ext_root,
        max_external_repos=4,
        max_paths_per_repo=2,
        max_commits_per_path=4,
    )
    assert summary['augmented_episode_count'] == 1
    row = rows[0]
    assert row['context_token_count'] > 10
    roles = {context_row['role'] for context_row in row['context_rows']}
    assert 'external_commit_analogue' in roles
    assert row['external_git_history_augmentation_metadata']['added_external_commit_rows'] >= 1
