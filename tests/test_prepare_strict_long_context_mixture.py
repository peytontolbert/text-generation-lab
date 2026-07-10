from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from prepare_strict_long_context_mixture import build_strict_long_context_mixture_manifest  # noqa: E402


def test_build_strict_long_context_mixture_manifest_uses_dataset_card_parquet(tmp_path: Path) -> None:
    compiled_dir = tmp_path / 'compiled'
    compiled_dir.mkdir(parents=True, exist_ok=True)
    for name in ('full_context_rows', 'retrieval_rows', 'memory_rows'):
        (compiled_dir / f'{name}.jsonl').write_text('{}\n', encoding='utf-8')
        parquet_dir = compiled_dir / 'parquet' / name
        parquet_dir.mkdir(parents=True, exist_ok=True)
        (parquet_dir / f'{name}-000000.parquet').write_text('stub', encoding='utf-8')

    dataset_card = tmp_path / 'dataset_card.json'
    dataset_card.write_text(
        json.dumps(
            {
                'output_dir': str(compiled_dir),
                'include_audit_only_direct': False,
                'compiled_outputs': {
                    'full_context_rows_jsonl': str(compiled_dir / 'full_context_rows.jsonl'),
                    'retrieval_rows_jsonl': str(compiled_dir / 'retrieval_rows.jsonl'),
                    'memory_rows_jsonl': str(compiled_dir / 'memory_rows.jsonl'),
                    'compile_card_json': str(compiled_dir / 'compile_card.json'),
                },
                'compile_summary': {
                    'trainer_rows': 10,
                    'full_context_rows': 10,
                    'retrieval_rows': 25,
                    'memory_rows': 10,
                },
                'parquet_summary': {
                    'exports': {
                        'full_context_rows': {'output_dir': str(compiled_dir / 'parquet' / 'full_context_rows')},
                        'retrieval_rows': {'output_dir': str(compiled_dir / 'parquet' / 'retrieval_rows')},
                        'memory_rows': {'output_dir': str(compiled_dir / 'parquet' / 'memory_rows')},
                    }
                },
            },
            sort_keys=True,
        ),
        encoding='utf-8',
    )

    config = tmp_path / 'mixture_config.json'
    config.write_text(
        json.dumps(
            {
                'launcher_defaults': {
                    'output_dir': str(tmp_path / 'mixture_out'),
                    'storage_format': 'parquet',
                    'surfaces': [
                        {'name': 'full_context_rows', 'task_family': 'full_context_state_reconstruction', 'weight': 1.0},
                        {'name': 'retrieval_rows', 'task_family': 'retrieval_supervision', 'weight': 1.0},
                        {'name': 'memory_rows', 'task_family': 'state_summary_compression', 'weight': 0.5},
                    ],
                }
            },
            sort_keys=True,
        ),
        encoding='utf-8',
    )

    result = build_strict_long_context_mixture_manifest(
        dataset_card_path=dataset_card,
        config_path=config,
    )
    assert result['storage_format'] == 'parquet'
    assert [row['surface'] for row in result['rows']] == ['full_context_rows', 'retrieval_rows', 'memory_rows']
    assert result['rows'][0]['path'].endswith('/parquet/full_context_rows')
    assert result['rows'][2]['weight'] == 0.5
    assert Path(result['mixture_manifest_path']).is_file()


def test_build_strict_long_context_mixture_manifest_can_select_jsonl_surface_subset(tmp_path: Path) -> None:
    compiled_dir = tmp_path / 'compiled'
    compiled_dir.mkdir(parents=True, exist_ok=True)
    for name in ('full_context_rows', 'retrieval_rows', 'memory_rows'):
        (compiled_dir / f'{name}.jsonl').write_text('{}\n', encoding='utf-8')

    dataset_card = tmp_path / 'dataset_card.json'
    dataset_card.write_text(
        json.dumps(
            {
                'output_dir': str(compiled_dir),
                'include_audit_only_direct': False,
                'compiled_outputs': {
                    'full_context_rows_jsonl': str(compiled_dir / 'full_context_rows.jsonl'),
                    'retrieval_rows_jsonl': str(compiled_dir / 'retrieval_rows.jsonl'),
                    'memory_rows_jsonl': str(compiled_dir / 'memory_rows.jsonl'),
                    'compile_card_json': str(compiled_dir / 'compile_card.json'),
                },
                'compile_summary': {
                    'trainer_rows': 10,
                    'full_context_rows': 10,
                    'retrieval_rows': 25,
                    'memory_rows': 10,
                },
            },
            sort_keys=True,
        ),
        encoding='utf-8',
    )

    config = tmp_path / 'mixture_config.json'
    config.write_text(
        json.dumps(
            {
                'launcher_defaults': {
                    'output_dir': str(tmp_path / 'mixture_out'),
                    'storage_format': 'jsonl',
                    'surfaces': [
                        {'name': 'full_context_rows', 'task_family': 'full_context_state_reconstruction', 'weight': 1.0},
                        {'name': 'retrieval_rows', 'task_family': 'retrieval_supervision', 'weight': 1.0},
                        {'name': 'memory_rows', 'task_family': 'state_summary_compression', 'weight': 0.5},
                    ],
                }
            },
            sort_keys=True,
        ),
        encoding='utf-8',
    )

    result = build_strict_long_context_mixture_manifest(
        dataset_card_path=dataset_card,
        config_path=config,
        surfaces=['retrieval_rows'],
    )
    assert result['storage_format'] == 'jsonl'
    assert len(result['rows']) == 1
    assert result['rows'][0]['surface'] == 'retrieval_rows'
    assert result['rows'][0]['path'].endswith('/retrieval_rows.jsonl')
