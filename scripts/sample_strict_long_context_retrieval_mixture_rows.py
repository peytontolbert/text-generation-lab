from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from pathlib import Path
from typing import Any

from long_context_common import write_json, write_jsonl

ROOT = Path(__file__).resolve().parents[1]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def _normalized_split(row: dict[str, Any]) -> str:
    split = str(row.get('split') or row.get('effective_split') or 'train').strip()
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


def sample_strict_long_context_retrieval_mixture_rows(
    *,
    rows_path: Path,
    output_dir: Path,
    seed: int = 0,
    max_train_rows: int | None = None,
    max_eval_rows: int | None = None,
    max_strict_rows: int | None = None,
) -> dict[str, Any]:
    rows = _read_jsonl(rows_path)
    if not rows:
        raise ValueError('empty_retrieval_mixture_rows')

    by_split: dict[str, list[dict[str, Any]]] = {'train': [], 'eval': [], 'strict_eval': []}
    for row in rows:
        split = _normalized_split(row)
        row_copy = dict(row)
        row_copy['split'] = split
        by_split[split].append(row_copy)

    caps = {
        'train': max_train_rows,
        'eval': max_eval_rows,
        'strict_eval': max_strict_rows,
    }
    rng = random.Random(seed)
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
    manifest_path = output_dir / 'strict_long_context_retrieval_sampled_manifest.jsonl'
    card_path = output_dir / 'strict_long_context_retrieval_sampled_manifest_card.json'
    write_jsonl(manifest_path, sampled)
    card = {
        'rows_path': str(rows_path),
        'output_dir': str(output_dir),
        'seed': seed,
        'caps': caps,
        'row_count': len(sampled),
        'split_cards': split_cards,
    }
    write_json(card_path, card)
    return {'manifest_path': str(manifest_path), 'card_path': str(card_path), 'row_count': len(sampled), 'split_cards': split_cards}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Sample trainer-ready retrieval-side strict long-context mixture manifests.')
    parser.add_argument('--rows', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--max-train-rows', type=int)
    parser.add_argument('--max-eval-rows', type=int)
    parser.add_argument('--max-strict-rows', type=int)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sample_strict_long_context_retrieval_mixture_rows(
        rows_path=args.rows,
        output_dir=args.output_dir,
        seed=args.seed,
        max_train_rows=args.max_train_rows,
        max_eval_rows=args.max_eval_rows,
        max_strict_rows=args.max_strict_rows,
    )


if __name__ == '__main__':
    main()
