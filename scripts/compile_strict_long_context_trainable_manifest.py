from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from long_context_common import write_json


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def _artifact_card(base: Path) -> dict[str, Any]:
    return {
        'base_dir': str(base),
        'summary_json': str(base / 'strict_long_context_packs_summary.json'),
        'signal_summary_json': str(base / 'strict_long_context_training_signal_summary.json'),
        'packs_jsonl': str(base / 'strict_long_context_packs.jsonl'),
        'training_rows_jsonl': str(base / 'strict_long_context_pack_training_rows.jsonl'),
        'quality_reports_jsonl': str(base / 'strict_long_context_pack_quality_reports.jsonl'),
        'pack_audit_jsonl': str(base / 'strict_long_context_training_signal_pack_audit.jsonl'),
        'target_audit_jsonl': str(base / 'strict_long_context_training_signal_target_audit.jsonl'),
        'packs_parquet': str(base / 'parquet' / 'strict_long_context_packs-000000.parquet'),
        'training_rows_parquet': str(base / 'parquet' / 'strict_long_context_pack_training_rows-000000.parquet'),
        'quality_reports_parquet': str(base / 'parquet' / 'strict_long_context_pack_quality_reports-000000.parquet'),
    }


def _validate_required_outputs(card: dict[str, Any]) -> dict[str, bool]:
    return {key: Path(value).exists() for key, value in card.items() if key != 'base_dir'}


def build_manifest(*, acceptance_report: Path, output_path: Path, min_pack_tokens: int | None, include_audit_only: bool) -> dict[str, Any]:
    report = _load_json(acceptance_report)
    accepted_rows = [dict(row) for row in report.get('accepted_shards') or [] if isinstance(row, dict)]

    selected: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for row in accepted_rows:
        acceptance_mode = str(row.get('acceptance_mode') or '')
        pack_token_count = float(row.get('pack_token_count') or 0.0)
        if acceptance_mode == 'audit_only_direct' and not include_audit_only:
            excluded.append({'name': row.get('name'), 'reason': 'audit_only_direct_excluded'})
            continue
        if min_pack_tokens is not None and pack_token_count < float(min_pack_tokens):
            excluded.append({'name': row.get('name'), 'reason': f'pack_token_count_below_floor:{min_pack_tokens}'})
            continue
        base = Path(str(row['path']))
        artifacts = _artifact_card(base)
        exists = _validate_required_outputs(artifacts)
        missing_required = sorted(key for key, present in exists.items() if not present)
        selected.append({
            'name': str(row.get('name') or ''),
            'path': str(base),
            'pack_token_count': pack_token_count,
            'target_audit_count': int(row.get('target_audit_count') or 0),
            'artifact_status': str(row.get('artifact_status') or ''),
            'acceptance_mode': acceptance_mode,
            'notes': str(row.get('notes') or ''),
            'artifacts': artifacts,
            'artifact_presence': exists,
            'missing_required_outputs': missing_required,
            'ready_for_training': not missing_required,
        })

    selected.sort(key=lambda row: (-float(row.get('pack_token_count') or 0.0), str(row.get('name') or '')))
    manifest = {
        'manifest_version': 1,
        'source_acceptance_report': str(acceptance_report),
        'include_audit_only_direct': bool(include_audit_only),
        'min_pack_tokens_filter': min_pack_tokens,
        'selected_shard_count': len(selected),
        'training_ready_shard_count': sum(1 for row in selected if bool(row.get('ready_for_training'))),
        'strict_builder_shard_count': sum(1 for row in selected if str(row.get('acceptance_mode') or '') == 'strict_builder'),
        'audit_only_direct_shard_count': sum(1 for row in selected if str(row.get('acceptance_mode') or '') == 'audit_only_direct'),
        'excluded': excluded,
        'selected_shards': selected,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(output_path, manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description='Compile a trainable strict long-context shard manifest from the hardened acceptance report.')
    parser.add_argument('--acceptance-report', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--min-pack-tokens', type=int)
    parser.add_argument('--include-audit-only-direct', action='store_true')
    args = parser.parse_args()
    manifest = build_manifest(
        acceptance_report=args.acceptance_report,
        output_path=args.output,
        min_pack_tokens=args.min_pack_tokens,
        include_audit_only=args.include_audit_only_direct,
    )
    print(json.dumps({
        'selected_shard_count': manifest['selected_shard_count'],
        'training_ready_shard_count': manifest['training_ready_shard_count'],
        'strict_builder_shard_count': manifest['strict_builder_shard_count'],
        'audit_only_direct_shard_count': manifest['audit_only_direct_shard_count'],
        'output': str(args.output),
    }, indent=2))


if __name__ == '__main__':
    main()
