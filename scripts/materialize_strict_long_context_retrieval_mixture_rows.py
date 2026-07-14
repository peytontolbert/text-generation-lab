from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from long_context_common import write_json, write_jsonl


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


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


def _matches_clause(row: dict[str, Any], clause: str) -> bool:
    clause = clause.strip()
    if not clause:
        return True
    if ' contains ' in clause:
        key, expected = clause.split(' contains ', 1)
        actual = str(row.get(key.strip()) or '')
        return expected.strip() in actual
    if '==' in clause:
        key, expected = clause.split('==', 1)
        actual = row.get(key.strip())
        return _coerce_value(actual) == _coerce_value(expected.strip())
    raise ValueError(f'unsupported_filter_clause:{clause}')


def _matches_filter(row: dict[str, Any], filter_expr: str | None) -> bool:
    if not filter_expr:
        return True
    or_clauses = [part.strip() for part in str(filter_expr).split(' or ') if part.strip()]
    return any(_matches_clause(row, clause) for clause in or_clauses)


def materialize_strict_long_context_retrieval_mixture_rows(*, mixture_manifest_path: Path, output_dir: Path) -> dict[str, Any]:
    manifest_rows = _read_jsonl(mixture_manifest_path)
    if not manifest_rows:
        raise ValueError('empty_retrieval_mixture_manifest')

    materialized_rows: list[dict[str, Any]] = []
    surface_cards: list[dict[str, Any]] = []
    seen_row_ids: set[str] = set()

    for manifest_row in manifest_rows:
        surface = str(manifest_row.get('surface') or '').strip()
        task_family = str(manifest_row.get('task_family') or '').strip()
        source_path = Path(str(manifest_row.get('path') or '').strip())
        expected_row_count = int(manifest_row.get('row_count') or 0)
        weight = float(manifest_row.get('weight') or 0.0)
        dataset_card_path = str(manifest_row.get('dataset_card_path') or '').strip()
        profile = str(manifest_row.get('profile') or '').strip()
        filter_expr = str(manifest_row.get('filter_expr') or '').strip() or None

        if not surface or not task_family or not str(source_path):
            raise ValueError(f'incomplete_retrieval_mixture_manifest_row:{manifest_row}')
        if expected_row_count <= 0:
            raise ValueError(f'invalid_expected_row_count:{surface}:{expected_row_count}')
        if weight <= 0.0:
            raise ValueError(f'invalid_weight:{surface}:{weight}')
        if not source_path.exists():
            raise FileNotFoundError(f'missing_surface_path:{source_path}')

        source_rows = _read_jsonl(source_path)
        if len(source_rows) != expected_row_count:
            raise ValueError(f'row_count_mismatch:{surface}:expected={expected_row_count}:actual={len(source_rows)}')

        kept_count = 0
        for row in source_rows:
            if not _matches_filter(row, filter_expr):
                continue
            row_id = str(row.get('curriculum_example_id') or row.get('pairwise_example_id') or row.get('listwise_example_id') or row.get('retriever_example_id') or row.get('row_id') or '').strip()
            if not row_id:
                raise ValueError(f'missing_row_id:{surface}:{source_path}')
            mixture_row_id = f'{surface}::{row_id}'
            if mixture_row_id in seen_row_ids:
                raise ValueError(f'duplicate_retrieval_mixture_row_id:{mixture_row_id}')
            seen_row_ids.add(mixture_row_id)
            row_copy = dict(row)
            row_copy['mixture_row_id'] = mixture_row_id
            row_copy['mixture_surface'] = surface
            row_copy['mixture_task_family'] = task_family
            row_copy['mixture_weight'] = weight
            row_copy['mixture_dataset_card_path'] = dataset_card_path
            row_copy['mixture_profile'] = profile
            row_copy['mixture_filter_expr'] = filter_expr
            materialized_rows.append(row_copy)
            kept_count += 1

        surface_cards.append(
            {
                'surface': surface,
                'task_family': task_family,
                'path': str(source_path),
                'expected_row_count': expected_row_count,
                'materialized_row_count': kept_count,
                'weight': weight,
                'profile': profile,
                'filter_expr': filter_expr,
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    rows_path = output_dir / 'strict_long_context_retrieval_mixture_rows.jsonl'
    card_path = output_dir / 'strict_long_context_retrieval_mixture_rows_card.json'
    write_jsonl(rows_path, materialized_rows)
    card = {
        'mixture_manifest_path': str(mixture_manifest_path),
        'output_dir': str(output_dir),
        'row_count': len(materialized_rows),
        'surface_count': len(surface_cards),
        'surface_cards': surface_cards,
    }
    write_json(card_path, card)
    return {'rows_path': str(rows_path), 'card_path': str(card_path), 'row_count': len(materialized_rows), 'surface_cards': surface_cards}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Materialize retrieval-side strict long-context mixture rows with filter application.')
    parser.add_argument('--mixture-manifest', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    materialize_strict_long_context_retrieval_mixture_rows(mixture_manifest_path=args.mixture_manifest, output_dir=args.output_dir)


if __name__ == '__main__':
    main()
