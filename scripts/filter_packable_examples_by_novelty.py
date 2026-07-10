from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
from typing import Any

from long_context_common import read_jsonl, write_json, write_jsonl


def _chunk_ids(example: dict[str, Any]) -> set[str]:
    rendered = {str(chunk_id) for chunk_id in example.get('rendered_chunk_ids', []) if str(chunk_id)}
    if rendered:
        return rendered
    return {
        str(row.get('chunk_id') or '')
        for row in example.get('context_rows', [])
        if isinstance(row, dict) and str(row.get('chunk_id') or '')
    }


def _group_value(example: dict[str, Any], field: str) -> str:
    value = example.get(field)
    if value is None and isinstance(example.get('metadata'), dict):
        value = dict(example.get('metadata') or {}).get(field)
    return str(value or '')


def _verification_targets(example: dict[str, Any]) -> list[str]:
    query = dict(example.get('query') or {})
    targets = dict(example.get('targets') or {})
    final_state = dict(targets.get('final_state') or {})
    selected = [str(item) for item in list(query.get('selected_tests') or []) if str(item)]
    if selected:
        return selected
    return [str(item) for item in list(final_state.get('verification_targets') or []) if str(item)]


def _verification_family_signature(example: dict[str, Any]) -> str:
    stems = []
    for path in _verification_targets(example):
        stem = Path(str(path)).stem.lower()
        if stem.startswith('test_'):
            stem = stem[5:]
        if stem.endswith('_test'):
            stem = stem[:-5]
        if stem:
            stems.append(stem)
    normalized = sorted(set(stems))
    return '|'.join(normalized)


