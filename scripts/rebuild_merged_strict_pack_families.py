from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from build_strict_long_context_episode_packs import build_strict_long_context_episode_packs
from long_context_common import read_jsonl, write_json, write_jsonl
from long_context_parquet import shard_path, write_parquet_shard


def _infer_target_pack_tokens(name: str) -> int:
    lowered = name.lower()
    if '10m' in lowered:
        return 10_000_000
    if '8m' in lowered:
        return 8_500_000
    if '5m' in lowered:
        return 5_000_000
    if '4m' in lowered:
        return 4_500_000
    if '2m' in lowered:
        return 2_000_000
    raise ValueError(f'unable_to_infer_target_pack_tokens:{name}')


def _infer_min_pack_tokens(name: str, *, target_pack_tokens: int) -> int:
    lowered = name.lower()
    if 'floor1m' in lowered:
        return 1_000_000
    if 'relaxed' in lowered and target_pack_tokens >= 5_000_000:
        return 4_000_000
    if '4m' in lowered:
        return 3_500_000
    if '2m' in lowered:
        return 1_000_000
    if target_pack_tokens >= 8_000_000:
        return target_pack_tokens - 500_000
    return max(1_000_000, target_pack_tokens - 500_000)


def _load_existing_summary(family_dir: Path) -> dict[str, Any] | None:
    path = family_dir / 'strict_long_context_packs_summary.json'
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding='utf-8'))


def _example_source_types(examples_path: Path) -> list[str]:
    source_types: set[str] = set()
    for row in read_jsonl(examples_path):
        for context_row in row.get('context_rows', []) or []:
            if not isinstance(context_row, dict):
                continue
            value = str(context_row.get('source_type') or '').strip()
            if value:
                source_types.add(value)
    if not source_types:
        raise ValueError(f'no_source_types_detected:{examples_path}')
    return sorted(source_types)


def _family_config(family_dir: Path) -> dict[str, Any]:
    summary = _load_existing_summary(family_dir)
    examples_path = family_dir / '_merged_filtered_examples.jsonl'
    if not examples_path.exists():
        raise ValueError(f'missing_examples:{examples_path}')
    observed_source_types = _example_source_types(examples_path)
    name = family_dir.name

    target_pack_tokens = int(summary.get('target_pack_tokens')) if summary and summary.get('target_pack_tokens') is not None else _infer_target_pack_tokens(name)
    min_pack_tokens = int(summary.get('min_pack_tokens')) if summary and summary.get('min_pack_tokens') is not None else _infer_min_pack_tokens(name, target_pack_tokens=target_pack_tokens)
    min_example_quality = float(summary.get('min_example_quality')) if summary and summary.get('min_example_quality') is not None else 0.94
    min_avg_example_quality = float(summary.get('min_avg_example_quality')) if summary and summary.get('min_avg_example_quality') is not None else 0.96
    min_distinct_repos = int(summary.get('min_distinct_repos')) if summary and summary.get('min_distinct_repos') is not None else (1 if 'agentkernel_tail_2m' in name else 8)
    min_verification_rows = int(summary.get('min_verification_rows')) if summary and summary.get('min_verification_rows') is not None else 4
    family_key_field = str(summary.get('family_key_field') or 'program_id') if summary else 'program_id'

    if 'familyfiltered_tuned' in name:
        min_example_quality = max(min_example_quality, 0.94)
        min_avg_example_quality = max(min_avg_example_quality, 0.97)
        min_distinct_repos = max(min_distinct_repos, 20)
    if 'plus_current_recent96' in name:
        min_example_quality = max(min_example_quality, 0.94)
        min_avg_example_quality = max(min_avg_example_quality, 0.96)
        min_distinct_repos = max(min_distinct_repos, 20)
    if '8m' in name:
        min_example_quality = max(min_example_quality, 0.95)
        min_avg_example_quality = max(min_avg_example_quality, 0.97)
        min_distinct_repos = max(min_distinct_repos, 70)
    if '10m' in name:
        min_example_quality = max(min_example_quality, 0.95)
        min_avg_example_quality = max(min_avg_example_quality, 0.97)
        min_distinct_repos = max(min_distinct_repos, 70)

    return {
        'examples_path': examples_path,
        'target_pack_tokens': target_pack_tokens,
        'min_pack_tokens': min_pack_tokens,
        'min_example_quality': min_example_quality,
        'min_avg_example_quality': min_avg_example_quality,
        'min_distinct_repos': min_distinct_repos,
        'require_source_types': observed_source_types,
        'min_verification_rows': min_verification_rows,
        'family_key_field': family_key_field,
    }


