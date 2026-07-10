from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from augment_session_episode_with_git_history import augment_session_episode_with_git_history  # noqa: E402


def _git(repo: Path, *args: str) -> None:
    subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True, text=True)


def test_augment_session_episode_with_git_history_adds_commit_rows(tmp_path: Path) -> None:
    repo = tmp_path / 'repo'
    repo.mkdir()
    _git(repo, 'init')
    _git(repo, 'config', 'user.email', 'test@example.com')
    _git(repo, 'config', 'user.name', 'Test User')

    src = repo / 'src'
    src.mkdir()
    path = src / 'engine.py'
    path.write_text('def run_order(x):\n    return x\n', encoding='utf-8')
    _git(repo, 'add', 'src/engine.py')
    _git(repo, 'commit', '-m', 'add engine')

    path.write_text('def run_order(x):\n    return x + 1\n', encoding='utf-8')
    _git(repo, 'add', 'src/engine.py')
    _git(repo, 'commit', '-m', 'fix run_order')

    episodes = tmp_path / 'episodes.jsonl'
    episodes.write_text(
        json.dumps(
            {
                'episode_id': 'ep1',
                'repo_id': 'repo',
                'local_repo_root': str(repo),
                'seed_paths': ['src/engine.py'],
                'context_token_count': 10,
                'context_rows': [
                    {
                        'chunk_id': 'seed1',
                        'source_type': 'local_repo',
                        'source_id': 'repo',
                        'path': 'src/engine.py',
                        'chunk_index': 0,
                        'token_count': 10,
                        'text': 'def run_order(x): return x + 1',
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

    rows, summary = augment_session_episode_with_git_history(episodes_path=episodes, max_commits_per_path=4)
    assert summary['augmented_episode_count'] == 1
    row = rows[0]
    assert row['context_token_count'] > 10
    roles = {context_row['role'] for context_row in row['context_rows']}
    assert 'commit_history_analogue' in roles
    assert row['git_history_augmentation_metadata']['added_commit_history_rows'] >= 1
