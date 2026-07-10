from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from episode_example_quality import score_example  # noqa: E402


def test_score_example_flags_generic_and_missing_verification() -> None:
    bad_example = {
        'example_id': 'bad1',
        'query': {'text': 'Goal: repair_or_edit | patch_tool_used', 'seed_paths': ['src/main.js'], 'selected_tests': []},
        'targets': {'final_answer': 'repair_or_edit | patch_tool_used', 'final_state': {}},
        'context_rows': [
            {'chunk_id': 'a', 'source_type': 'local_repo', 'path': 'src/main.js', 'text': 'console.log(1)', 'role': 'seed_change'},
            {'chunk_id': 'b', 'source_type': 'repo', 'path': 'AI-Papers-of-the-Week/years/2025.md', 'text': 'weekly list', 'role': 'cross_repo_analogue'},
        ],
    }
    report = score_example(bad_example)
    assert 'generic_final_answer' in report['fatal_reasons']
    assert 'missing_selected_tests' in report['fatal_reasons']
    assert 'low_retrieval_precision' in report['fatal_reasons']


def test_score_example_accepts_specific_execution_grounded_example() -> None:
    good_example = {
        'example_id': 'good1',
        'query': {
            'text': 'Repository: repo_a\nTask: Modify repository files to preserve behavior under execution-backed maintenance.\nChanged files: src/loader.py\nKey symbols: tensor_loader\nVerification targets: tests/test_loader.py\nExecution route: PATCH_PLUS_EXEC\nTest selection route: PASS_TARGETED_TEST_SELECTION',
            'seed_paths': ['src/loader.py'],
            'selected_tests': ['tests/test_loader.py'],
            'seed_symbols': ['tensor_loader'],
        },
        'targets': {
            'final_answer': 'Patch intent: Update src/loader.py so that tests/test_loader.py remain satisfied after patch_plus_exec.\nExpected outcome: verification_targets_hold_under_patch_plus_exec\nChanged files: src/loader.py\nVerification targets: tests/test_loader.py\nExecution route: PATCH_PLUS_EXEC',
            'final_state': {
                'expected_changed_files': ['src/loader.py'],
                'verification_targets': ['tests/test_loader.py'],
                'execution_route': 'PATCH_PLUS_EXEC',
            },
        },
        'context_rows': [
            {'chunk_id': 'a', 'source_type': 'local_repo', 'path': 'src/loader.py', 'text': 'def tensor_loader(x): return x', 'role': 'seed_change'},
            {'chunk_id': 'b', 'source_type': 'local_repo', 'path': 'tests/test_loader.py', 'text': 'def test_load(): assert tensor_loader(1) == 1', 'role': 'verification_constraint'},
            {'chunk_id': 'c', 'source_type': 'repo', 'path': 'other_repo/src/loader.py', 'text': 'def tensor_loader(batch): return batch', 'role': 'cross_repo_analogue'},
            {'chunk_id': 'd', 'source_type': 'paper', 'path': 'paper_a/algorithm.txt', 'text': 'algorithm for tensor loader verification under execution', 'role': 'algorithm_grounding'},
            {'chunk_id': 'e', 'source_type': 'dataset', 'path': 'trace_a/error_trace.txt', 'text': 'runtime error trace for tensor loader failure', 'role': 'trace_analogue'},
        ],
    }
    report = score_example(good_example)
    assert not report['fatal_reasons']
    assert report['overall_score'] >= 0.75
    assert report['grounded_retrieval_precision'] == 1.0
    assert report['evidence_source_diversity'] == 1.0


def test_score_example_excludes_local_repo_roles_from_external_diversity() -> None:
    example = {
        'query': {
            'text': 'Repository: repo_a\nChanged files: src/a.py\nVerification targets: tests/test_a.py',
            'seed_paths': ['src/a.py'],
            'selected_tests': ['tests/test_a.py'],
            'seed_symbols': ['tensor_loader'],
        },
        'targets': {
            'final_answer': 'Patch intent: update src/a.py while keeping tests/test_a.py satisfied.',
            'final_state': {
                'execution_route': 'COMMIT_PLUS_VERIFY',
                'expected_changed_files': ['src/a.py'],
                'verification_targets': ['tests/test_a.py'],
            },
        },
        'context_rows': [
            {
                'source_type': 'repo',
                'path': 'repo_a/src/a.py',
                'text': 'def tensor_loader(x):\n    return x\n',
                'role': 'seed_change',
            },
            {
                'source_type': 'repo',
                'path': 'repo_a/tests/test_a.py',
                'text': 'def test_a():\n    assert tensor_loader(1) == 1\n',
                'role': 'verification_constraint',
            },
            {
                'source_type': 'repo',
                'path': 'other_repo/src/tensor_loader.py',
                'text': 'def tensor_loader(shape_error, verification):\n    return shape_error\n',
                'role': 'cross_repo_analogue',
            },
            {
                'source_type': 'paper',
                'path': 'paper_a/algorithm.txt',
                'text': 'Tensor loader verification algorithm under execution.',
                'role': 'algorithm_grounding',
            },
            {
                'source_type': 'dataset',
                'path': 'trace_a/error_trace.txt',
                'text': 'Runtime error trace for tensor loader verification failure.',
                'role': 'trace_analogue',
            },
        ],
    }
    report = score_example(example)
    assert report['external_row_count'] == 3
    assert report['external_path_diversity'] == 1.0
    assert 'low_external_path_diversity' not in report['fatal_reasons']


