from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from audit_strict_long_context_training_signals import audit_strict_long_context_training_signals
from build_long_context_training_packs import build_long_context_packs
from long_context_common import read_jsonl, write_json, write_jsonl
from long_context_parquet import shard_path, write_parquet_shard


LOCAL_CONTEXT_ROLES = {'seed_change', 'repo_graph_neighbor', 'test_neighbor', 'verification_constraint'}


def _load_examples(paths: list[Path]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for path in paths:
        for row in read_jsonl(path):
            example_id = str(row.get('example_id') or '')
            if not example_id:
                raise ValueError(f'missing_example_id:{path}')
            if example_id in seen_ids:
                continue
            seen_ids.add(example_id)
            merged.append(row)
    if not merged:
        raise ValueError('no_examples_loaded')
    return merged


def _example_quality_score(row: dict[str, Any]) -> float:
    quality = dict(row.get('quality') or {})
    value = quality.get('quality_score')
    if value is None:
        raise ValueError(f"missing_quality_score:{row.get('example_id')}")
    return float(value)


def _filter_examples(rows: list[dict[str, Any]], *, min_example_quality: float) -> list[dict[str, Any]]:
    kept = [row for row in rows if _example_quality_score(row) >= float(min_example_quality)]
    if not kept:
        raise ValueError('no_examples_meet_quality_floor')
    return kept


def _role_counts_for_pack(pack_row: dict[str, Any], examples_by_id: dict[str, dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for example_id in pack_row.get('example_ids', []):
        example = examples_by_id.get(str(example_id))
        if not example:
            continue
        for row in example.get('context_rows', []):
            counts[str(row.get('role') or '')] += 1
    return dict(sorted(counts.items()))


def _pack_quality_report(
    pack_row: dict[str, Any],
    training_row: dict[str, Any],
    *,
    examples_by_id: dict[str, dict[str, Any]],
    min_pack_tokens: int,
    min_example_quality: float,
    min_avg_example_quality: float,
    min_distinct_repos: int,
    require_source_types: set[str],
    min_verification_rows: int,
) -> dict[str, Any]:
    example_ids = [str(item) for item in pack_row.get('example_ids', []) if str(item)]
    examples = [examples_by_id[example_id] for example_id in example_ids if example_id in examples_by_id]
    if not examples:
        raise ValueError(f"pack_without_examples:{pack_row.get('pack_id')}")

    quality_scores = [_example_quality_score(example) for example in examples]
    repo_ids = [str(example.get('repo_id') or example.get('program_id') or '') for example in examples if str(example.get('repo_id') or example.get('program_id') or '')]
    distinct_repos = sorted(set(repo_ids))
    context_rows = [dict(row) for row in training_row.get('context_rows', []) if isinstance(row, dict)]
    source_mix = Counter(str(row.get('source_type') or 'unknown') for row in context_rows)
    role_counts = _role_counts_for_pack(pack_row, examples_by_id)
    external_rows = [row for row in context_rows if str(row.get('source_type') or '') != 'local_repo']
    fatal_reasons: list[str] = []

    min_quality = min(quality_scores)
    avg_quality = sum(quality_scores) / len(quality_scores)
    if int(pack_row.get('pack_token_count') or 0) < int(min_pack_tokens):
        fatal_reasons.append('underfilled_pack')
    if min_quality < float(min_example_quality):
        fatal_reasons.append('pack_contains_low_quality_example')
    if avg_quality < float(min_avg_example_quality):
        fatal_reasons.append('pack_average_quality_below_threshold')
    if len(distinct_repos) < int(min_distinct_repos):
        fatal_reasons.append('insufficient_repo_diversity')
    if int(role_counts.get('verification_constraint', 0)) < int(min_verification_rows):
        fatal_reasons.append('insufficient_verification_rows')
    if require_source_types - set(source_mix):
        fatal_reasons.append('missing_required_source_types')
    if not external_rows:
        fatal_reasons.append('missing_external_rows')

    return {
        'pack_id': str(pack_row.get('pack_id') or ''),
        'pack_token_count': int(pack_row.get('pack_token_count') or 0),
        'example_count': len(examples),
        'avg_example_quality': avg_quality,
        'min_example_quality': min_quality,
        'distinct_repo_count': len(distinct_repos),
        'distinct_repos': distinct_repos[:64],
        'source_mix': dict(sorted(source_mix.items())),
        'role_counts': role_counts,
        'external_row_count': len(external_rows),
        'fatal_reasons': fatal_reasons,
    }


def build_strict_long_context_episode_packs(
    *,
    example_paths: list[Path],
    output_dir: Path,
    target_pack_tokens: int,
    min_pack_tokens: int | None = None,
    max_examples_per_pack: int | None = None,
    allow_example_reuse: bool = False,
    family_key_field: str | None = 'repo_id',
    max_packs: int | None = None,
    min_example_quality: float = 0.90,
    min_avg_example_quality: float = 0.94,
    min_distinct_repos: int = 4,
    require_source_types: set[str] | None = None,
    min_verification_rows: int = 4,
    min_locality_ready_fraction: float = 0.60,
    min_retrieval_ready_fraction: float = 0.55,
    min_long_range_join_ready_fraction: float = 0.40,
    min_state_update_ready_fraction: float = 0.80,
    min_target_rows_for_lost_state_probe: int = 32,
    min_programs_for_lost_state_probe: int = 8,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    require_source_types = set(require_source_types or {'repo', 'paper'})
    merged_examples = _load_examples(example_paths)
    filtered_examples = _filter_examples(merged_examples, min_example_quality=min_example_quality)
    temp_examples_path = output_dir / '_merged_filtered_examples.jsonl'
    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(temp_examples_path, filtered_examples)

    packs, pack_chunk_rows, training_rows, pack_summary = build_long_context_packs(
        index_dir=None,
        examples_path=temp_examples_path,
        target_pack_tokens=target_pack_tokens,
        min_pack_tokens=min_pack_tokens,
        max_examples_per_pack=max_examples_per_pack,
        allow_example_reuse=allow_example_reuse,
        family_key_field=family_key_field,
        max_packs=max_packs,
    )
    examples_by_id = {str(row.get('example_id') or ''): row for row in filtered_examples}
    training_rows_audit_input = output_dir / 'strict_long_context_pack_training_rows.audit_input.jsonl'
    write_jsonl(training_rows_audit_input, training_rows)
    reports = [
        _pack_quality_report(
            pack_row,
            training_row,
            examples_by_id=examples_by_id,
            min_pack_tokens=int(min_pack_tokens or max(1, target_pack_tokens // 2)),
            min_example_quality=min_example_quality,
            min_avg_example_quality=min_avg_example_quality,
            min_distinct_repos=min_distinct_repos,
            require_source_types=require_source_types,
            min_verification_rows=min_verification_rows,
        )
        for pack_row, training_row in zip(packs, training_rows)
    ]
    signal_pack_rows, signal_target_rows, signal_summary = audit_strict_long_context_training_signals(
        training_rows_path=output_dir / 'strict_long_context_pack_training_rows.audit_input.jsonl',
        min_locality_ready_fraction=min_locality_ready_fraction,
        min_retrieval_ready_fraction=min_retrieval_ready_fraction,
        min_long_range_join_ready_fraction=min_long_range_join_ready_fraction,
        min_state_update_ready_fraction=min_state_update_ready_fraction,
        min_target_rows_for_lost_state_probe=min_target_rows_for_lost_state_probe,
        min_programs_for_lost_state_probe=min_programs_for_lost_state_probe,
    )
    signal_by_pack = {str(row.get('pack_id') or ''): row for row in signal_pack_rows}
    reports = [
        {
            **report,
            'training_signal_audit': signal_by_pack.get(report['pack_id'], {}),
        }
        for report in reports
    ]
    quality_failing = [report for report in reports if report['fatal_reasons']]
    signal_failing = [row for row in signal_pack_rows if not row.get('accepted')]
    if quality_failing or signal_failing:
        failure_rows = []
        for row in quality_failing[:10]:
            failure_rows.append(f"{row['pack_id']}:{','.join(row['fatal_reasons'])}")
        for row in signal_failing[:10]:
            failure_rows.append(f"{row['pack_id']}:{','.join(row.get('fatal_reasons') or [])}")
        raise ValueError('strict_pack_quality_failure:' + ';'.join(failure_rows[:10]))

    write_jsonl(output_dir / 'strict_long_context_training_signal_pack_audit.jsonl', signal_pack_rows)
    write_jsonl(output_dir / 'strict_long_context_training_signal_target_audit.jsonl', signal_target_rows)
    write_json(output_dir / 'strict_long_context_training_signal_summary.json', signal_summary)

    summary = {
        **pack_summary,
        'input_example_count': len(merged_examples),
        'filtered_example_count': len(filtered_examples),
        'min_example_quality': float(min_example_quality),
        'min_avg_example_quality': float(min_avg_example_quality),
        'min_distinct_repos': int(min_distinct_repos),
        'required_source_types': sorted(require_source_types),
        'min_verification_rows': int(min_verification_rows),
        'avg_pack_example_quality': (sum(float(report['avg_example_quality']) for report in reports) / len(reports)) if reports else 0.0,
        'avg_pack_token_count': (sum(int(report['pack_token_count']) for report in reports) / len(reports)) if reports else 0.0,
        'max_pack_token_count': max((int(report['pack_token_count']) for report in reports), default=0),
        'min_pack_token_count': min((int(report['pack_token_count']) for report in reports), default=0),
        'training_signal_summary': signal_summary,
    }
    return packs, pack_chunk_rows, training_rows, reports, summary


def main() -> None:
    parser = argparse.ArgumentParser(description='Build strict long-context episode packs with pack-level quality gates.')
    parser.add_argument('--examples', type=Path, nargs='+', required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--target-pack-tokens', type=int, required=True)
    parser.add_argument('--min-pack-tokens', type=int)
    parser.add_argument('--max-examples-per-pack', type=int)
    parser.add_argument('--allow-example-reuse', action='store_true')
    parser.add_argument('--family-key-field', type=str, default='repo_id')
    parser.add_argument('--max-packs', type=int)
    parser.add_argument('--min-example-quality', type=float, default=0.90)
    parser.add_argument('--min-avg-example-quality', type=float, default=0.94)
    parser.add_argument('--min-distinct-repos', type=int, default=4)
    parser.add_argument('--require-source-types', nargs='*', default=['repo', 'paper'])
    parser.add_argument('--min-verification-rows', type=int, default=4)
    parser.add_argument('--min-locality-ready-fraction', type=float, default=0.60)
    parser.add_argument('--min-retrieval-ready-fraction', type=float, default=0.55)
    parser.add_argument('--min-long-range-join-ready-fraction', type=float, default=0.40)
    parser.add_argument('--min-state-update-ready-fraction', type=float, default=0.80)
    parser.add_argument('--min-target-rows-for-lost-state-probe', type=int, default=32)
    parser.add_argument('--min-programs-for-lost-state-probe', type=int, default=8)
    args = parser.parse_args()

    packs, pack_chunk_rows, training_rows, reports, summary = build_strict_long_context_episode_packs(
        example_paths=args.examples,
        output_dir=args.output_dir,
        target_pack_tokens=args.target_pack_tokens,
        min_pack_tokens=args.min_pack_tokens,
        max_examples_per_pack=args.max_examples_per_pack,
        allow_example_reuse=args.allow_example_reuse,
        family_key_field=args.family_key_field,
        max_packs=args.max_packs,
        min_example_quality=args.min_example_quality,
        min_avg_example_quality=args.min_avg_example_quality,
        min_distinct_repos=args.min_distinct_repos,
        require_source_types=set(args.require_source_types),
        min_verification_rows=args.min_verification_rows,
        min_locality_ready_fraction=args.min_locality_ready_fraction,
        min_retrieval_ready_fraction=args.min_retrieval_ready_fraction,
        min_long_range_join_ready_fraction=args.min_long_range_join_ready_fraction,
        min_state_update_ready_fraction=args.min_state_update_ready_fraction,
        min_target_rows_for_lost_state_probe=args.min_target_rows_for_lost_state_probe,
        min_programs_for_lost_state_probe=args.min_programs_for_lost_state_probe,
    )
    write_jsonl(args.output_dir / 'strict_long_context_packs.jsonl', packs)
    write_jsonl(args.output_dir / 'strict_long_context_pack_training_rows.jsonl', training_rows)
    write_jsonl(args.output_dir / 'strict_long_context_pack_quality_reports.jsonl', reports)
    write_json(args.output_dir / 'strict_long_context_packs_summary.json', summary)
    write_parquet_shard(shard_path(args.output_dir / 'parquet', 'strict_long_context_packs', 0), packs)
    write_parquet_shard(shard_path(args.output_dir / 'parquet', 'strict_long_context_pack_chunks', 0), pack_chunk_rows)
    write_parquet_shard(shard_path(args.output_dir / 'parquet', 'strict_long_context_pack_training_rows', 0), training_rows)
    write_parquet_shard(shard_path(args.output_dir / 'parquet', 'strict_long_context_pack_quality_reports', 0), reports)


if __name__ == '__main__':
    main()
