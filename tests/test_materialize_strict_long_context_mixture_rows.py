from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from materialize_strict_long_context_mixture_rows import materialize_strict_long_context_mixture_rows  # noqa: E402
from long_context_parquet import write_parquet_shard  # noqa: E402


def test_materialize_strict_long_context_mixture_rows_from_jsonl(tmp_path: Path) -> None:
    full_path = tmp_path / 'full.jsonl'
    retrieval_path = tmp_path / 'retrieval.jsonl'
    full_path.write_text(json.dumps({'row_id': 'full::p1', 'task_type': 'full_context_state_reconstruction'}) + '\n', encoding='utf-8')
    retrieval_path.write_text(json.dumps({'row_id': 'retrieval::p1::1', 'task_type': 'retrieval_supervision'}) + '\n', encoding='utf-8')

    manifest = tmp_path / 'mixture.jsonl'
    manifest.write_text(
        '\n'.join(
            [
                json.dumps({
                    'surface': 'full_context_rows',
                    'task_family': 'full_context_state_reconstruction',
                    'storage_format': 'jsonl',
                    'path': str(full_path),
                    'row_count': 1,
                    'weight': 1.0,
                    'dataset_card_path': '/tmp/dataset_card.json',
                    'include_audit_only_direct': False,
                }, sort_keys=True),
                json.dumps({
                    'surface': 'retrieval_rows',
                    'task_family': 'retrieval_supervision',
                    'storage_format': 'jsonl',
                    'path': str(retrieval_path),
                    'row_count': 1,
                    'weight': 2.0,
                    'dataset_card_path': '/tmp/dataset_card.json',
                    'include_audit_only_direct': False,
                }, sort_keys=True),
            ]
        ) + '\n',
        encoding='utf-8',
    )

    result = materialize_strict_long_context_mixture_rows(
        mixture_manifest_path=manifest,
        output_dir=tmp_path / 'out',
    )
    rows = [json.loads(line) for line in Path(result['rows_path']).read_text(encoding='utf-8').splitlines() if line.strip()]
    assert result['row_count'] == 2
    assert rows[0]['mixture_surface'] == 'full_context_rows'
    assert rows[1]['mixture_surface'] == 'retrieval_rows'
    assert rows[1]['mixture_weight'] == 2.0
    assert rows[0]['mixture_row_id'] == 'full_context_rows::full::p1'


def test_materialize_strict_long_context_mixture_rows_from_parquet(tmp_path: Path) -> None:
    parquet_dir = tmp_path / 'full_context_rows'
    parquet_dir.mkdir(parents=True, exist_ok=True)
    write_parquet_shard(
        parquet_dir / 'full_context_rows-000000.parquet',
        [
            {'row_id': 'full::p1', 'task_type': 'full_context_state_reconstruction'},
            {'row_id': 'full::p2', 'task_type': 'full_context_state_reconstruction'},
        ],
    )

    manifest = tmp_path / 'mixture.jsonl'
    manifest.write_text(
        json.dumps({
            'surface': 'full_context_rows',
            'task_family': 'full_context_state_reconstruction',
            'storage_format': 'parquet',
            'path': str(parquet_dir),
            'row_count': 2,
            'weight': 1.0,
            'dataset_card_path': '/tmp/dataset_card.json',
            'include_audit_only_direct': False,
        }, sort_keys=True) + '\n',
        encoding='utf-8',
    )

    result = materialize_strict_long_context_mixture_rows(
        mixture_manifest_path=manifest,
        output_dir=tmp_path / 'out',
    )
    rows = [json.loads(line) for line in Path(result['rows_path']).read_text(encoding='utf-8').splitlines() if line.strip()]
    assert result['row_count'] == 2
    assert [row['mixture_row_id'] for row in rows] == [
        'full_context_rows::full::p1',
        'full_context_rows::full::p2',
    ]


def test_materialize_strict_long_context_mixture_rows_applies_manifest_quality_gate(tmp_path: Path) -> None:
    full_path = tmp_path / 'full.jsonl'
    retrieval_path = tmp_path / 'retrieval.jsonl'
    full_path.write_text(json.dumps({'row_id': 'full::p1', 'task_type': 'full_context_state_reconstruction'}) + '\n', encoding='utf-8')
    retrieval_path.write_text(json.dumps({'row_id': 'retrieval::p1::1', 'task_type': 'retrieval_supervision'}) + '\n', encoding='utf-8')

    manifest = tmp_path / 'mixture.jsonl'
    manifest.write_text(
        '\n'.join(
            [
                json.dumps({
                    'surface': 'full_context_rows',
                    'task_family': 'full_context_state_reconstruction',
                    'storage_format': 'jsonl',
                    'path': str(full_path),
                    'row_count': 1,
                    'weight': 1.0,
                    'dataset_card_path': '/tmp/dataset_card.json',
                    'include_audit_only_direct': False,
                    'min_state_delta_ready_fraction': 0.82,
                    'min_evidence_anchor_ready_fraction': 0.81,
                    'manifest_filter_expr': 'min_state_delta_ready_fraction>=0.8 and min_evidence_anchor_ready_fraction>=0.8',
                }, sort_keys=True),
                json.dumps({
                    'surface': 'retrieval_rows',
                    'task_family': 'retrieval_supervision',
                    'storage_format': 'jsonl',
                    'path': str(retrieval_path),
                    'row_count': 1,
                    'weight': 2.0,
                    'dataset_card_path': '/tmp/dataset_card.json',
                    'include_audit_only_direct': False,
                    'min_state_delta_ready_fraction': 0.75,
                    'min_evidence_anchor_ready_fraction': 0.9,
                    'manifest_filter_expr': 'min_state_delta_ready_fraction>=0.8 and min_evidence_anchor_ready_fraction>=0.8',
                }, sort_keys=True),
            ]
        ) + '\n',
        encoding='utf-8',
    )

    result = materialize_strict_long_context_mixture_rows(
        mixture_manifest_path=manifest,
        output_dir=tmp_path / 'out',
    )
    rows = [json.loads(line) for line in Path(result['rows_path']).read_text(encoding='utf-8').splitlines() if line.strip()]
    assert result['row_count'] == 1
    assert rows[0]['mixture_surface'] == 'full_context_rows'
    assert rows[0]['mixture_min_state_delta_ready_fraction'] == 0.82
    assert rows[0]['mixture_min_evidence_anchor_ready_fraction'] == 0.81
    assert result['surface_cards'][0]['manifest_accepted'] is True
    assert result['surface_cards'][1]['manifest_accepted'] is False
