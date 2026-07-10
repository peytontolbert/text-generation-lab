from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from long_context_common import write_json, write_jsonl


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT / "configs" / "software_maintainer" / "strict_long_context_splitter_v1.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _pack_token_count(row: dict[str, Any]) -> int:
    metadata = row.get('metadata')
    if isinstance(metadata, str) and metadata.strip():
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            metadata = {}
    if isinstance(metadata, dict):
        return int(metadata.get('pack_token_count') or 0)
    return 0


def _resolve_targets(pack_count: int, *, eval_ratio: float, strict_ratio: float) -> dict[str, int]:
    if pack_count < 3:
        raise ValueError(f'insufficient_pack_count_for_heldout_splits:{pack_count}')
    eval_target = max(1, int(round(pack_count * eval_ratio)))
    strict_target = max(1, int(round(pack_count * strict_ratio)))
    if eval_target + strict_target >= pack_count:
        strict_target = max(1, min(strict_target, pack_count - 2))
        eval_target = max(1, min(eval_target, pack_count - strict_target - 1))
    train_target = pack_count - eval_target - strict_target
    if train_target < 1:
        raise ValueError(f'invalid_pack_targets:pack_count={pack_count}:eval={eval_target}:strict={strict_target}')
    return {'train': train_target, 'eval': eval_target, 'strict_eval': strict_target}


def assign_strict_long_context_pack_splits(
    *,
    rows_path: Path,
    output_dir: Path,
    config_path: Path = DEFAULT_CONFIG_PATH,
    eval_ratio: float | None = None,
    strict_ratio: float | None = None,
) -> dict[str, Any]:
    config = _read_json(config_path.resolve())
    defaults = dict(config.get('splitter_defaults') or {})
    resolved_eval_ratio = float(defaults.get('eval_ratio', 0.1) if eval_ratio is None else eval_ratio)
    resolved_strict_ratio = float(defaults.get('strict_ratio', 0.1) if strict_ratio is None else strict_ratio)

    rows = _read_jsonl(rows_path)
    if not rows:
        raise ValueError('empty_rows')

    pack_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    pack_stats: dict[str, dict[str, Any]] = {}
    for row in rows:
        pack_id = str(row.get('pack_id') or '').strip()
        if not pack_id:
            raise ValueError('missing_pack_id')
        pack_rows[pack_id].append(dict(row))
        stats = pack_stats.setdefault(pack_id, {
            'pack_id': pack_id,
            'row_count': 0,
            'retrieval_rows': 0,
            'surface_counts': Counter(),
            'pack_token_count': 0,
        })
        stats['row_count'] += 1
        surface = str(row.get('mixture_surface') or '')
        stats['surface_counts'][surface] += 1
        if surface == 'retrieval_rows':
            stats['retrieval_rows'] += 1
        stats['pack_token_count'] = max(stats['pack_token_count'], _pack_token_count(row))

    targets = _resolve_targets(len(pack_rows), eval_ratio=resolved_eval_ratio, strict_ratio=resolved_strict_ratio)
    ordered_packs = sorted(
        pack_stats.values(),
        key=lambda item: (-int(item['row_count']), -int(item['pack_token_count']), str(item['pack_id'])),
    )

    assigned: dict[str, str] = {}
    selected_eval = ordered_packs[0]
    assigned[selected_eval['pack_id']] = 'eval'
    selected_strict = ordered_packs[1]
    assigned[selected_strict['pack_id']] = 'strict_eval'

    remaining_targets = {
        'train': targets['train'],
        'eval': targets['eval'] - 1,
        'strict_eval': targets['strict_eval'] - 1,
    }
    remaining_row_targets = {
        'train': sum(item['row_count'] for item in ordered_packs) * (targets['train'] / len(ordered_packs)),
        'eval': sum(item['row_count'] for item in ordered_packs) * (targets['eval'] / len(ordered_packs)) - selected_eval['row_count'],
        'strict_eval': sum(item['row_count'] for item in ordered_packs) * (targets['strict_eval'] / len(ordered_packs)) - selected_strict['row_count'],
    }

    for pack in ordered_packs[2:]:
        candidates = [split for split, count in remaining_targets.items() if count > 0]
        if not candidates:
            raise ValueError('no_remaining_split_capacity')
        split = max(
            candidates,
            key=lambda name: (remaining_row_targets[name], remaining_targets[name], name == 'train'),
        )
        assigned[pack['pack_id']] = split
        remaining_targets[split] -= 1
        remaining_row_targets[split] -= pack['row_count']

    if any(value != 0 for value in remaining_targets.values()):
        raise ValueError(f'unfilled_split_targets:{remaining_targets}')

    split_cards: dict[str, Any] = {
        'train': {'packs': 0, 'rows': 0, 'surface_counts': Counter()},
        'eval': {'packs': 0, 'rows': 0, 'surface_counts': Counter()},
        'strict_eval': {'packs': 0, 'rows': 0, 'surface_counts': Counter()},
    }
    output_rows: list[dict[str, Any]] = []
    for pack_id, pack_row_list in sorted(pack_rows.items()):
        split = assigned[pack_id]
        split_cards[split]['packs'] += 1
        for row in pack_row_list:
            out = dict(row)
            out['effective_split'] = split
            out['split'] = split
            output_rows.append(out)
            split_cards[split]['rows'] += 1
            split_cards[split]['surface_counts'][str(out.get('mixture_surface') or '')] += 1

    output_rows.sort(key=lambda row: (str(row.get('effective_split') or ''), str(row.get('mixture_surface') or ''), str(row.get('mixture_row_id') or '')))
    output_dir.mkdir(parents=True, exist_ok=True)
    rows_out = output_dir / 'strict_long_context_split_rows.jsonl'
    card_out = output_dir / 'strict_long_context_split_card.json'
    write_jsonl(rows_out, output_rows)
    card = {
        'rows_path': str(rows_path),
        'output_dir': str(output_dir),
        'pack_count': len(pack_rows),
        'targets': targets,
        'ratios': {'eval_ratio': resolved_eval_ratio, 'strict_ratio': resolved_strict_ratio},
        'assignments': assigned,
        'split_cards': {
            split: {
                'packs': stats['packs'],
                'rows': stats['rows'],
                'surface_counts': dict(sorted(stats['surface_counts'].items())),
            }
            for split, stats in split_cards.items()
        },
        'pack_stats': [
            {
                'pack_id': pack['pack_id'],
                'row_count': pack['row_count'],
                'retrieval_rows': pack['retrieval_rows'],
                'pack_token_count': pack['pack_token_count'],
                'surface_counts': dict(sorted(pack['surface_counts'].items())),
                'assigned_split': assigned[pack['pack_id']],
            }
            for pack in ordered_packs
        ],
    }
    write_json(card_out, card)
    return {'rows_path': str(rows_out), 'card_path': str(card_out), 'split_cards': card['split_cards'], 'targets': targets}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Assign deterministic held-out splits over strict long-context mixture rows at pack granularity.')
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument('--rows', type=Path, default=ROOT / 'runs' / 'local' / 'artifacts' / 'strict_long_context_mixture_rows_v1' / 'strict_long_context_mixture_rows.jsonl')
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--eval-ratio', type=float)
    parser.add_argument('--strict-ratio', type=float)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    assign_strict_long_context_pack_splits(
        rows_path=args.rows,
        output_dir=args.output_dir,
        config_path=args.config,
        eval_ratio=args.eval_ratio,
        strict_ratio=args.strict_ratio,
    )


if __name__ == '__main__':
    main()
