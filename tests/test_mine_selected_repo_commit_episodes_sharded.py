from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from mine_selected_repo_commit_episodes_sharded import mine_selected_repo_commit_episodes_sharded  # noqa: E402


def test_mine_selected_repo_commit_episodes_sharded_merges_local_repo_rows(tmp_path: Path) -> None:
    repo_root = tmp_path / 'repos'
    repo_a = repo_root / 'repo_a'
    repo_b = repo_root / 'repo_b'
    (repo_a / 'src').mkdir(parents=True)
    (repo_a / 'tests').mkdir(parents=True)
    (repo_b / 'pkg').mkdir(parents=True)
    (repo_b / 'tests').mkdir(parents=True)
    (repo_a / 'src' / 'engine.py').write_text('def run_order(x):\n    return x + 1\n', encoding='utf-8')
    (repo_a / 'tests' / 'test_engine.py').write_text('from src.engine import run_order\n\ndef test_run_order():\n    assert run_order(1) == 2\n', encoding='utf-8')
    (repo_b / 'pkg' / 'reader.py').write_text('def load_data(x):\n    return x\n', encoding='utf-8')
    (repo_b / 'tests' / 'test_reader.py').write_text('from pkg.reader import load_data\n\ndef test_reader():\n    assert load_data(1) == 1\n', encoding='utf-8')

    seeds = tmp_path / 'seeds.jsonl'
    seeds.write_text(
        '\n'.join(
            [
                json.dumps({'seed_id': 's1', 'seed_type': 'external_repo_commit', 'repo_id': 'repo_a', 'goal': 'Fix run_order behavior', 'changes': [{'path': 'repo_a/src/engine.py'}], 'metadata': {'commit_sha': 'a1', 'commit_subject': 'Fix run_order'}}),
                json.dumps({'seed_id': 's2', 'seed_type': 'external_repo_commit', 'repo_id': 'repo_b', 'goal': 'Fix load_data behavior', 'changes': [{'path': 'repo_b/pkg/reader.py'}], 'metadata': {'commit_sha': 'b1', 'commit_subject': 'Fix load_data'}}),
            ]
        ) + '\n',
        encoding='utf-8',
    )

    rows, summary = mine_selected_repo_commit_episodes_sharded(
        seeds_path=seeds,
        repositories_root=repo_root,
        output_dir=tmp_path / 'out',
        shard_size=1,
        include_papers=False,
        root_file_limit=20,
        neighbor_dir_file_limit=20,
        max_total_candidates=50,
    )

    assert summary['source_mode'] == 'repositories_root'
    assert summary['seed_count'] == 2
    assert summary['episode_count'] == 2
    assert summary['shard_count'] == 2
    assert (tmp_path / 'out' / 'shards' / 'episodes_0000_summary.json').exists()
    assert all(row['source_metadata']['source_mode'] == 'repositories_root' for row in rows)
