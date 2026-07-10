from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from rerank_commit_seeds_by_corpus_novelty import rerank_commit_seeds_by_corpus_novelty  # noqa: E402


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')


def test_rerank_commit_seeds_by_corpus_novelty_prefers_unseen_repo(tmp_path: Path) -> None:
    ranked_seeds_path = tmp_path / 'ranked.jsonl'
    existing_examples_path = tmp_path / 'examples.jsonl'
    _write_jsonl(
        existing_examples_path,
        [
            {
                'example_id': 'ex1',
                'repo_id': 'repo_seen',
                'program_id': 'repo_seen',
                'query': {'seed_paths': ['src/known.py']},
            }
        ],
    )
    _write_jsonl(
        ranked_seeds_path,
        [
            {
                'seed_id': 'seed_seen',
                'repo_id': 'repo_seen',
                'changes': [{'path': 'src/known.py'}],
                'rank_metadata': {'discoverability_score': 50.0, 'discoverability_route': 'PASS_TARGETED_TEST_SELECTION'},
            },
            {
                'seed_id': 'seed_unseen',
                'repo_id': 'repo_new',
                'changes': [{'path': 'src/new.py'}],
                'rank_metadata': {'discoverability_score': 40.0, 'discoverability_route': 'PASS_TARGETED_TEST_SELECTION'},
            },
        ],
    )

    rows, summary = rerank_commit_seeds_by_corpus_novelty(
        ranked_seeds_path=ranked_seeds_path,
        existing_examples_path=existing_examples_path,
    )

    assert rows[0]['seed_id'] == 'seed_unseen'
    assert (rows[0]['rank_metadata'] or {})['corpus_novelty']['repo_seen_before'] is False
    assert summary['repo_seen_histogram'] == {'0': 1, '1': 1}


def test_rerank_commit_seeds_by_corpus_novelty_rewards_new_paths_in_seen_repo(tmp_path: Path) -> None:
    ranked_seeds_path = tmp_path / 'ranked.jsonl'
    existing_examples_path = tmp_path / 'examples.jsonl'
    _write_jsonl(
        existing_examples_path,
        [
            {
                'example_id': 'ex1',
                'repo_id': 'repo_seen',
                'program_id': 'repo_seen',
                'query': {'seed_paths': ['pkg/core/model.py', 'tests/test_model.py']},
            }
        ],
    )
    _write_jsonl(
        ranked_seeds_path,
        [
            {
                'seed_id': 'seed_overlap',
                'repo_id': 'repo_seen',
                'changes': [{'path': 'pkg/core/model.py'}],
                'rank_metadata': {'discoverability_score': 60.0, 'discoverability_route': 'PASS_TARGETED_TEST_SELECTION'},
            },
            {
                'seed_id': 'seed_novel_paths',
                'repo_id': 'repo_seen',
                'changes': [{'path': 'pkg/trainer/runtime.py'}, {'path': 'tests/test_runtime.py'}],
                'rank_metadata': {'discoverability_score': 55.0, 'discoverability_route': 'PASS_TARGETED_TEST_SELECTION'},
            },
        ],
    )

    rows, _ = rerank_commit_seeds_by_corpus_novelty(
        ranked_seeds_path=ranked_seeds_path,
        existing_examples_path=existing_examples_path,
    )

    assert rows[0]['seed_id'] == 'seed_novel_paths'
    top_meta = rows[0]['rank_metadata']['corpus_novelty']
    assert top_meta['repo_seen_before'] is True
    assert top_meta['novel_path_count'] == 2
    assert top_meta['overlapping_path_count'] == 0
