from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from prune_packable_example_context import refresh_packable_examples_with_pruning  # noqa: E402


def test_refresh_packable_examples_with_pruning_removes_weak_rows_and_rescores(tmp_path: Path) -> None:
    examples_path = tmp_path / 'examples.jsonl'
    row = {
        'example_id': 'ex1',
        'repo_id': 'repo_a',
        'program_id': 'repo_a',
        'context_token_count': 140,
        'rendered_chunk_ids': ['c1', 'c2', 'c3', 'c4', 'junk1'],
        'context_rows': [
            {'chunk_id': 'c1', 'source_type': 'local_repo', 'source_id': 'repo_a', 'path': 'src/loader.py', 'token_count': 20, 'text': 'def tensor_loader(x): return x', 'role': 'seed_change'},
            {'chunk_id': 'c2', 'source_type': 'local_repo', 'source_id': 'repo_a', 'path': 'tests/test_loader.py', 'token_count': 22, 'text': 'assert tensor_loader(1) == 1', 'role': 'verification_constraint'},
            {'chunk_id': 'c3', 'source_type': 'repo', 'source_id': 'other_repo', 'path': 'other_repo/src/loader.py', 'token_count': 30, 'text': 'def tensor_loader(batch): return batch', 'role': 'cross_repo_analogue', 'retrieval_reason': 'path_stem_overlap|shared_seed_symbol'},
            {'chunk_id': 'c4', 'source_type': 'paper', 'source_id': 'paper_a', 'path': 'paper_a/algorithm.txt', 'token_count': 28, 'text': 'This algorithm describes tensor loader verification under execution.', 'role': 'algorithm_grounding', 'retrieval_reason': 'focus_overlap'},
            {'chunk_id': 'junk1', 'source_type': 'dataset', 'source_id': 'junk_trace', 'path': 'junk_trace/gods_universe.txt', 'token_count': 40, 'text': 'Sacred Goal: achieve full self-rewriting capability with god-level recursive creativity.', 'role': 'trace_analogue', 'retrieval_reason': 'trace'},
        ],
        'query': {
            'text': 'Repository: repo_a\nTask: repair tensor loader\nChanged files: src/loader.py\nKey symbols: tensor_loader\nVerification targets: tests/test_loader.py\nExecution route: PATCH_PLUS_EXEC',
            'seed_paths': ['src/loader.py'],
            'selected_tests': ['tests/test_loader.py'],
            'seed_symbols': ['tensor_loader'],
        },
        'targets': {
            'final_answer': 'Patch intent: update src/loader.py\nExpected outcome: verification target stays green\nChanged files: src/loader.py\nVerification targets: tests/test_loader.py\nExecution route: PATCH_PLUS_EXEC',
            'final_state': {
                'expected_changed_files': ['src/loader.py'],
                'verification_targets': ['tests/test_loader.py'],
                'execution_route': 'PATCH_PLUS_EXEC',
            },
        },
        'quality': {'quality_score': 0.8},
    }
    examples_path.write_text(json.dumps(row) + '\n', encoding='utf-8')

    refreshed, summary = refresh_packable_examples_with_pruning(examples_path=examples_path, min_quality_score=0.60)

    assert summary['example_count'] == 1
    assert summary['examples_changed'] == 1
    assert summary['total_dropped_low_value_rows'] == 1
    assert refreshed[0]['rendered_chunk_ids'] == ['c1', 'c2', 'c3', 'c4']
    assert refreshed[0]['context_token_count'] == 100
    assert refreshed[0]['quality']['context_pruning']['dropped_low_value_rows'] == 1
    assert refreshed[0]['quality']['quality_score'] >= 0.60
