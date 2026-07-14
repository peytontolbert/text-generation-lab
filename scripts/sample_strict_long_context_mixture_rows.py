from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from pathlib import Path
from typing import Any

from long_context_common import write_json, write_jsonl


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT / "configs" / "software_maintainer" / "strict_long_context_sampler_v1.json"
COMPARISON_OPERATORS = ('>=', '<=', '!=', '==', '>', '<')


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open('r', encoding='utf-8') as handle:
        for line in handle:
            if not line.strip():
                continue
            rows.append(json.loads(line))
    return rows


def _resolve_path(base_dir: Path, value: str | None) -> Path | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    candidate = Path(text)
    if candidate.is_absolute():
        return candidate
    return (base_dir / candidate).resolve()


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


def _row_value(row: dict[str, Any], key: str) -> Any:
    if key in row:
        return row.get(key)
    prefixed_key = f'mixture_{key}'
    if prefixed_key in row:
        return row.get(prefixed_key)
    return None


def _matches_clause(row: dict[str, Any], clause: str) -> bool:
    clause = clause.strip()
    if not clause:
        return True
    if ' contains ' in clause:
        key, expected = clause.split(' contains ', 1)
        actual = str(_row_value(row, key.strip()) or '')
        return expected.strip() in actual
    for operator in COMPARISON_OPERATORS:
        if operator not in clause:
            continue
        key, expected = clause.split(operator, 1)
        actual = _row_value(row, key.strip())
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


def _normalized_split(row: dict[str, Any]) -> str:
    split = str(row.get('effective_split') or row.get('split') or row.get('requested_split') or 'train').strip()
    if split == 'strict':
        return 'strict_eval'
    if split not in {'train', 'eval', 'strict_eval'}:
        return 'train'
    return split


def _weighted_sample(rows: list[dict[str, Any]], *, count: int, rng: random.Random) -> list[dict[str, Any]]:
    if count >= len(rows):
        return list(rows)
    indexed = list(enumerate(rows))
    selected: list[dict[str, Any]] = []
    remaining = indexed
    for _ in range(count):
        total = sum(max(float(row.get('mixture_weight') or 0.0), 1e-6) for _, row in remaining)
        threshold = rng.random() * total
        running = 0.0
        picked_index = 0
        for idx, (_, row) in enumerate(remaining):
            running += max(float(row.get('mixture_weight') or 0.0), 1e-6)
            if running >= threshold:
                picked_index = idx
                break
        _, picked = remaining.pop(picked_index)
        selected.append(picked)
    return selected


def _passes_quality_thresholds(
    row: dict[str, Any],
    *,
    min_state_delta_ready_fraction: float | None,
    min_evidence_anchor_ready_fraction: float | None,
) -> bool:
    if min_state_delta_ready_fraction is not None:
        value = _row_value(row, 'min_state_delta_ready_fraction')
        if value is None or float(value) < float(min_state_delta_ready_fraction):
            return False
    if min_evidence_anchor_ready_fraction is not None:
        value = _row_value(row, 'min_evidence_anchor_ready_fraction')
        if value is None or float(value) < float(min_evidence_anchor_ready_fraction):
            return False
    return True


