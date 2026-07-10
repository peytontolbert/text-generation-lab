from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from episode_example_quality import prune_context_rows, require_passing_example
from long_context_common import read_jsonl, write_json, write_jsonl

STRONG_VERIFIED_ROUTES = {'PATCH_PLUS_EXEC', 'PATCH_PLUS_VERIFY', 'COMMIT_PLUS_VERIFY'}


def _structured_query_payload(row: dict[str, Any]) -> dict[str, Any]:
    repo_id = str(row.get('repo_id') or '')
    seed_paths = list(row.get('seed_paths') or [])
    selected_tests = list(row.get('selected_tests') or [])
    seed_symbols = list(row.get('seed_symbols') or [])[:32]
    source_metadata = dict(row.get('source_metadata') or {})
    execution_route = str(source_metadata.get('route') or '')
    test_selection_route = str(row.get('test_selection_route') or '')
    target_state = dict((row.get('target') or {}).get('state_after') or {})
    expected_changed_files = list(target_state.get('expected_changed_files') or seed_paths)
    verification_targets = list(target_state.get('verification_targets') or selected_tests)
    task_summary = str(row.get('goal') or '').strip()
    if not task_summary:
        raise ValueError(f"missing_task_summary:{row.get('episode_id')}")
    summary_lines = [line.strip() for line in task_summary.splitlines() if line.strip()]
    if summary_lines and summary_lines[0].lower().startswith('modify repository files'):
        task_lines = summary_lines
    else:
        task_lines = [f'Task: {task_summary}']

    query_lines = [
        f'Repository: {repo_id}',
        *task_lines,
        'Changed files: ' + ', '.join(expected_changed_files),
        'Key symbols: ' + ', '.join(seed_symbols),
        'Verification targets: ' + ', '.join(verification_targets),
        f'Execution route: {execution_route}',
        f'Test selection route: {test_selection_route}',
    ]
    trace_failure_types = list(source_metadata.get('trace_failure_types') or [])
    trace_exception_types = list(source_metadata.get('trace_exception_types') or [])
    trace_verification_targets = list(source_metadata.get('trace_verification_targets') or [])
    if trace_failure_types:
        query_lines.append('Observed failure types: ' + ', '.join(str(item) for item in trace_failure_types[:8]))
    if trace_exception_types:
        query_lines.append('Observed exception types: ' + ', '.join(str(item) for item in trace_exception_types[:8]))
    if trace_verification_targets:
        query_lines.append('Trace verification targets: ' + ', '.join(str(item) for item in trace_verification_targets[:8]))

    return {
        'text': '\n'.join(query_lines),
        'repo_id': repo_id,
        'seed_paths': seed_paths,
        'selected_tests': selected_tests,
        'seed_symbols': seed_symbols,
        'execution_route': execution_route,
        'test_selection_route': test_selection_route,
    }


def _target_payload(row: dict[str, Any]) -> dict[str, Any]:
    target = dict(row.get('target') or {})
    expected_patch_summary = str(target.get('expected_patch_summary') or '').strip()
    expected_outcome = str(target.get('expected_outcome') or '').strip()
    state_after = target.get('state_after')
    if not expected_patch_summary:
        raise ValueError(f"missing_expected_patch_summary:{row.get('episode_id')}")
    if not expected_outcome:
        raise ValueError(f"missing_expected_outcome:{row.get('episode_id')}")
    if not isinstance(state_after, dict) or not state_after:
        raise ValueError(f"missing_state_after:{row.get('episode_id')}")
    if not list(state_after.get('expected_changed_files') or []):
        raise ValueError(f"missing_expected_changed_files:{row.get('episode_id')}")
    if not list(state_after.get('verification_targets') or []):
        raise ValueError(f"missing_verification_targets:{row.get('episode_id')}")
    final_answer = '\n'.join(
        [
            f'Patch intent: {expected_patch_summary}',
            f'Expected outcome: {expected_outcome}',
            'Changed files: ' + ', '.join(list(state_after.get('expected_changed_files') or [])),
            'Verification targets: ' + ', '.join(list(state_after.get('verification_targets') or [])),
            'Execution route: ' + str(state_after.get('execution_route') or ''),
        ]
    )
    return {
        'final_answer': final_answer,
        'final_state': state_after,
    }