def test_score_example_rejects_generic_trace_overlap_without_seed_binding() -> None:
    example = {
        'query': {
            'text': 'Repository: repo_a\nChanged files: src/loader.py\nVerification targets: tests/test_loader.py\nKey symbols: tensor_loader',
            'seed_paths': ['src/loader.py'],
            'selected_tests': ['tests/test_loader.py'],
            'seed_symbols': ['tensor_loader'],
        },
        'targets': {
            'final_answer': 'Patch intent: update src/loader.py while keeping tests/test_loader.py satisfied.',
            'final_state': {
                'execution_route': 'PATCH_PLUS_EXEC',
                'expected_changed_files': ['src/loader.py'],
                'verification_targets': ['tests/test_loader.py'],
            },
        },
        'context_rows': [
            {'source_type': 'local_repo', 'path': 'src/loader.py', 'text': 'def tensor_loader(x): return x', 'role': 'seed_change'},
            {'source_type': 'local_repo', 'path': 'tests/test_loader.py', 'text': 'assert tensor_loader(1) == 1', 'role': 'verification_constraint'},
            {'source_type': 'dataset', 'path': 'trace_a/runtime_error.txt', 'text': 'runtime error trace exception stack failure', 'role': 'trace_analogue'},
        ],
    }
    report = score_example(example)
    assert 'low_retrieval_precision' in report['fatal_reasons']
    assert 'low_grounded_retrieval_precision' in report['fatal_reasons']


def test_score_example_rejects_generic_verification_constraint_without_focus_overlap() -> None:
    example = {
        'query': {
            'text': 'Repository: repo_a\nChanged files: src/train_gpt_upgrade.py\nVerification targets: data/tokenizer_specs.json\nKey symbols: train_upgrade',
            'seed_paths': ['src/train_gpt_upgrade.py'],
            'selected_tests': ['data/tokenizer_specs.json'],
            'seed_symbols': ['train_upgrade'],
        },
        'targets': {
            'final_answer': 'Patch intent: update src/train_gpt_upgrade.py while keeping data/tokenizer_specs.json satisfied.',
            'final_state': {
                'execution_route': 'PATCH_PLUS_EXEC',
                'expected_changed_files': ['src/train_gpt_upgrade.py'],
                'verification_targets': ['data/tokenizer_specs.json'],
            },
        },
        'context_rows': [
            {'source_type': 'local_repo', 'path': 'src/train_gpt_upgrade.py', 'text': 'def train_upgrade(x): return x', 'role': 'seed_change'},
            {'source_type': 'local_repo', 'path': 'data/tokenizer_specs.json', 'text': '{"tokenizer": "bpe", "spec": "generic"}', 'role': 'verification_constraint', 'retrieval_reason': 'directory_overlap|verification_marker'},
            {'source_type': 'paper', 'path': 'paper_a/algorithm.txt', 'text': 'Training upgrade algorithm under execution.', 'role': 'algorithm_grounding'},
        ],
    }
    report = score_example(example)
    assert 'low_verification_constraint_specificity' in report['fatal_reasons']
    assert report['verification_constraint_specificity'] < 0.55


def test_score_example_rejects_low_verification_alignment_even_with_grounded_overlap() -> None:
    example = {
        'query': {
            'text': 'Repository: repo_a\nChanged files: src/loader.py\nVerification targets: tests/test_behavior_contract.py\nKey symbols: tensor_loader',
            'seed_paths': ['src/loader.py'],
            'selected_tests': ['tests/test_behavior_contract.py'],
            'seed_symbols': ['tensor_loader'],
        },
        'targets': {
            'final_answer': 'Patch intent: update src/loader.py while keeping tests/test_behavior_contract.py satisfied.',
            'final_state': {
                'execution_route': 'PATCH_PLUS_EXEC',
                'expected_changed_files': ['src/loader.py'],
                'verification_targets': ['tests/test_behavior_contract.py'],
            },
        },
        'context_rows': [
            {'source_type': 'local_repo', 'path': 'src/loader.py', 'text': 'def tensor_loader(x): return x', 'role': 'seed_change'},
            {'source_type': 'local_repo', 'path': 'tests/test_behavior_contract.py', 'text': 'assert tensor_loader(1) == 1', 'role': 'verification_constraint'},
            {'source_type': 'repo', 'path': 'other_repo/src/loader.py', 'text': 'def tensor_loader(shape_error): return shape_error', 'role': 'cross_repo_analogue'},
            {'source_type': 'repo', 'path': 'other_repo/src/loader_alt.py', 'text': 'def tensor_loader(batch): return batch', 'role': 'cross_repo_analogue'},
            {'source_type': 'paper', 'path': 'paper_a/algorithm.txt', 'text': 'Tensor loader algorithm under execution.', 'role': 'algorithm_grounding'},
        ],
    }
    report = score_example(example)
    assert 'low_verification_alignment' in report['fatal_reasons']
    assert report['grounded_retrieval_precision'] == 1.0
    assert report['verification_alignment'] < 0.34
