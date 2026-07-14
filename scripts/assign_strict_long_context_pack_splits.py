from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from long_context_common import write_json, write_jsonl


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT / "configs" / "software_maintainer" / "strict_long_context_splitter_v1.json"
PACK_ID_PREFIX_RE = re.compile(r"^lcp_pack_\d+_\d+_")
PACK_ID_SUFFIX_RE = re.compile(r"_[0-9a-f]{8,}$")


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


def _normalized_pack_family(pack_id: str) -> str:
    text = PACK_ID_PREFIX_RE.sub('', str(pack_id or '').strip())
    text = PACK_ID_SUFFIX_RE.sub('', text)
    return text or str(pack_id or '').strip()


def _context_source_signature(row: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    context_rows = row.get('context_rows') or []
    source_ids = sorted({str(item.get('source_id') or '').strip() for item in context_rows if isinstance(item, dict) and str(item.get('source_id') or '').strip()})
    source_types = sorted({str(item.get('source_type') or '').strip() for item in context_rows if isinstance(item, dict) and str(item.get('source_type') or '').strip()})
    if not source_ids and not source_types:
        return '', [], []
    digest = hashlib.sha1(('|'.join(source_ids) + '||' + '|'.join(source_types)).encode('utf-8')).hexdigest()[:16]
    return digest, source_ids, source_types


def _choose_group_key(pack: dict[str, Any]) -> str:
    overlap_families = sorted(value for value in pack.get('overlap_family_ids', set()) if value)
    if overlap_families:
        return 'overlap::' + '|'.join(overlap_families)
    family_key = str(pack.get('pack_family_key') or '')
    source_signature = str(pack.get('source_signature') or '')
    if family_key and source_signature:
        return f'family_source::{family_key}::{source_signature}'
    if family_key:
        return f'family::{family_key}'
    if source_signature:
        return f'source::{source_signature}'
    return f'pack::{pack["pack_id"]}'


def _build_group_stats(pack_stats: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for pack in pack_stats.values():
        group_key = _choose_group_key(pack)
        group = groups.setdefault(group_key, {
            'group_key': group_key,
            'pack_ids': [],
            'pack_count': 0,
            'row_count': 0,
            'retrieval_rows': 0,
            'pack_token_count': 0,
            'family_keys': set(),
            'source_signatures': set(),
        })
        group['pack_ids'].append(pack['pack_id'])
        group['pack_count'] += 1
        group['row_count'] += int(pack['row_count'])
        group['retrieval_rows'] += int(pack['retrieval_rows'])
        group['pack_token_count'] = max(group['pack_token_count'], int(pack['pack_token_count']))
        if pack.get('pack_family_key'):
            group['family_keys'].add(str(pack['pack_family_key']))
        if pack.get('source_signature'):
            group['source_signatures'].add(str(pack['source_signature']))
    ordered = sorted(
        groups.values(),
        key=lambda item: (-int(item['pack_count']), -int(item['row_count']), item['group_key']),
    )
    return ordered


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
            'pack_family_key': _normalized_pack_family(pack_id),
            'source_signature': '',
            'source_ids': [],
            'source_types': [],
            'overlap_family_ids': set(),
        })
        overlap_family_id = str(row.get('overlap_family_id') or '').strip()
        if overlap_family_id:
            stats['overlap_family_ids'].add(overlap_family_id)
        stats['row_count'] += 1
        surface = str(row.get('mixture_surface') or '')
        stats['surface_counts'][surface] += 1
        if surface == 'retrieval_rows':
            stats['retrieval_rows'] += 1
        elif surface == 'full_context_rows':
            source_signature, source_ids, source_types = _context_source_signature(row)
            stats['source_signature'] = source_signature or stats['source_signature']
            if source_ids:
                stats['source_ids'] = source_ids
            if source_types:
                stats['source_types'] = source_types
        stats['pack_token_count'] = max(stats['pack_token_count'], _pack_token_count(row))

    targets = _resolve_targets(len(pack_rows), eval_ratio=resolved_eval_ratio, strict_ratio=resolved_strict_ratio)
    total_rows = sum(item['row_count'] for item in pack_stats.values())
    groups = _build_group_stats(pack_stats)

    assigned: dict[str, str] = {}
    split_pack_counts = {'train': 0, 'eval': 0, 'strict_eval': 0}
    split_row_counts = {'train': 0, 'eval': 0, 'strict_eval': 0}
    remaining_row_targets = {
        'train': total_rows * (targets['train'] / len(pack_stats)),
        'eval': total_rows * (targets['eval'] / len(pack_stats)),
        'strict_eval': total_rows * (targets['strict_eval'] / len(pack_stats)),
    }

    for index, group in enumerate(groups):
        groups_left = len(groups) - index - 1
        split_candidates: list[tuple[tuple[int, float, float, int], str]] = []
        for split in ('train', 'eval', 'strict_eval'):
            unmet_pack_need = max(0, targets[split] - split_pack_counts[split])
            required_future_groups = sum(1 for other in ('train', 'eval', 'strict_eval') if max(0, targets[other] - split_pack_counts[other]) > 0 and other != split)
            if groups_left < required_future_groups and unmet_pack_need <= 0:
                continue
            score = (
                1 if unmet_pack_need > 0 else 0,
                float(remaining_row_targets[split]),
                float(unmet_pack_need),
                1 if split == 'train' else 0,
            )
            split_candidates.append((score, split))
        if not split_candidates:
            raise ValueError(f'no_split_candidate_for_group:{group["group_key"]}')
        split = max(split_candidates, key=lambda item: item[0])[1]
        for pack_id in group['pack_ids']:
            assigned[pack_id] = split
        split_pack_counts[split] += int(group['pack_count'])
        split_row_counts[split] += int(group['row_count'])
        remaining_row_targets[split] -= int(group['row_count'])

    if any(split_pack_counts[split] <= 0 for split in ('train', 'eval', 'strict_eval')):
        raise ValueError(f'empty_split_after_group_assignment:{split_pack_counts}')

    ordered_packs = sorted(
        pack_stats.values(),
        key=lambda item: (assigned[item['pack_id']], -int(item['row_count']), -int(item['pack_token_count']), str(item['pack_id'])),
    )

    split_cards: dict[str, Any] = {
        'train': {'packs': 0, 'rows': 0, 'surface_counts': Counter(), 'group_count': 0},
        'eval': {'packs': 0, 'rows': 0, 'surface_counts': Counter(), 'group_count': 0},
        'strict_eval': {'packs': 0, 'rows': 0, 'surface_counts': Counter(), 'group_count': 0},
    }
    for group in groups:
        group_split = assigned[group['pack_ids'][0]]
        split_cards[group_split]['group_count'] += 1

    output_rows: list[dict[str, Any]] = []
    for pack_id, pack_row_list in sorted(pack_rows.items()):
        split = assigned[pack_id]
        split_cards[split]['packs'] += 1
        for row in pack_row_list:
            out = dict(row)
            out['effective_split'] = split
            out['split'] = split
            out['pack_family_key'] = pack_stats[pack_id]['pack_family_key']
            out['pack_source_signature'] = pack_stats[pack_id]['source_signature']
            out['pack_group_key'] = _choose_group_key(pack_stats[pack_id])
            output_rows.append(out)
            split_cards[split]['rows'] += 1
            split_cards[split]['surface_counts'][str(out.get('mixture_surface') or '')] += 1

    output_rows.sort(key=lambda row: (str(row.get('effective_split') or ''), str(row.get('pack_group_key') or ''), str(row.get('mixture_surface') or ''), str(row.get('mixture_row_id') or '')))
    output_dir.mkdir(parents=True, exist_ok=True)
    rows_out = output_dir / 'strict_long_context_split_rows.jsonl'
    card_out = output_dir / 'strict_long_context_split_card.json'
    write_jsonl(rows_out, output_rows)
    card = {
        'rows_path': str(rows_path),
        'output_dir': str(output_dir),
        'pack_count': len(pack_rows),
        'group_count': len(groups),
        'targets': targets,
        'actual_pack_counts': split_pack_counts,
        'actual_row_counts': split_row_counts,
        'ratios': {'eval_ratio': resolved_eval_ratio, 'strict_ratio': resolved_strict_ratio},
        'assignments': assigned,
        'split_cards': {
            split: {
                'packs': stats['packs'],
                'rows': stats['rows'],
                'group_count': stats['group_count'],
                'surface_counts': dict(sorted(stats['surface_counts'].items())),
            }
            for split, stats in split_cards.items()
        },
        'group_cards': [
            {
                'group_key': group['group_key'],
                'pack_ids': sorted(group['pack_ids']),
                'pack_count': group['pack_count'],
                'row_count': group['row_count'],
                'retrieval_rows': group['retrieval_rows'],
                'family_keys': sorted(group['family_keys']),
                'source_signatures': sorted(group['source_signatures']),
                'assigned_split': assigned[group['pack_ids'][0]],
            }
            for group in groups
        ],
        'pack_stats': [
            {
                'pack_id': pack['pack_id'],
                'row_count': pack['row_count'],
                'retrieval_rows': pack['retrieval_rows'],
                'pack_token_count': pack['pack_token_count'],
                'surface_counts': dict(sorted(pack['surface_counts'].items())),
                'pack_family_key': pack['pack_family_key'],
                'source_signature': pack['source_signature'],
                'source_ids': pack['source_ids'],
                'source_types': pack['source_types'],
                'overlap_family_ids': sorted(pack['overlap_family_ids']),
                'group_key': _choose_group_key(pack),
                'assigned_split': assigned[pack['pack_id']],
            }
            for pack in ordered_packs
        ],
    }
    write_json(card_out, card)
    return {'rows_path': str(rows_out), 'card_path': str(card_out), 'split_cards': card['split_cards'], 'targets': targets}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Assign family/source-aware held-out splits over strict long-context mixture rows at pack granularity.')
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