def sample_strict_long_context_mixture_rows(
    *,
    rows_path: Path,
    output_dir: Path,
    config_path: Path = DEFAULT_CONFIG_PATH,
    seed: int | None = None,
    max_train_rows: int | None = None,
    max_eval_rows: int | None = None,
    max_strict_rows: int | None = None,
    min_state_delta_ready_fraction: float | None = None,
    min_evidence_anchor_ready_fraction: float | None = None,
    filter_expr: str | None = None,
) -> dict[str, Any]:
    config_path = config_path.resolve()
    config = _read_json(config_path)
    defaults = dict(config.get('sampler_defaults') or {})
    resolved_seed = int(defaults.get('seed', 0) if seed is None else seed)
    resolved_max_train = defaults.get('max_train_rows') if max_train_rows is None else max_train_rows
    resolved_max_eval = defaults.get('max_eval_rows') if max_eval_rows is None else max_eval_rows
    resolved_max_strict = defaults.get('max_strict_rows') if max_strict_rows is None else max_strict_rows
    resolved_min_state_delta = defaults.get('min_state_delta_ready_fraction') if min_state_delta_ready_fraction is None else min_state_delta_ready_fraction
    resolved_min_evidence_anchor = defaults.get('min_evidence_anchor_ready_fraction') if min_evidence_anchor_ready_fraction is None else min_evidence_anchor_ready_fraction
    resolved_filter_expr = str(defaults.get('filter_expr') or '').strip() if filter_expr is None else str(filter_expr).strip()
    if resolved_filter_expr == '':
        resolved_filter_expr = None

    rows = _read_jsonl(rows_path)
    if not rows:
        raise ValueError('empty_mixture_rows')

    filtered_rows: list[dict[str, Any]] = []
    for row in rows:
        if not _passes_quality_thresholds(
            row,
            min_state_delta_ready_fraction=None if resolved_min_state_delta is None else float(resolved_min_state_delta),
            min_evidence_anchor_ready_fraction=None if resolved_min_evidence_anchor is None else float(resolved_min_evidence_anchor),
        ):
            continue
        if not _matches_filter(row, resolved_filter_expr):
            continue
        filtered_rows.append(row)
    if not filtered_rows:
        raise ValueError('empty_filtered_mixture_rows')

    by_split: dict[str, list[dict[str, Any]]] = {'train': [], 'eval': [], 'strict_eval': []}
    for row in filtered_rows:
        split = _normalized_split(row)
        row_copy = dict(row)
        row_copy['split'] = split
        by_split[split].append(row_copy)

    caps = {
        'train': None if resolved_max_train is None else int(resolved_max_train),
        'eval': None if resolved_max_eval is None else int(resolved_max_eval),
        'strict_eval': None if resolved_max_strict is None else int(resolved_max_strict),
    }
    rng = random.Random(resolved_seed)
    sampled: list[dict[str, Any]] = []
    split_cards: dict[str, Any] = {}
    for split in ('train', 'eval', 'strict_eval'):
        split_rows = list(by_split[split])
        if not split_rows:
            split_cards[split] = {'available': 0, 'selected': 0, 'surface_counts': {}}
            continue
        split_rows.sort(key=lambda row: (str(row.get('mixture_surface') or ''), str(row.get('mixture_row_id') or '')))
        cap = caps[split]
        selected = split_rows if cap is None else _weighted_sample(split_rows, count=cap, rng=rng)
        selected.sort(key=lambda row: (str(row.get('mixture_surface') or ''), str(row.get('mixture_row_id') or '')))
        sampled.extend(selected)
        split_cards[split] = {
            'available': len(split_rows),
            'selected': len(selected),
            'surface_counts': dict(sorted(Counter(str(row.get('mixture_surface') or '') for row in selected).items())),
        }

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / 'strict_long_context_sampled_manifest.jsonl'
    card_path = output_dir / 'strict_long_context_sampled_manifest_card.json'
    write_jsonl(manifest_path, sampled)
    card = {
        'config_path': str(config_path),
        'rows_path': str(rows_path),
        'output_dir': str(output_dir),
        'seed': resolved_seed,
        'caps': caps,
        'filter_expr': resolved_filter_expr,
        'min_state_delta_ready_fraction': resolved_min_state_delta,
        'min_evidence_anchor_ready_fraction': resolved_min_evidence_anchor,
        'row_count': len(sampled),
        'filtered_row_count': len(filtered_rows),
        'split_cards': split_cards,
    }
    write_json(card_path, card)
    return {
        'manifest_path': str(manifest_path),
        'card_path': str(card_path),
        'row_count': len(sampled),
        'filtered_row_count': len(filtered_rows),
        'split_cards': split_cards,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Sample the canonical strict long-context mixture rows into one trainer-ready manifest.')
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument('--rows', type=Path, default=ROOT / 'runs' / 'local' / 'artifacts' / 'strict_long_context_mixture_rows_v1' / 'strict_long_context_mixture_rows.jsonl')
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--seed', type=int)
    parser.add_argument('--max-train-rows', type=int)
    parser.add_argument('--max-eval-rows', type=int)
    parser.add_argument('--max-strict-rows', type=int)
    parser.add_argument('--min-state-delta-ready-fraction', type=float)
    parser.add_argument('--min-evidence-anchor-ready-fraction', type=float)
    parser.add_argument('--filter-expr')
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sample_strict_long_context_mixture_rows(
        rows_path=args.rows,
        output_dir=args.output_dir,
        config_path=args.config,
        seed=args.seed,
        max_train_rows=args.max_train_rows,
        max_eval_rows=args.max_eval_rows,
        max_strict_rows=args.max_strict_rows,
        min_state_delta_ready_fraction=args.min_state_delta_ready_fraction,
        min_evidence_anchor_ready_fraction=args.min_evidence_anchor_ready_fraction,
        filter_expr=args.filter_expr,
    )


if __name__ == '__main__':
    main()
