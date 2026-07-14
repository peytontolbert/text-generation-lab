from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from prepare_strict_long_context_training_dataset import prepare_strict_long_context_training_dataset  # noqa: E402


def _write_training_rows(path: Path, *, pack_id: str, chunk_id: str, state_variable: str, source_id: str | None = None) -> None:
    resolved_source_id = source_id or pack_id
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
                'source_id': resolved_source_id,
                'source_type': 'repo',
                'path': f'src/{pack_id}.py',
                'text': f'{state_variable} is true',
            },
            {
                'chunk_id': f'{chunk_id}::test',
                'chunk_ordinal': 2,
                'source_id': f'{resolved_source_id}_test',
                'source_type': 'test',
                'path': f'tests/test_{pack_id}.py',
                'text': f'assert {state_variable}',
            },
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
        'chunk_count': 2,
        'candidate_count': 1,
    }
    path.write_text(json.dumps(row, sort_keys=True) + '\n', encoding='utf-8')


def _write_pack_audit(path: Path, *, pack_id: str, accepted: bool, state_delta_ready_fraction: float, evidence_anchor_ready_fraction: float) -> None:
    row = {
        'pack_id': pack_id,
        'accepted': accepted,
        'state_delta_ready_fraction': state_delta_ready_fraction,
        'evidence_anchor_ready_fraction': evidence_anchor_ready_fraction,
    }
    path.write_text(json.dumps(row, sort_keys=True) + '\n', encoding='utf-8')


