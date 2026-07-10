from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

from long_context_common import write_json, write_jsonl


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _read_parquet_rows(directory: Path) -> list[dict[str, Any]]:
    import pyarrow.parquet as pq

    if not directory.is_dir():
        raise FileNotFoundError(f"missing_parquet_directory:{directory}")
    paths = sorted(directory.glob('*.parquet'))
    if not paths:
        raise FileNotFoundError(f"missing_parquet_files:{directory}")
    rows: list[dict[str, Any]] = []
    for path in paths:
        table = pq.read_table(path)
        columns = table.to_pydict()
        if not columns:
            continue
        row_count = len(next(iter(columns.values())))
        for index in range(row_count):
            row = {key: value[index] for key, value in columns.items()}
            rows.append(row)
    if not rows:
        raise ValueError(f"empty_parquet_rows:{directory}")
    return rows


def _iter_surface_rows(path: Path, *, storage_format: str) -> list[dict[str, Any]]:
    if storage_format == 'jsonl':
        if not path.is_file():
            raise FileNotFoundError(f"missing_jsonl_surface:{path}")
        rows = _read_jsonl(path)
    elif storage_format == 'parquet':
        rows = _read_parquet_rows(path)
    else:
        raise ValueError(f"unsupported_storage_format:{storage_format}")
    if not rows:
        raise ValueError(f"empty_surface_rows:{path}")
    return rows


def materialize_strict_long_context_mixture_rows(
    *,
    mixture_manifest_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    manifest_rows = _read_jsonl(mixture_manifest_path)
    if not manifest_rows:
        raise ValueError('empty_mixture_manifest')

    materialized_rows: list[dict[str, Any]] = []
    surface_cards: list[dict[str, Any]] = []
    seen_row_ids: set[str] = set()

    for manifest_row in manifest_rows:
        surface = str(manifest_row.get('surface') or '').strip()
        task_family = str(manifest_row.get('task_family') or '').strip()
        storage_format = str(manifest_row.get('storage_format') or '').strip()
        source_path = Path(str(manifest_row.get('path') or '').strip())
        expected_row_count = int(manifest_row.get('row_count') or 0)
        weight = float(manifest_row.get('weight') or 0.0)
        dataset_card_path = str(manifest_row.get('dataset_card_path') or '').strip()
        include_audit_only_direct = bool(manifest_row.get('include_audit_only_direct'))

        if not surface or not task_family or not storage_format or not str(source_path):
            raise ValueError(f'incomplete_mixture_manifest_row:{manifest_row}')
        if expected_row_count <= 0:
            raise ValueError(f'invalid_expected_row_count:{surface}:{expected_row_count}')
        if weight <= 0.0:
            raise ValueError(f'invalid_weight:{surface}:{weight}')

        source_rows = _iter_surface_rows(source_path, storage_format=storage_format)
        if len(source_rows) != expected_row_count:
            raise ValueError(f'row_count_mismatch:{surface}:expected={expected_row_count}:actual={len(source_rows)}')

        for row in source_rows:
            row_id = str(row.get('row_id') or '').strip()
            if not row_id:
                raise ValueError(f'missing_row_id:{surface}:{source_path}')
            mixture_row_id = f'{surface}::{row_id}'
            if mixture_row_id in seen_row_ids:
                raise ValueError(f'duplicate_mixture_row_id:{mixture_row_id}')
            seen_row_ids.add(mixture_row_id)
            row_copy = dict(row)
            row_copy['mixture_row_id'] = mixture_row_id
            row_copy['mixture_surface'] = surface
            row_copy['mixture_task_family'] = task_family
            row_copy['mixture_weight'] = weight
            row_copy['mixture_storage_format'] = storage_format
            row_copy['mixture_dataset_card_path'] = dataset_card_path
            row_copy['mixture_include_audit_only_direct'] = include_audit_only_direct
            materialized_rows.append(row_copy)

        surface_cards.append(
            {
                'surface': surface,
                'task_family': task_family,
                'storage_format': storage_format,
                'path': str(source_path),
                'expected_row_count': expected_row_count,
                'actual_row_count': len(source_rows),
                'weight': weight,
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    rows_path = output_dir / 'strict_long_context_mixture_rows.jsonl'
    card_path = output_dir / 'strict_long_context_mixture_rows_card.json'
    write_jsonl(rows_path, materialized_rows)
    card = {
        'mixture_manifest_path': str(mixture_manifest_path),
        'output_dir': str(output_dir),
        'row_count': len(materialized_rows),
        'surface_count': len(surface_cards),
        'surface_cards': surface_cards,
    }
    write_json(card_path, card)
    return {
        'rows_path': str(rows_path),
        'card_path': str(card_path),
        'row_count': len(materialized_rows),
        'surface_count': len(surface_cards),
        'surface_cards': surface_cards,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Materialize weighted strict long-context mixture rows from the canonical mixture manifest.')
    parser.add_argument('--mixture-manifest', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    materialize_strict_long_context_mixture_rows(
        mixture_manifest_path=args.mixture_manifest,
        output_dir=args.output_dir,
    )


if __name__ == '__main__':
    main()
