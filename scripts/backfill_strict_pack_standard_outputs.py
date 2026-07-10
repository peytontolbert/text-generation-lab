from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from long_context_common import read_jsonl, write_json, write_jsonl
from long_context_parquet import shard_path, write_parquet_shard


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [dict(row) for row in read_jsonl(path)]


def _example_quality_score(row: dict[str, Any]) -> float:
    quality = dict(row.get('quality') or {})
    value = quality.get('quality_score')
    if value is None:
        raise ValueError(f"missing_quality_score:{row.get('example_id')}")
    return float(value)


def _role_counts_for_pack(training_row: dict[str, Any]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in training_row.get('context_rows', []) or []:
        if not isinstance(row, dict):
            continue
        counts[str(row.get('role') or '')] += 1
    return dict(sorted(counts.items()))


def _source_mix_for_pack(training_row: dict[str, Any]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in training_row.get('context_rows', []) or []:
        if not isinstance(row, dict):
            continue
        counts[str(row.get('source_type') or 'unknown')] += 1
    return dict(sorted(counts.items()))


def _pack_rows_from_training_rows(training_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    packs: list[dict[str, Any]] = []
    for row in training_rows:
        target_rows = [dict(item) for item in row.get('target_rows') or [] if isinstance(item, dict)]
        packs.append({
            'pack_id': str(row.get('pack_id') or ''),
            'pack_token_count': int(row.get('pack_token_count') or 0),
            'chunk_count': int(row.get('chunk_count') or len(row.get('context_rows') or [])),
            'example_count': int(row.get('example_count') or len(target_rows)),
            'example_ids': [str(item.get('example_id') or '') for item in target_rows if str(item.get('example_id') or '')],
        })
    return packs


def _pack_chunk_rows_from_training_rows(training_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for training_row in training_rows:
        pack_id = str(training_row.get('pack_id') or '')
        for row in training_row.get('context_rows', []) or []:
            if not isinstance(row, dict):
                continue
            rows.append({
                'pack_id': pack_id,
                'chunk_id': str(row.get('chunk_id') or ''),
                'chunk_ordinal': int(row.get('chunk_ordinal') or 0),
                'source_type': str(row.get('source_type') or ''),
                'path': str(row.get('path') or ''),
                'role': str(row.get('role') or ''),
            })
    return rows


def _quality_reports(
    *,
    packs: list[dict[str, Any]],
    training_rows: list[dict[str, Any]],
    examples_by_id: dict[str, dict[str, Any]],
    signal_by_pack: dict[str, dict[str, Any]],
    acceptance_mode: str,
    min_pack_tokens: int | None,
) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for pack_row, training_row in zip(packs, training_rows):
        example_ids = [str(item) for item in pack_row.get('example_ids', []) if str(item)]
        examples = [examples_by_id[item] for item in example_ids if item in examples_by_id]
        if not examples:
            raise ValueError(f"pack_without_examples:{pack_row.get('pack_id')}")
        quality_scores = [_example_quality_score(row) for row in examples]
        context_rows = [dict(row) for row in training_row.get('context_rows', []) if isinstance(row, dict)]
        external_row_count = sum(1 for row in context_rows if str(row.get('source_type') or '') != 'local_repo')
        distinct_repos = sorted({str(row.get('program_id') or '') for row in examples if str(row.get('program_id') or '')})
        report = {
            'pack_id': str(pack_row.get('pack_id') or ''),
            'pack_token_count': int(pack_row.get('pack_token_count') or 0),
            'example_count': len(examples),
            'avg_example_quality': sum(quality_scores) / len(quality_scores),
            'min_example_quality': min(quality_scores),
            'distinct_repo_count': len(distinct_repos),
            'distinct_repos': distinct_repos[:64],
            'source_mix': _source_mix_for_pack(training_row),
            'role_counts': _role_counts_for_pack(training_row),
            'external_row_count': external_row_count,
            'fatal_reasons': [],
            'acceptance_mode': acceptance_mode,
            'training_signal_audit': signal_by_pack.get(str(pack_row.get('pack_id') or ''), {}),
        }
        if min_pack_tokens is not None:
            report['min_pack_tokens_reference'] = int(min_pack_tokens)
        reports.append(report)
    return reports


def _summary_from_reports(
    *,
    packs: list[dict[str, Any]],
    training_rows: list[dict[str, Any]],
    reports: list[dict[str, Any]],
    signal_summary: dict[str, Any],
    examples_path: Path,
    acceptance_mode: str,
    config_summary: dict[str, Any],
) -> dict[str, Any]:
    pack_token_counts = [int(row.get('pack_token_count') or 0) for row in reports]
    merged_example_count = sum(len(row.get('example_ids') or []) for row in packs)
    unique_chunks = {str(item.get('chunk_id') or '') for row in training_rows for item in row.get('context_rows', []) if isinstance(item, dict) and str(item.get('chunk_id') or '')}
    summary = {
        'allow_example_reuse': False,
        'avg_pack_example_quality': (sum(float(row.get('avg_example_quality') or 0.0) for row in reports) / len(reports)) if reports else 0.0,
        'avg_pack_token_count': (sum(pack_token_counts) / len(pack_token_counts)) if pack_token_counts else 0.0,
        'chunk_source_mode': 'direct_context_rows',
        'duplicate_pack_count': 0,
        'family_key_field': str(config_summary.get('family_key_field') or 'program_id'),
        'filtered_example_count': merged_example_count,
        'input_example_count': merged_example_count,
        'max_pack_token_count': max(pack_token_counts, default=0),
        'max_packs': len(packs),
        'min_avg_example_quality': config_summary.get('min_avg_example_quality'),
        'min_distinct_repos': config_summary.get('min_distinct_repos'),
        'min_example_quality': config_summary.get('min_example_quality'),
        'min_pack_token_count': min(pack_token_counts, default=0),
        'min_pack_tokens': config_summary.get('min_pack_tokens'),
        'min_verification_rows': config_summary.get('min_verification_rows'),
        'pack_count': len(packs),
        'pack_token_count_stats': {
            'avg': (sum(pack_token_counts) / len(pack_token_counts)) if pack_token_counts else 0.0,
            'max': max(pack_token_counts, default=0),
            'min': min(pack_token_counts, default=0),
        },
        'required_source_types': list(config_summary.get('require_source_types') or []),
        'target_pack_tokens': config_summary.get('target_pack_tokens'),
        'total_examples_consumed': merged_example_count,
        'total_unique_chunks_across_packs': len(unique_chunks),
        'training_row_count': len(training_rows),
        'training_signal_summary': signal_summary,
        'acceptance_mode': acceptance_mode,
        'examples_path': str(examples_path),
    }
    if acceptance_mode != 'strict_builder':
        summary['quality_gate_note'] = 'standard outputs backfilled from direct audit/manifests; not promoted beyond recorded acceptance mode'
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description='Backfill standard strict-pack outputs from audit inputs, examples, and audit/manifests.')
    parser.add_argument('--hardened-dir', type=Path, required=True)
    parser.add_argument('--examples', type=Path, required=True)
    parser.add_argument('--acceptance-mode', choices=['strict_builder', 'audit_only_direct'], required=True)
    parser.add_argument('--signal-summary-json', type=Path)
    parser.add_argument('--signal-pack-audit-jsonl', type=Path)
    parser.add_argument('--signal-target-audit-jsonl', type=Path)
    parser.add_argument('--rebuild-manifest-json', type=Path)
    parser.add_argument('--target-pack-tokens', type=int)
    parser.add_argument('--min-pack-tokens', type=int)
    parser.add_argument('--min-example-quality', type=float)
    parser.add_argument('--min-avg-example-quality', type=float)
    parser.add_argument('--min-distinct-repos', type=int)
    parser.add_argument('--min-verification-rows', type=int)
    parser.add_argument('--family-key-field', type=str, default='program_id')
    parser.add_argument('--require-source-types', nargs='*')
    args = parser.parse_args()

    hardened_dir = args.hardened_dir
    audit_input = hardened_dir / 'strict_long_context_pack_training_rows.audit_input.jsonl'
    if not audit_input.exists():
        raise ValueError(f'missing_audit_input:{audit_input}')

    training_rows = _load_jsonl(audit_input)
    packs = _pack_rows_from_training_rows(training_rows)
    pack_chunk_rows = _pack_chunk_rows_from_training_rows(training_rows)

    examples = _load_jsonl(args.examples)
    examples_by_id = {str(row.get('example_id') or ''): row for row in examples}

    signal_summary_path = args.signal_summary_json or (hardened_dir / 'strict_long_context_training_signal_summary.json')
    signal_pack_path = args.signal_pack_audit_jsonl or (hardened_dir / 'strict_long_context_training_signal_pack_audit.jsonl')
    signal_target_path = args.signal_target_audit_jsonl or (hardened_dir / 'strict_long_context_training_signal_target_audit.jsonl')
    if not signal_summary_path.exists() or not signal_pack_path.exists() or not signal_target_path.exists():
        raise ValueError('missing_signal_artifacts')

    signal_summary = _load_json(signal_summary_path)
    signal_pack_rows = _load_jsonl(signal_pack_path)
    signal_target_rows = _load_jsonl(signal_target_path)
    signal_by_pack = {str(row.get('pack_id') or ''): row for row in signal_pack_rows}

    config_summary: dict[str, Any] = {
        'family_key_field': args.family_key_field,
        'target_pack_tokens': args.target_pack_tokens,
        'min_pack_tokens': args.min_pack_tokens,
        'min_example_quality': args.min_example_quality,
        'min_avg_example_quality': args.min_avg_example_quality,
        'min_distinct_repos': args.min_distinct_repos,
        'min_verification_rows': args.min_verification_rows,
        'require_source_types': list(args.require_source_types or []),
    }
    rebuild_manifest_path = args.rebuild_manifest_json or (hardened_dir / 'rebuild_manifest.json')
    if rebuild_manifest_path.exists():
        rebuild_manifest = _load_json(rebuild_manifest_path)
        config = dict(rebuild_manifest.get('config') or {})
        for key, value in config.items():
            if value is not None:
                config_summary[key] = value

    reports = _quality_reports(
        packs=packs,
        training_rows=training_rows,
        examples_by_id=examples_by_id,
        signal_by_pack=signal_by_pack,
        acceptance_mode=args.acceptance_mode,
        min_pack_tokens=config_summary.get('min_pack_tokens'),
    )
    summary = _summary_from_reports(
        packs=packs,
        training_rows=training_rows,
        reports=reports,
        signal_summary=signal_summary,
        examples_path=args.examples,
        acceptance_mode=args.acceptance_mode,
        config_summary=config_summary,
    )

    write_jsonl(hardened_dir / 'strict_long_context_packs.jsonl', packs)
    write_jsonl(hardened_dir / 'strict_long_context_pack_training_rows.jsonl', training_rows)
    write_jsonl(hardened_dir / 'strict_long_context_pack_quality_reports.jsonl', reports)
    write_json(hardened_dir / 'strict_long_context_packs_summary.json', summary)
    write_jsonl(hardened_dir / 'strict_long_context_training_signal_pack_audit.jsonl', signal_pack_rows)
    write_jsonl(hardened_dir / 'strict_long_context_training_signal_target_audit.jsonl', signal_target_rows)
    write_json(hardened_dir / 'strict_long_context_training_signal_summary.json', signal_summary)
    write_parquet_shard(shard_path(hardened_dir / 'parquet', 'strict_long_context_packs', 0), packs)
    write_parquet_shard(shard_path(hardened_dir / 'parquet', 'strict_long_context_pack_chunks', 0), pack_chunk_rows)
    write_parquet_shard(shard_path(hardened_dir / 'parquet', 'strict_long_context_pack_training_rows', 0), training_rows)
    write_parquet_shard(shard_path(hardened_dir / 'parquet', 'strict_long_context_pack_quality_reports', 0), reports)


if __name__ == '__main__':
    main()
