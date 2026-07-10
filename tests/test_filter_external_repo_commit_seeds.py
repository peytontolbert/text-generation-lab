from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from filter_external_repo_commit_seeds import filter_external_repo_commit_seeds  # noqa: E402


def test_filter_external_repo_commit_seeds_keeps_code_heavy_rows(tmp_path: Path) -> None:
    seeds = tmp_path / 'seeds.jsonl'
    seeds.write_text(
        ''.join(
            json.dumps(row) + '\n'
            for row in [
                {
                    'seed_id': 'drop1',
                    'goal': 'Update README.md',
                    'changes': [{'path': 'Repo/README.md'}],
                },
                {
                    'seed_id': 'keep1',
                    'goal': 'Fix lazy import in chat API',
                    'changes': [{'path': 'Repo/src/chat_api.py'}, {'path': 'Repo/src/llm_utils.py'}],
                },
            ]
        ),
        encoding='utf-8',
    )
    kept, summary = filter_external_repo_commit_seeds(seeds)
    assert summary['kept_seed_count'] == 1
    assert kept[0]['seed_id'] == 'keep1'
