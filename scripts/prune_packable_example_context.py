from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from episode_example_quality import prune_context_rows, require_passing_example
from long_context_common import read_jsonl, write_json, write_jsonl


def _context_token_count(rows: list[dict[str, Any]]) -> int:
    return sum(int(row.get('token_count') or 0) for row in rows)


def refresh_packable_examples_with_pruning(*, examples_path: Path, min_quality_score: float) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = read_jsonl(examples_path)
    refreshed: list[dict[str, Any]] = []
    examples_changed = 0
    total_before_rows = 0
    total_after_rows = 0
    total_dropped_low_value = 0
    total_dropped_duplicate = 0
    for row in rows:
        example = dict(row)
        example['context_rows'] = [dict(context_row) for context_row in row.get('context_rows', []) if isinstance(context_row, dict)]
        before_rows = len(example['context_rows'])
        total_before_rows += before_rows
        pruned_rows, pruning_report = prune_context_rows(example)
        example['context_rows'] = pruned_rows
        example['rendered_chunk_ids'] = [str(context_row.get('chunk_id') or '') for context_row in pruned_rows if str(context_row.get('chunk_id') or '')]
        example['context_token_count'] = _context_token_count(pruned_rows)
        quality = dict(example.get('quality') or {})
        quality_report = require_passing_example(example, min_quality_score=min_quality_score)
        quality['quality_score'] = float(quality_report['overall_score'])
        quality['quality_report'] = quality_report
        quality['context_pruning'] = pruning_report
        example['quality'] = quality
        after_rows = len(pruned_rows)
        total_after_rows += after_rows
        total_dropped_low_value += int(pruning_report.get('dropped_low_value_rows') or 0)
        total_dropped_duplicate += int(pruning_report.get('dropped_duplicate_rows') or 0)
        if before_rows != after_rows:
            examples_changed += 1
        refreshed.append(example)
    summary = {
        'example_count': len(refreshed),
        'examples_changed': examples_changed,
        'total_context_rows_before': total_before_rows,
        'total_context_rows_after': total_after_rows,
        'total_dropped_low_value_rows': total_dropped_low_value,
        'total_dropped_duplicate_rows': total_dropped_duplicate,
        'min_quality_score': float(min_quality_score),
        'avg_quality_score': (sum(float(dict(row.get('quality') or {}).get('quality_score') or 0.0) for row in refreshed) / len(refreshed)) if refreshed else 0.0,
    }
    return refreshed, summary


def main() -> None:
    parser = argparse.ArgumentParser(description='Prune weakly grounded context rows from packable examples and re-score quality.')
    parser.add_argument('--examples', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--summary-output', type=Path)
    parser.add_argument('--min-quality-score', type=float, default=0.75)
    args = parser.parse_args()
    rows, summary = refresh_packable_examples_with_pruning(examples_path=args.examples, min_quality_score=args.min_quality_score)
    write_jsonl(args.output, rows)
    write_json(args.summary_output or args.output.with_name(args.output.stem + '_summary.json'), summary)


if __name__ == '__main__':
    main()
