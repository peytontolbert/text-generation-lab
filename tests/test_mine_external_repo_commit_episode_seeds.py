from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from mine_external_repo_commit_episode_seeds import mine_external_repo_commit_episode_seeds  # noqa: E402


def _git(repo: Path, *args: str) -> None:
    subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True, text=True)


def test_mine_external_repo_commit_episode_seeds_emits_commit_rows(tmp_path: Path) -> None:
    repo_root = tmp_path / 'repos'
    repo = repo_root / 'repo_alpha'
    repo.mkdir(parents=True)
    _git(repo, 'init')
    _git(repo, 'config', 'user.email', 'test@example.com')
    _git(repo, 'config', 'user.name', 'Test User')

    src = repo / 'src'
    src.mkdir()
    (src / 'engine.py').write_text('def run_order(x):\n    return x\n', encoding='utf-8')
    _git(repo, 'add', 'src/engine.py')
    _git(repo, 'commit', '-m', 'add engine')

    (src / 'engine.py').write_text('def run_order(x):\n    return x + 1\n', encoding='utf-8')
    _git(repo, 'add', 'src/engine.py')
    _git(repo, 'commit', '-m', 'fix run_order')

    seeds, summary = mine_external_repo_commit_episode_seeds(
        repo_root=repo_root,
        max_repos=4,
        max_commits_per_repo=4,
        max_files_per_commit=4,
    )

    assert summary['seed_count'] >= 2
    row = seeds[0]
    assert row['seed_type'] == 'external_repo_commit'
    assert row['repo_id'] == 'repo_alpha'
    assert row['changes']
    assert row['changes'][0]['path'].startswith('repo_alpha/')
    assert row['target']['expected_outcome'] == 'commit_applied'
    assert row['metadata']['commit_sha']
