from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from prepare_strict_long_context_training_dataset import prepare_strict_long_context_training_dataset  # noqa: E402


def _write_training_rows(path: Path, *, pack_id: str, chunk_id: str, state_variable: str) -> None:
    row = {
        'pack_id': pack_id,
        'effective_split': 'train',
        'trainer_policy_mode': 'family_cluster_constrained_training',
        'overlap_family_id': f'cluster::{pack_id}',
        'prompt_text': f'Prompt for {pack_id}',
        'context_rows': [
            {
                'chunk_id': chunk_id,
                'chunk_ordinal': 1,
                'source_type': 'repo',
                'path': f'src/{pack_id}.py',
                'text': f'{state_variable} is true',
            }
        ],
        'target_rows': [
            {
                'query_index': 1,
                'candidate_id': f'cand::{pack_id}',
                'canonical_name': state_variable,
                'final_state': {state_variable: True},
                'state_variable': state_variable,
            }
        ],
        'pack_token_count': 128,
        'chunk_count': 1,
        'candidate_count': 1,
    }
    path.write_text(json.dumps(row, sort_keys=True) + '\n', encoding='utf-8')


def test_prepare_strict_long_context_training_dataset_defaults_to_conservative_manifest(tmp_path: Path) -> None:
    strict_rows = tmp_path / 'strict_rows.jsonl'
    audit_rows = tmp_path / 'audit_rows.jsonl'
    _write_training_rows(strict_rows, pack_id='strict-pack', chunk_id='strict-c1', state_variable='strict_state')
    _write_training_rows(audit_rows, pack_id='audit-pack', chunk_id='audit-c1', state_variable='audit_state')

    manifest = tmp_path / 'strict_manifest.json'
    manifest.write_text(
        json.dumps(
            {
                'selected_shards': [
                    {
                        'name': 'strict_shard',
                        'acceptance_mode': 'strict_builder',
                        'ready_for_training': True,
                        'artifacts': {'training_rows_jsonl': str(strict_rows)},
                    },
                    {
                        'name': 'audit_shard',
                        'acceptance_mode': 'audit_only_direct',
                        'ready_for_training': True,
                        'artifacts': {'training_rows_jsonl': str(audit_rows)},
                    },
                ]
            },
            sort_keys=True,
        ),
        encoding='utf-8',
    )

    config = tmp_path / 'entrypoint_config.json'
    config.write_text(
        json.dumps(
            {
                'dataset_defaults': {
                    'strict_shard_manifest': str(manifest),
                    'include_audit_only_direct': False,
                    'output_dir': str(tmp_path / 'compiled_default'),
                    'export_parquet': True,
                    'parquet_output_dir': str(tmp_path / 'compiled_default' / 'parquet'),
                    'max_positive_chunks': 4,
                    'rows_per_shard': 100,
                    'compression': 'zstd',
                }
            },
            sort_keys=True,
        ),
        encoding='utf-8',
    )

    result = prepare_strict_long_context_training_dataset(config_path=config)
    assert result['include_audit_only_direct'] is False
    assert result['compile_summary']['trainer_rows'] == 1
    assert result['compile_summary']['source_summary']['included_shards'] == ['strict_shard']
    assert result['compile_summary']['source_summary']['excluded_shards'] == [
        {'name': 'audit_shard', 'reason': 'audit_only_direct_excluded'}
    ]
    assert result['parquet_summary'] is not None
    assert Path(result['compiled_outputs']['full_context_rows_jsonl']).is_file()
    assert Path(result['compiled_outputs']['compile_card_json']).is_file()
    assert Path(result['output_dir'], 'strict_long_context_training_dataset_card.json').is_file()


def test_prepare_strict_long_context_training_dataset_can_include_audit_only_direct(tmp_path: Path) -> None:
    strict_rows = tmp_path / 'strict_rows.jsonl'
    audit_rows = tmp_path / 'audit_rows.jsonl'
    _write_training_rows(strict_rows, pack_id='strict-pack', chunk_id='strict-c1', state_variable='strict_state')
    _write_training_rows(audit_rows, pack_id='audit-pack', chunk_id='audit-c1', state_variable='audit_state')

    manifest = tmp_path / 'strict_manifest.json'
    manifest.write_text(
        json.dumps(
            {
                'selected_shards': [
                    {
                        'name': 'strict_shard',
                        'acceptance_mode': 'strict_builder',
                        'ready_for_training': True,
                        'artifacts': {'training_rows_jsonl': str(strict_rows)},
                    },
                    {
                        'name': 'audit_shard',
                        'acceptance_mode': 'audit_only_direct',
                        'ready_for_training': True,
                        'artifacts': {'training_rows_jsonl': str(audit_rows)},
                    },
                ]
            },
            sort_keys=True,
        ),
        encoding='utf-8',
    )

    config = tmp_path / 'entrypoint_config.json'
    config.write_text(
        json.dumps(
            {
                'dataset_defaults': {
                    'strict_shard_manifest': str(manifest),
                    'include_audit_only_direct': False,
                    'output_dir': str(tmp_path / 'compiled_with_audit'),
                    'export_parquet': False,
                    'max_positive_chunks': 4,
                    'rows_per_shard': 100,
                    'compression': 'zstd',
                }
            },
            sort_keys=True,
        ),
        encoding='utf-8',
    )

    result = prepare_strict_long_context_training_dataset(
        config_path=config,
        include_audit_only_direct=True,
    )
    assert result['include_audit_only_direct'] is True
    assert result['compile_summary']['trainer_rows'] == 2
    assert result['compile_summary']['source_summary']['included_shards'] == ['strict_shard', 'audit_shard']
    assert result['compile_summary']['source_summary']['excluded_shards'] == []
    assert result['parquet_summary'] is None