def filter_packable_examples_by_novelty(
    *,
    examples_path: Path,
    group_field: str = 'program_id',
    min_keep_per_group: int = 1,
    min_global_novel_ratio: float = 0.08,
    min_global_novel_chunks: int = 32,
    min_group_novel_ratio: float = 0.12,
    min_group_novel_chunks: int = 48,
    max_examples_per_verification_family: int = 0,
    max_keep_per_group: int = 0,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    examples = read_jsonl(examples_path)
    ordered = sorted(
        examples,
        key=lambda row: (
            int(row.get('context_token_count', 0)),
            float(dict(row.get('quality') or {}).get('quality_score', 0.0)),
            str(row.get('example_id') or ''),
        ),
        reverse=True,
    )

    kept: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    reports: list[dict[str, Any]] = []
    kept_counts_by_group: dict[str, int] = defaultdict(int)
    kept_counts_by_verification_family: dict[str, int] = defaultdict(int)
    group_seen_chunks: dict[str, set[str]] = defaultdict(set)
    global_seen_chunks: set[str] = set()
    total_input_chunks = 0

    for example in ordered:
        example_id = str(example.get('example_id') or '')
        group = _group_value(example, group_field)
        chunk_ids = _chunk_ids(example)
        total_chunks = len(chunk_ids)
        total_input_chunks += total_chunks
        verification_family = _verification_family_signature(example)

        global_novel = chunk_ids - global_seen_chunks
        group_novel = chunk_ids - group_seen_chunks[group]
        global_novel_count = len(global_novel)
        group_novel_count = len(group_novel)
        global_novel_ratio = (global_novel_count / total_chunks) if total_chunks else 0.0
        group_novel_ratio = (group_novel_count / total_chunks) if total_chunks else 0.0

        keep = False
        reason = ''
        if kept_counts_by_group[group] < max(0, int(min_keep_per_group)):
            keep = True
            reason = 'min_keep_per_group'
        elif int(max_keep_per_group) > 0 and kept_counts_by_group[group] >= int(max_keep_per_group):
            reason = 'group_saturated'
        elif int(max_examples_per_verification_family) > 0 and verification_family and kept_counts_by_verification_family[verification_family] >= int(max_examples_per_verification_family):
            reason = 'verification_family_saturated'
        elif global_novel_ratio >= float(min_global_novel_ratio) and global_novel_count >= int(min_global_novel_chunks):
            if group_novel_ratio >= float(min_group_novel_ratio) or group_novel_count >= int(min_group_novel_chunks):
                keep = True
                reason = 'novel_global_and_group'
            else:
                reason = 'low_group_novelty'
        else:
            reason = 'low_global_novelty'

        report = {
            'example_id': example_id,
            'group': group,
            'context_token_count': int(example.get('context_token_count', 0)),
            'total_chunk_count': total_chunks,
            'global_novel_chunk_count': global_novel_count,
            'global_novel_ratio': round(global_novel_ratio, 6),
            'group_novel_chunk_count': group_novel_count,
            'group_novel_ratio': round(group_novel_ratio, 6),
            'verification_family': verification_family,
            'verification_family_kept_count_before': kept_counts_by_verification_family[verification_family] if verification_family else 0,
            'decision': 'keep' if keep else 'reject',
            'reason': reason,
        }
        reports.append(report)

        if keep:
            kept.append(example)
            kept_counts_by_group[group] += 1
            if verification_family:
                kept_counts_by_verification_family[verification_family] += 1
            global_seen_chunks.update(chunk_ids)
            group_seen_chunks[group].update(chunk_ids)
        else:
            rejected.append(report)

    kept_chunk_ids = set()
    for example in kept:
        kept_chunk_ids.update(_chunk_ids(example))

    kept_group_counts = dict(sorted(kept_counts_by_group.items()))
    summary = {
        'input_example_count': len(examples),
        'kept_example_count': len(kept),
        'rejected_example_count': len(rejected),
        'group_field': group_field,
        'min_keep_per_group': int(min_keep_per_group),
        'min_global_novel_ratio': float(min_global_novel_ratio),
        'min_global_novel_chunks': int(min_global_novel_chunks),
        'min_group_novel_ratio': float(min_group_novel_ratio),
        'min_group_novel_chunks': int(min_group_novel_chunks),
        'max_examples_per_verification_family': int(max_examples_per_verification_family),
        'max_keep_per_group': int(max_keep_per_group),
        'kept_group_counts': kept_group_counts,
        'kept_verification_family_counts': dict(sorted(kept_counts_by_verification_family.items())),
        'unique_kept_chunk_count': len(kept_chunk_ids),
        'avg_chunks_per_input_example': (total_input_chunks / len(examples)) if examples else 0.0,
        'avg_chunks_per_kept_example': (sum(len(_chunk_ids(example)) for example in kept) / len(kept)) if kept else 0.0,
        'top_rejections': rejected[: min(20, len(rejected))],
    }
    return kept, reports, summary


def main() -> None:
    parser = argparse.ArgumentParser(description='Filter packable examples by incremental chunk novelty.')
    parser.add_argument('--examples', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--report-output', type=Path, required=True)
    parser.add_argument('--summary-output', type=Path, required=True)
    parser.add_argument('--group-field', type=str, default='program_id')
    parser.add_argument('--min-keep-per-group', type=int, default=1)
    parser.add_argument('--min-global-novel-ratio', type=float, default=0.08)
    parser.add_argument('--min-global-novel-chunks', type=int, default=32)
    parser.add_argument('--min-group-novel-ratio', type=float, default=0.12)
    parser.add_argument('--min-group-novel-chunks', type=int, default=48)
    parser.add_argument('--max-examples-per-verification-family', type=int, default=0)
    parser.add_argument('--max-keep-per-group', type=int, default=0)
    args = parser.parse_args()

    kept, reports, summary = filter_packable_examples_by_novelty(
        examples_path=args.examples,
        group_field=args.group_field,
        min_keep_per_group=args.min_keep_per_group,
        min_global_novel_ratio=args.min_global_novel_ratio,
        min_global_novel_chunks=args.min_global_novel_chunks,
        min_group_novel_ratio=args.min_group_novel_ratio,
        min_group_novel_chunks=args.min_group_novel_chunks,
        max_examples_per_verification_family=args.max_examples_per_verification_family,
        max_keep_per_group=args.max_keep_per_group,
    )
    write_jsonl(args.output, kept)
    write_jsonl(args.report_output, reports)
    write_json(args.summary_output, summary)


if __name__ == '__main__':
    main()
