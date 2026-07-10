from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from build_packable_episode_examples import build_packable_episode_examples  # noqa: E402


def test_build_packable_episode_examples_preserves_context_rows(tmp_path: Path) -> None:
    episodes = tmp_path / 'episodes.jsonl'
    episodes.write_text(
        json.dumps(
            {
                'episode_id': 'ep1',
                'repo_id': 'repo_a',
                'seed_type': 'session_episode_local_root',
                'goal': 'Modify repository files to preserve behavior under execution-backed maintenance.\nChanged files: src/loader.py\nVerification targets: tests/test_loader.py\nKey symbols: load_tensor\nExecution route: PATCH_PLUS_EXEC',
                'seed_paths': ['src/loader.py'],
                'seed_symbols': ['load_tensor'],
                'selected_tests': ['tests/test_loader.py'],
                'context_token_count': 42,
                'context_role_counts': {'seed_change': 1, 'verification_constraint': 1},
                'candidate_file_count': 8,
                'test_selection_route': 'PASS_TARGETED_TEST_SELECTION',
                'context_rows': [
                    {'chunk_id': 'c1', 'source_type': 'local_repo', 'source_id': 'repo_a', 'path': 'src/loader.py', 'token_count': 20, 'text': 'def load(): pass', 'role': 'seed_change'},
                    {'chunk_id': 'c2', 'source_type': 'local_repo', 'source_id': 'repo_a', 'path': 'tests/test_loader.py', 'token_count': 22, 'text': 'def test_load(): pass', 'role': 'verification_constraint'},
                ],
                'target': {'expected_patch_summary': 'fix loader shape bug', 'expected_outcome': 'verification_targets_hold_under_patch_plus_exec', 'state_after': {'tests': 'green', 'expected_changed_files': ['src/loader.py'], 'verification_targets': ['tests/test_loader.py'], 'execution_route': 'PATCH_PLUS_EXEC'}},
                'source_metadata': {'route': 'PATCH_PLUS_EXEC', 'trace_failure_types': ['test_assertion_failure']},
            }
        ) + '\n',
        encoding='utf-8',
    )

    examples, summary = build_packable_episode_examples(episodes_path=episodes)
    assert summary['example_rows'] == 1
    example = examples[0]
    assert example['example_id'] == 'ep1'
    assert example['rendered_chunk_ids'] == ['c1', 'c2']
    assert example['context_rows'][0]['path'] == 'src/loader.py'
    assert 'Patch intent: fix loader shape bug' in example['targets']['final_answer']
    assert example['quality']['selected_test_count'] == 1
    assert example['query']['seed_symbols'] == ['load_tensor']
    assert 'Observed failure types: test_assertion_failure' in example['query']['text']


def test_build_packable_episode_examples_fails_without_strong_target(tmp_path: Path) -> None:
    episodes = tmp_path / 'episodes.jsonl'
    episodes.write_text(
        json.dumps(
            {
                'episode_id': 'ep_missing',
                'repo_id': 'repo_a',
                'seed_type': 'session_episode_local_root',
                'goal': 'generic',
                'seed_paths': ['src/loader.py'],
                'selected_tests': ['tests/test_loader.py'],
                'context_token_count': 1,
                'context_rows': [],
                'target': {},
            }
        ) + '\n',
        encoding='utf-8',
    )

    with pytest.raises(ValueError, match='weak_execution_route'):
        build_packable_episode_examples(episodes_path=episodes)
