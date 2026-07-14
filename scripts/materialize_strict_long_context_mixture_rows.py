from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from long_context_common import write_json, write_jsonl


COMPARISON_OPERATORS = ('>=', '<=', '!=', '==', '>', '<')


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


def _coerce_value(value: Any) -> Any:
    if isinstance(value, str):
        text = value.strip()
        lowered = text.lower()
        if lowered in {'true', 'false'}:
            return lowered == 'true'
        try:
            if '.' in text:
                return float(text)
            return int(text)
        except ValueError:
            return text
    return value


def _numeric_value(value: Any) -> float:
    coerced = _coerce_value(value)
    if isinstance(coerced, bool):
        return 1.0 if coerced else 0.0
    if isinstance(coerced, (int, float)):
        return float(coerced)
    raise ValueError(f'non_numeric_filter_value:{value}')


def _matches_clause(row: dict[str, Any], clause: str) -> bool:
    clause = clause.strip()
    if not clause:
        return True
    if ' contains ' in clause:
        key, expected = clause.split(' contains ', 1)
        actual = str(row.get(key.strip()) or '')
        return expected.strip() in actual
    for operator in COMPARISON_OPERATORS:
        if operator not in clause:
            continue
        key, expected = clause.split(operator, 1)
        actual = row.get(key.strip())
        expected_value = _coerce_value(expected.strip())
        actual_value = _coerce_value(actual)
        if operator == '==':
            return actual_value == expected_value
        if operator == '!=':
            return actual_value != expected_value
        if actual is None:
            return False
        actual_numeric = _numeric_value(actual_value)
        expected_numeric = _numeric_value(expected_value)
        if operator == '>=':
            return actual_numeric >= expected_numeric
        if operator == '<=':
            return actual_numeric <= expected_numeric
        if operator == '>':
            return actual_numeric > expected_numeric
        if operator == '<':
            return actual_numeric < expected_numeric
    raise ValueError(f'unsupported_filter_clause:{clause}')


def _matches_filter(row: dict[str, Any], filter_expr: str | None) -> bool:
    if not filter_expr:
        return True
    or_groups = [part.strip() for part in str(filter_expr).split(' or ') if part.strip()]
    if not or_groups:
        return True
    for group in or_groups:
        and_clauses = [part.strip() for part in group.split(' and ') if part.strip()]
        if and_clauses and all(_matches_clause(row, clause) for clause in and_clauses):
            return True
    return False


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
        filter_expr = str(manifest_row.get('filter_expr') or '').strip() or None
        manifest_filter_expr = str(manifest_row.get('manifest_filter_expr') or '').strip() or None
        state_delta_ready_fraction = float(manifest_row.get('state_delta_ready_fraction') or 0.0)
        evidence_anchor_ready_fraction = float(manifest_row.get('evidence_anchor_ready_fraction') or 0.0)
        min_state_delta_ready_fraction = float(manifest_row.get('min_state_delta_ready_fraction') or 0.0)
        min_evidence_anchor_ready_fraction = float(manifest_row.get('min_evidence_anchor_ready_fraction') or 0.0)

        if not surface or not task_family or not storage_format or not str(source_path):
            raise ValueError(f'incomplete_mixture_manifest_row:{manifest_row}')
        if expected_row_count <= 0:
            raise ValueError(f'invalid_expected_row_count:{surface}:{expected_row_count}')
        if weight <= 0.0:
            raise ValueError(f'invalid_weight:{surface}:{weight}')

        manifest_accepted = _matches_filter(manifest_row, manifest_filter_expr)
        if not manifest_accepted:
            surface_cards.append(
                {
                    'surface': surface,
                    'task_family': task_family,
                    'storage_format': storage_format,
                    'path': str(source_path),
                    'expected_row_count': expected_row_count,
                    'actual_row_count': 0,
                    'materialized_row_count': 0,
                    'weight': weight,
                    'filter_expr': filter_expr,
                    'manifest_filter_expr': manifest_filter_expr,
                    'manifest_accepted': False,
                    'state_delta_ready_fraction': state_delta_ready_fraction,
                    'evidence_anchor_ready_fraction': evidence_anchor_ready_fraction,
                    'min_state_delta_ready_fraction': min_state_delta_ready_fraction,
                    'min_evidence_anchor_ready_fraction': min_evidence_anchor_ready_fraction,
                }
            )
            continue

        source_rows = _iter_surface_rows(source_path, storage_format=storage_format)
        if len(source_rows) != expected_row_count:
            raise ValueError(f'row_count_mismatch:{surface}:expected={expected_row_count}:actual={len(source_rows)}')

        kept_rows = [row for row in source_rows if _matches_filter(row, filter_expr)]
        for row in kept_rows:
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
            row_copy['mixture_filter_expr'] = filter_expr
            row_copy['mixture_manifest_filter_expr'] = manifest_filter_expr
            row_copy['mixture_state_delta_ready_fraction'] = state_delta_ready_fraction
            row_copy['mixture_evidence_anchor_ready_fraction'] = evidence_anchor_ready_fraction
            row_copy['mixture_min_state_delta_ready_fraction'] = min_state_delta_ready_fraction
            row_copy['mixture_min_evidence_anchor_ready_fraction'] = min_evidence_anchor_ready_fraction
            materialized_rows.append(row_copy)

        surface_cards.append(
            {
                'surface': surface,
                'task_family': task_family,
                'storage_format': storage_format,
                'path': str(source_path),
                'expected_row_count': expected_row_count,
                'actual_row_count': len(source_rows),
                'materialized_row_count': len(kept_rows),
                'weight': weight,
                'filter_expr': filter_expr,
                'manifest_filter_expr': manifest_filter_expr,
                'manifest_accepted': True,
                'state_delta_ready_fraction': state_delta_ready_fraction,
                'evidence_anchor_ready_fraction': evidence_anchor_ready_fraction,
                'min_state_delta_ready_fraction': min_state_delta_ready_fraction,
                'min_evidence_anchor_ready_fraction': min_evidence_anchor_ready_fraction,
            }
        )

    if not materialized_rows:
        raise ValueError('empty_materialized_rows')

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
