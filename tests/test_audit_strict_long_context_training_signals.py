from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from audit_strict_long_context_training_signals import audit_strict_long_context_training_signals  # noqa: E402
from long_context_common import write_jsonl  # noqa: E402


def _final_state(*, changed_files: list[str], key_symbols: list[str], verification_targets: list[str]) -> str:
    return json.dumps({
        'execution_route': 'PATCH_PLUS_EXEC',
        'expected_changed_files': changed_files,
        'key_symbols': key_symbols,
        'test_selection_route': 'PASS_TARGETED_TEST_SELECTION',
        'verification_targets': verification_targets,
    })


def test_audit_strict_long_context_training_signals_accepts_probe_ready_pack(tmp_path: Path) -> None:
    context_rows = [
        {
            'chunk_id': 'c1', 'chunk_ordinal': 0, 'source_type': 'local_repo', 'role': 'seed_change',
            'path': 'repo_a/src/router.py', 'text': 'router dispatch state machine uses merge_state and apply_update', 'token_count': 20,
        },
        {
            'chunk_id': 'c2', 'chunk_ordinal': 1, 'source_type': 'repo', 'role': 'trace_analogue',
            'path': 'repo_a/tests/test_router.py', 'text': 'test_router covers merge_state apply_update and event stream assertions', 'token_count': 20,
        },
        {
            'chunk_id': 'c3', 'chunk_ordinal': 2, 'source_type': 'paper', 'role': 'algorithm_grounding',
            'path': 'papers/state_merge_attention.txt', 'text': 'merge_state apply_update event stream state reconciliation algorithm', 'token_count': 20,
        },
        {
            'chunk_id': 'c4', 'chunk_ordinal': 3, 'source_type': 'dataset', 'role': 'verification_constraint',
            'path': 'logs/router_failure_trace.txt', 'text': 'router failure trace assert apply_update event stream mismatch', 'token_count': 20,
        },
        {
            'chunk_id': 'c5', 'chunk_ordinal': 4, 'source_type': 'local_repo', 'role': 'seed_change',
            'path': 'repo_b/src/allocator.py', 'text': 'allocator rebalance_state uses schedule_merge and apply_budget', 'token_count': 20,
        },
        {
            'chunk_id': 'c6', 'chunk_ordinal': 5, 'source_type': 'repo', 'role': 'test_neighbor',
            'path': 'repo_b/tests/test_allocator.py', 'text': 'test_allocator covers rebalance_state apply_budget schedule_merge', 'token_count': 20,
        },
        {
            'chunk_id': 'c7', 'chunk_ordinal': 6, 'source_type': 'paper', 'role': 'cross_repo_analogue',
            'path': 'papers/budget_rebalance.txt', 'text': 'rebalance_state schedule_merge apply_budget allocator state updates', 'token_count': 20,
        },
        {
            'chunk_id': 'c8', 'chunk_ordinal': 7, 'source_type': 'dataset', 'role': 'verification_constraint',
            'path': 'logs/allocator_runtime.txt', 'text': 'allocator runtime trace apply_budget mismatch schedule_merge', 'token_count': 20,
        },
    ]
    target_rows = []
    for index in range(32):
        if index % 2 == 0:
            target_rows.append({
                'example_id': f'ex-{index}',
                'program_id': f'prog-{index % 8}',
                'query_index': index + 1,
                'final_answer': 'update router state',
                'final_state_json': _final_state(
                    changed_files=['repo_a/src/router.py', 'repo_a/tests/test_router.py'],
                    key_symbols=['merge_state', 'apply_update'],
                    verification_targets=['repo_a/tests/test_router.py'],
                ),
            })
        else:
            target_rows.append({
                'example_id': f'ex-{index}',
                'program_id': f'prog-{index % 8}',
                'query_index': index + 1,
                'final_answer': 'update allocator state',
                'final_state_json': _final_state(
                    changed_files=['repo_b/src/allocator.py', 'repo_b/tests/test_allocator.py'],
                    key_symbols=['rebalance_state', 'apply_budget', 'schedule_merge'],
                    verification_targets=['repo_b/tests/test_allocator.py'],
                ),
            })
    for index in range(24):
        context_rows.append({
            'chunk_id': f'd{index}', 'chunk_ordinal': 8 + index, 'source_type': 'repo', 'role': 'cross_repo_analogue',
            'path': f'misc/module_{index}.py', 'text': f'unrelated helper module {index} for caching and serialization only', 'token_count': 20,
        })

    training_rows_path = tmp_path / 'training_rows.jsonl'
    write_jsonl(training_rows_path, [{
        'pack_id': 'pack-1',
        'pack_token_count': 5000000,
        'chunk_count': len(context_rows),
        'context_rows': context_rows,
        'target_rows': target_rows,
    }])

    pack_rows, target_audits, summary = audit_strict_long_context_training_signals(training_rows_path=training_rows_path)

    assert summary['accepted_pack_count'] == 1
    assert pack_rows[0]['accepted'] is True
    assert pack_rows[0]['locality_probe_ready'] is True
    assert pack_rows[0]['retrieval_probe_ready'] is True
    assert pack_rows[0]['lost_state_probe_ready'] is True
    assert pack_rows[0]['long_range_join_probe_ready'] is True
    assert pack_rows[0]['state_update_probe_ready'] is True
    assert len(target_audits) == 32


def test_audit_strict_long_context_training_signals_rejects_shortcut_pack(tmp_path: Path) -> None:
    context_rows = [
        {
            'chunk_id': 'c1', 'chunk_ordinal': 0, 'source_type': 'local_repo', 'role': 'seed_change',
            'path': 'repo/src/router.py', 'text': 'router file only', 'token_count': 20,
        },
        {
            'chunk_id': 'c2', 'chunk_ordinal': 1, 'source_type': 'local_repo', 'role': 'seed_change',
            'path': 'repo/tests/test_router.py', 'text': 'test file only', 'token_count': 20,
        },
    ]
    target_rows = [{
        'example_id': 'ex-1',
        'program_id': 'prog-1',
        'query_index': 1,
        'final_answer': 'update router state',
        'final_state_json': _final_state(
            changed_files=['repo/src/router.py'],
            key_symbols=['merge_state'],
            verification_targets=['repo/tests/test_router.py'],
        ),
    }]
    training_rows_path = tmp_path / 'training_rows.jsonl'
    write_jsonl(training_rows_path, [{
        'pack_id': 'pack-1',
        'pack_token_count': 1000,
        'chunk_count': len(context_rows),
        'context_rows': context_rows,
        'target_rows': target_rows,
    }])

    pack_rows, _, summary = audit_strict_long_context_training_signals(training_rows_path=training_rows_path)

    assert summary['accepted_pack_count'] == 0
    assert pack_rows[0]['accepted'] is False
    assert 'insufficient_locality_probe_coverage' in pack_rows[0]['fatal_reasons']
    assert 'insufficient_retrieval_probe_coverage' in pack_rows[0]['fatal_reasons']
    assert 'insufficient_lost_state_probe_coverage' in pack_rows[0]['fatal_reasons']