def rebuild_family(family_dir: Path, *, force: bool) -> dict[str, Any]:
    hardened_dir = family_dir.parent / f'{family_dir.name}_hardened_v2'
    if hardened_dir.exists() and not force:
        signal_path = hardened_dir / 'strict_long_context_training_signal_summary.json'
        accepted = None
        if signal_path.exists():
            accepted = int(json.loads(signal_path.read_text(encoding='utf-8')).get('accepted_pack_count', 0))
        return {
            'family_dir': str(family_dir),
            'output_dir': str(hardened_dir),
            'status': 'skipped_existing',
            'accepted_pack_count': accepted,
        }

    config = _family_config(family_dir)
    packs, pack_chunk_rows, training_rows, reports, summary = build_strict_long_context_episode_packs(
        example_paths=[config['examples_path']],
        output_dir=hardened_dir,
        target_pack_tokens=int(config['target_pack_tokens']),
        min_pack_tokens=int(config['min_pack_tokens']),
        family_key_field=str(config['family_key_field']),
        max_packs=1,
        min_example_quality=float(config['min_example_quality']),
        min_avg_example_quality=float(config['min_avg_example_quality']),
        min_distinct_repos=int(config['min_distinct_repos']),
        require_source_types=set(config['require_source_types']),
        min_verification_rows=int(config['min_verification_rows']),
        min_locality_ready_fraction=0.60,
        min_retrieval_ready_fraction=0.55,
        min_long_range_join_ready_fraction=0.40,
        min_state_update_ready_fraction=0.80,
        min_target_rows_for_lost_state_probe=32,
        min_programs_for_lost_state_probe=8,
    )
    write_jsonl(hardened_dir / 'strict_long_context_packs.jsonl', packs)
    write_jsonl(hardened_dir / 'strict_long_context_pack_training_rows.jsonl', training_rows)
    write_jsonl(hardened_dir / 'strict_long_context_pack_quality_reports.jsonl', reports)
    write_json(hardened_dir / 'strict_long_context_packs_summary.json', summary)
    write_parquet_shard(shard_path(hardened_dir / 'parquet', 'strict_long_context_packs', 0), packs)
    write_parquet_shard(shard_path(hardened_dir / 'parquet', 'strict_long_context_pack_chunks', 0), pack_chunk_rows)
    write_parquet_shard(shard_path(hardened_dir / 'parquet', 'strict_long_context_pack_training_rows', 0), training_rows)
    write_parquet_shard(shard_path(hardened_dir / 'parquet', 'strict_long_context_pack_quality_reports', 0), reports)
    write_json(hardened_dir / 'rebuild_manifest.json', {
        'family_dir': str(family_dir),
        'output_dir': str(hardened_dir),
        'config': {
            **config,
            'examples_path': str(config['examples_path']),
        },
        'pack_count': len(packs),
        'training_row_count': len(training_rows),
        'quality_report_count': len(reports),
        'summary': summary,
    })
    return {
        'family_dir': str(family_dir),
        'output_dir': str(hardened_dir),
        'status': 'rebuilt',
        'accepted_pack_count': int((summary.get('training_signal_summary') or {}).get('accepted_pack_count', 0)),
        'pack_token_count': float(summary.get('avg_pack_token_count') or 0.0),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description='Rebuild preserved merged strict-pack families with the current hardened strict builder.')
    parser.add_argument('--base-dir', type=Path, default=Path('runs/local/artifacts/merged_packable_examples'))
    parser.add_argument('--family', action='append', default=[])
    parser.add_argument('--match', action='append', default=[])
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--report-path', type=Path)
    args = parser.parse_args()

    family_filters = {item for item in args.family if item}
    match_filters = [item for item in args.match if item]

    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for family_dir in sorted(args.base_dir.glob('*strict_packs*')):
        if family_dir.name.endswith('_hardened_v2'):
            continue
        if not (family_dir / '_merged_filtered_examples.jsonl').exists():
            continue
        if family_filters and family_dir.name not in family_filters:
            continue
        if match_filters and not any(token in family_dir.name for token in match_filters):
            continue
        try:
            rows.append(rebuild_family(family_dir, force=args.force))
        except Exception as exc:
            failures.append({
                'family_dir': str(family_dir),
                'status': 'failed',
                'error': str(exc),
            })
    report = {
        'rebuilt': rows,
        'failures': failures,
        'rebuilt_count': sum(1 for row in rows if row.get('status') == 'rebuilt'),
        'accepted_count': sum(1 for row in rows if int(row.get('accepted_pack_count') or 0) > 0),
        'failure_count': len(failures),
    }
    if args.report_path:
        write_json(args.report_path, report)
    else:
        print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