def build_packable_episode_examples(*, episodes_path: Path, min_quality_score: float = 0.75) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = read_jsonl(episodes_path)
    examples: list[dict[str, Any]] = []
    quality_scores: list[float] = []
    for row in rows:
        raw_context_rows = [dict(context_row) for context_row in row.get('context_rows', []) if isinstance(context_row, dict)]
        source_metadata = dict(row.get('source_metadata') or {})
        execution_route = str(source_metadata.get('route') or '')
        if execution_route not in STRONG_VERIFIED_ROUTES:
            raise ValueError(f"weak_execution_route:{row.get('episode_id')}:{execution_route}")
        example = {
            'example_id': str(row.get('episode_id') or ''),
            'repo_id': str(row.get('repo_id') or ''),
            'program_id': str(row.get('repo_id') or ''),
            'seed_type': str(row.get('seed_type') or ''),
            'context_token_count': int(row.get('context_token_count') or 0),
            'rendered_chunk_ids': [str(context_row.get('chunk_id') or '') for context_row in raw_context_rows if str(context_row.get('chunk_id') or '')],
            'context_rows': raw_context_rows,
            'query': _structured_query_payload(row),
            'targets': _target_payload(row),
            'difficulty': {
                'level': 4 if list(row.get('selected_tests') or []) else 3,
                'seed_path_count': len(list(row.get('seed_paths') or [])),
                'context_role_count': len(dict(row.get('context_role_counts') or {})),
            },
            'quality': {
                'test_selection_route': str(row.get('test_selection_route') or ''),
                'selected_test_count': len(list(row.get('selected_tests') or [])),
                'candidate_file_count': int(row.get('candidate_file_count') or 0),
            },
            'metadata': {
                'repo_id': str(row.get('repo_id') or ''),
                'local_repo_root': str(row.get('local_repo_root') or ''),
                'source_metadata': source_metadata,
            },
        }
        pruned_context_rows, pruning_report = prune_context_rows(example)
        example['context_rows'] = pruned_context_rows
        example['rendered_chunk_ids'] = [str(context_row.get('chunk_id') or '') for context_row in pruned_context_rows if str(context_row.get('chunk_id') or '')]
        example['context_token_count'] = sum(int(context_row.get('token_count') or 0) for context_row in pruned_context_rows)
        quality_report = require_passing_example(example, min_quality_score=min_quality_score)
        example['quality']['quality_score'] = float(quality_report['overall_score'])
        example['quality']['quality_report'] = quality_report
        example['quality']['context_pruning'] = pruning_report
        quality_scores.append(float(quality_report['overall_score']))
        examples.append(example)
    summary = {
        'episode_rows': len(rows),
        'example_rows': len(examples),
        'direct_context_examples': sum(int(bool(example.get('context_rows'))) for example in examples),
        'min_quality_score': float(min_quality_score),
        'avg_quality_score': (sum(quality_scores) / len(quality_scores)) if quality_scores else 0.0,
        'rejected_rows': 0,
    }
    return examples, summary


def main() -> None:
    parser = argparse.ArgumentParser(description='Build packable long-context examples from mined episode rows.')
    parser.add_argument('--episodes', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--summary-output', type=Path)
    parser.add_argument('--min-quality-score', type=float, default=0.75)
    args = parser.parse_args()
    rows, summary = build_packable_episode_examples(episodes_path=args.episodes, min_quality_score=args.min_quality_score)
    write_jsonl(args.output, rows)
    write_json(args.summary_output or args.output.with_name('packable_episode_examples_summary.json'), summary)


if __name__ == '__main__':
    main()