def test_prepare_strict_long_context_training_dataset_defaults_to_conservative_manifest(tmp_path: Path) -> None:
    strict_rows = tmp_path / 'strict_rows.jsonl'
    strict_rows_b = tmp_path / 'strict_rows_b.jsonl'
    strict_rows_c = tmp_path / 'strict_rows_c.jsonl'
    audit_rows = tmp_path / 'audit_rows.jsonl'
    strict_audit = tmp_path / 'strict_audit.jsonl'
    strict_audit_b = tmp_path / 'strict_audit_b.jsonl'
    strict_audit_c = tmp_path / 'strict_audit_c.jsonl'
    audit_only_pack_audit = tmp_path / 'audit_only_pack_audit.jsonl'
    _write_training_rows(strict_rows, pack_id='strict-pack-a', chunk_id='strict-c1', state_variable='strict_state_a')
    _write_training_rows(strict_rows_b, pack_id='strict-pack-b', chunk_id='strict-c2', state_variable='strict_state_b')
    _write_training_rows(strict_rows_c, pack_id='strict-pack-c', chunk_id='strict-c3', state_variable='strict_state_c')
    _write_training_rows(audit_rows, pack_id='audit-pack', chunk_id='audit-c1', state_variable='audit_state')
    _write_pack_audit(strict_audit, pack_id='strict-pack-a', accepted=True, state_delta_ready_fraction=0.9, evidence_anchor_ready_fraction=0.8)
    _write_pack_audit(strict_audit_b, pack_id='strict-pack-b', accepted=True, state_delta_ready_fraction=0.8, evidence_anchor_ready_fraction=0.9)
    _write_pack_audit(strict_audit_c, pack_id='strict-pack-c', accepted=True, state_delta_ready_fraction=1.0, evidence_anchor_ready_fraction=0.85)
    _write_pack_audit(audit_only_pack_audit, pack_id='audit-pack', accepted=True, state_delta_ready_fraction=0.5, evidence_anchor_ready_fraction=0.4)

    manifest = tmp_path / 'strict_manifest.json'
    manifest.write_text(
        json.dumps(
            {
                'selected_shards': [
                    {
                        'name': 'strict_shard_a',
                        'acceptance_mode': 'strict_builder',
                        'ready_for_training': True,
                        'artifacts': {'training_rows_jsonl': str(strict_rows), 'pack_audit_jsonl': str(strict_audit)},
                    },
                    {
                        'name': 'strict_shard_b',
                        'acceptance_mode': 'strict_builder',
                        'ready_for_training': True,
                        'artifacts': {'training_rows_jsonl': str(strict_rows_b), 'pack_audit_jsonl': str(strict_audit_b)},
                    },
                    {
                        'name': 'strict_shard_c',
                        'acceptance_mode': 'strict_builder',
                        'ready_for_training': True,
                        'artifacts': {'training_rows_jsonl': str(strict_rows_c), 'pack_audit_jsonl': str(strict_audit_c)},
                    },
                    {
                        'name': 'audit_shard',
                        'acceptance_mode': 'audit_only_direct',
                        'ready_for_training': True,
                        'artifacts': {'training_rows_jsonl': str(audit_rows), 'pack_audit_jsonl': str(audit_only_pack_audit)},
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
                    'prepare_split_pipeline': False,
                    'mixture_output_dir': str(tmp_path / 'mixture_default'),
                    'mixture_rows_output_dir': str(tmp_path / 'mixture_rows_default'),
                    'split_output_dir': str(tmp_path / 'split_default'),
                    'sampled_output_dir': str(tmp_path / 'sampled_default'),
                    'split_audit_output_path': str(tmp_path / 'sampled_default' / 'strict_long_context_split_quality_audit.json'),
                    'min_state_delta_ready_fraction': 0.8,
                    'min_evidence_anchor_ready_fraction': 0.8,
                }
            },
            sort_keys=True,
        ),
        encoding='utf-8',
    )

    result = prepare_strict_long_context_training_dataset(config_path=config)
    assert result['include_audit_only_direct'] is False
    assert result['compile_summary']['trainer_rows'] == 3
    assert result['compile_summary']['source_summary']['included_shards'] == ['strict_shard_a', 'strict_shard_b', 'strict_shard_c']
    assert result['compile_summary']['source_summary']['excluded_shards'] == [
        {'name': 'audit_shard', 'reason': 'audit_only_direct_excluded'}
    ]
    assert result['shard_filter_summary']['included_shards'] == ['strict_shard_a', 'strict_shard_b', 'strict_shard_c', 'audit_shard']
    assert result['shard_filter_summary']['excluded_shards'] == []
    assert result['parquet_summary'] is not None
    assert result['train_ready_audit_summary']['avg_state_delta_ready_fraction'] == 0.9
    assert round(result['train_ready_audit_summary']['avg_evidence_anchor_ready_fraction'], 6) == 0.85
    assert result['train_ready_audit_summary']['min_state_delta_ready_fraction'] == 0.8
    assert result['train_ready_audit_summary']['min_evidence_anchor_ready_fraction'] == 0.8
    assert result['split_pipeline'] is None
    assert Path(result['compiled_outputs']['full_context_rows_jsonl']).is_file()
    assert Path(result['compiled_outputs']['compile_card_json']).is_file()
    assert Path(result['output_dir'], 'strict_long_context_training_dataset_card.json').is_file()


def test_prepare_strict_long_context_training_dataset_can_include_audit_only_direct(tmp_path: Path) -> None:
    strict_rows = tmp_path / 'strict_rows.jsonl'
    strict_rows_b = tmp_path / 'strict_rows_b.jsonl'
    strict_rows_c = tmp_path / 'strict_rows_c.jsonl'
    audit_rows = tmp_path / 'audit_rows.jsonl'
    strict_audit = tmp_path / 'strict_audit.jsonl'
    strict_audit_b = tmp_path / 'strict_audit_b.jsonl'
    strict_audit_c = tmp_path / 'strict_audit_c.jsonl'
    audit_only_pack_audit = tmp_path / 'audit_only_pack_audit.jsonl'
    _write_training_rows(strict_rows, pack_id='strict-pack-a', chunk_id='strict-c1', state_variable='strict_state_a')
    _write_training_rows(strict_rows_b, pack_id='strict-pack-b', chunk_id='strict-c2', state_variable='strict_state_b')
    _write_training_rows(strict_rows_c, pack_id='strict-pack-c', chunk_id='strict-c3', state_variable='strict_state_c')
    _write_training_rows(audit_rows, pack_id='audit-pack', chunk_id='audit-c1', state_variable='audit_state')
    _write_pack_audit(strict_audit, pack_id='strict-pack-a', accepted=True, state_delta_ready_fraction=0.9, evidence_anchor_ready_fraction=0.8)
    _write_pack_audit(strict_audit_b, pack_id='strict-pack-b', accepted=True, state_delta_ready_fraction=0.8, evidence_anchor_ready_fraction=0.9)
    _write_pack_audit(strict_audit_c, pack_id='strict-pack-c', accepted=True, state_delta_ready_fraction=1.0, evidence_anchor_ready_fraction=0.85)
    _write_pack_audit(audit_only_pack_audit, pack_id='audit-pack', accepted=True, state_delta_ready_fraction=0.5, evidence_anchor_ready_fraction=0.4)

    manifest = tmp_path / 'strict_manifest.json'
    manifest.write_text(
        json.dumps(
            {
                'selected_shards': [
                    {
                        'name': 'strict_shard_a',
                        'acceptance_mode': 'strict_builder',
                        'ready_for_training': True,
                        'artifacts': {'training_rows_jsonl': str(strict_rows), 'pack_audit_jsonl': str(strict_audit)},
                    },
                    {
                        'name': 'strict_shard_b',
                        'acceptance_mode': 'strict_builder',
                        'ready_for_training': True,
                        'artifacts': {'training_rows_jsonl': str(strict_rows_b), 'pack_audit_jsonl': str(strict_audit_b)},
                    },
                    {
                        'name': 'strict_shard_c',
                        'acceptance_mode': 'strict_builder',
                        'ready_for_training': True,
                        'artifacts': {'training_rows_jsonl': str(strict_rows_c), 'pack_audit_jsonl': str(strict_audit_c)},
                    },
                    {
                        'name': 'audit_shard',
                        'acceptance_mode': 'audit_only_direct',
                        'ready_for_training': True,
                        'artifacts': {'training_rows_jsonl': str(audit_rows), 'pack_audit_jsonl': str(audit_only_pack_audit)},
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
                    'export_parquet': True,
                    'parquet_output_dir': str(tmp_path / 'compiled_with_audit' / 'parquet'),
                    'max_positive_chunks': 4,
                    'rows_per_shard': 100,
                    'compression': 'zstd',
                    'prepare_split_pipeline': False,
                    'mixture_output_dir': str(tmp_path / 'mixture_with_audit'),
                    'mixture_rows_output_dir': str(tmp_path / 'mixture_rows_with_audit'),
                    'split_output_dir': str(tmp_path / 'split_with_audit'),
                    'sampled_output_dir': str(tmp_path / 'sampled_with_audit'),
                    'split_audit_output_path': str(tmp_path / 'sampled_with_audit' / 'strict_long_context_split_quality_audit.json'),
                    'min_state_delta_ready_fraction': 0.0,
                    'min_evidence_anchor_ready_fraction': 0.0,
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
    assert result['train_ready_audit_summary']['included_shard_count'] == 4
    assert result['compile_summary']['trainer_rows'] == 4
    assert result['compile_summary']['source_summary']['included_shards'] == ['strict_shard_a', 'strict_shard_b', 'strict_shard_c', 'audit_shard']
    assert result['compile_summary']['source_summary']['excluded_shards'] == []
    assert result['shard_filter_summary']['excluded_shards'] == []
    assert result['parquet_summary'] is not None
    assert result['split_pipeline'] is None


def test_prepare_strict_long_context_training_dataset_split_pipeline_records_audit_output_path(tmp_path: Path) -> None:
    strict_rows = tmp_path / 'strict_rows.jsonl'
    strict_rows_b = tmp_path / 'strict_rows_b.jsonl'
    strict_rows_c = tmp_path / 'strict_rows_c.jsonl'
    strict_audit = tmp_path / 'strict_audit.jsonl'
    strict_audit_b = tmp_path / 'strict_audit_b.jsonl'
    strict_audit_c = tmp_path / 'strict_audit_c.jsonl'
    _write_training_rows(strict_rows, pack_id='strict-pack-a', chunk_id='strict-c1', state_variable='strict_state_a', source_id='repo_a')
    _write_training_rows(strict_rows_b, pack_id='strict-pack-b', chunk_id='strict-c2', state_variable='strict_state_b', source_id='repo_b')
    _write_training_rows(strict_rows_c, pack_id='strict-pack-c', chunk_id='strict-c3', state_variable='strict_state_c', source_id='repo_c')
    _write_pack_audit(strict_audit, pack_id='strict-pack-a', accepted=True, state_delta_ready_fraction=1.0, evidence_anchor_ready_fraction=1.0)
    _write_pack_audit(strict_audit_b, pack_id='strict-pack-b', accepted=True, state_delta_ready_fraction=1.0, evidence_anchor_ready_fraction=1.0)
    _write_pack_audit(strict_audit_c, pack_id='strict-pack-c', accepted=True, state_delta_ready_fraction=1.0, evidence_anchor_ready_fraction=1.0)

    manifest = tmp_path / 'strict_manifest.json'
    manifest.write_text(
        json.dumps(
            {
                'selected_shards': [
                    {
                        'name': 'strict_shard_a',
                        'acceptance_mode': 'strict_builder',
                        'ready_for_training': True,
                        'artifacts': {'training_rows_jsonl': str(strict_rows), 'pack_audit_jsonl': str(strict_audit)},
                    },
                    {
                        'name': 'strict_shard_b',
                        'acceptance_mode': 'strict_builder',
                        'ready_for_training': True,
                        'artifacts': {'training_rows_jsonl': str(strict_rows_b), 'pack_audit_jsonl': str(strict_audit_b)},
                    },
                    {
                        'name': 'strict_shard_c',
                        'acceptance_mode': 'strict_builder',
                        'ready_for_training': True,
                        'artifacts': {'training_rows_jsonl': str(strict_rows_c), 'pack_audit_jsonl': str(strict_audit_c)},
                    }
                ]
            },
            sort_keys=True,
        ),
        encoding='utf-8',
    )

    config = tmp_path / 'entrypoint_config_split.json'
    split_audit_output = tmp_path / 'sampled_split' / 'strict_long_context_split_quality_audit.json'
    config.write_text(
        json.dumps(
            {
                'dataset_defaults': {
                    'strict_shard_manifest': str(manifest),
                    'include_audit_only_direct': False,
                    'output_dir': str(tmp_path / 'compiled_split'),
                    'export_parquet': True,
                    'parquet_output_dir': str(tmp_path / 'compiled_split' / 'parquet'),
                    'max_positive_chunks': 4,
                    'rows_per_shard': 100,
                    'compression': 'zstd',
                    'prepare_split_pipeline': True,
                    'mixture_output_dir': str(tmp_path / 'mixture_split'),
                    'mixture_rows_output_dir': str(tmp_path / 'mixture_rows_split'),
                    'split_output_dir': str(tmp_path / 'split_rows_split'),
                    'sampled_output_dir': str(tmp_path / 'sampled_split'),
                    'split_audit_output_path': str(split_audit_output),
                    'min_state_delta_ready_fraction': 0.8,
                    'min_evidence_anchor_ready_fraction': 0.8,
                }
            },
            sort_keys=True,
        ),
        encoding='utf-8',
    )

    result = prepare_strict_long_context_training_dataset(config_path=config)
    assert result['split_pipeline'] is not None
    assert result['split_pipeline']['audit']['output_path'] == str(split_audit_output)
    assert Path(result['split_pipeline']['audit']['output_path']).is_file()
