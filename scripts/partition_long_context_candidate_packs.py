from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from long_context_common import read_jsonl, write_json, write_jsonl


def _jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def partition_candidate_packs(
    *,
    packs_path: Path,
    split_names: tuple[str, ...] = ('train', 'val', 'test'),
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    packs = read_jsonl(packs_path)
    prepared = []
    for row in packs:
        prepared.append(
            {
                'pack_id': str(row.get('pack_id') or ''),
                'pack_token_count': int(row.get('pack_token_count') or 0),
                'chunk_ids': set(str(item) for item in row.get('ordered_chunk_ids', [])),
                'candidate_ids': [str(item) for item in row.get('candidate_ids', [])],
                'candidate_count': int(row.get('candidate_count') or 0),
                'chunk_count': int(row.get('chunk_count') or 0),
            }
        )
    prepared.sort(key=lambda row: (row['pack_token_count'], row['pack_id']), reverse=True)
    split_states = {
        name: {
            'split': name,
            'pack_ids': [],
            'chunk_ids': set(),
            'token_count': 0,
            'candidate_count': 0,
            'chunk_count_union': 0,
        }
        for name in split_names
    }
    total_tokens = sum(row['pack_token_count'] for row in prepared)
    target_per_split = total_tokens / max(1, len(split_names))

    assignments: list[dict[str, Any]] = []
    for pack in prepared:
        best_split: str | None = None
        best_score: tuple[float, float, int, str] | None = None
        for split_name in split_names:
            state = split_states[split_name]
            overlap_jaccard = _jaccard(pack['chunk_ids'], state['chunk_ids'])
            projected_tokens = state['token_count'] + pack['pack_token_count']
            token_distance = abs(projected_tokens - target_per_split)
            score = (
                overlap_jaccard,
                token_distance,
                len(state['pack_ids']),
                split_name,
            )
            if best_score is None or score < best_score:
                best_score = score
                best_split = split_name
        assert best_split is not None
        state = split_states[best_split]
        assignment = {
            'pack_id': pack['pack_id'],
            'split': best_split,
            'pack_token_count': pack['pack_token_count'],
            'candidate_count': pack['candidate_count'],
            'chunk_count': pack['chunk_count'],
            'split_chunk_jaccard_before_assignment': round(_jaccard(pack['chunk_ids'], state['chunk_ids']), 6),
            'split_token_count_before_assignment': int(state['token_count']),
        }
        state['pack_ids'].append(pack['pack_id'])
        state['chunk_ids'].update(pack['chunk_ids'])
        state['token_count'] += pack['pack_token_count']
        state['candidate_count'] += pack['candidate_count']
        state['chunk_count_union'] = len(state['chunk_ids'])
        assignments.append(assignment)

    split_rows = []
    for split_name in split_names:
        state = split_states[split_name]
        split_rows.append(
            {
                'split': split_name,
                'pack_count': len(state['pack_ids']),
                'pack_ids': state['pack_ids'],
                'token_count': int(state['token_count']),
                'candidate_count': int(state['candidate_count']),
                'chunk_count_union': int(state['chunk_count_union']),
            }
        )

    cross_split_pairs: list[dict[str, Any]] = []
    split_jaccards: list[float] = []
    for left_index in range(len(split_names)):
        left = split_states[split_names[left_index]]
        for right_index in range(left_index + 1, len(split_names)):
            right = split_states[split_names[right_index]]
            chunk_jaccard = _jaccard(left['chunk_ids'], right['chunk_ids'])
            row = {
                'left_split': left['split'],
                'right_split': right['split'],
                'chunk_jaccard': round(chunk_jaccard, 6),
                'chunk_intersection_count': len(left['chunk_ids'] & right['chunk_ids']),
                'left_token_count': int(left['token_count']),
                'right_token_count': int(right['token_count']),
            }
            cross_split_pairs.append(row)
            split_jaccards.append(chunk_jaccard)

    summary = {
        'pack_count': len(prepared),
        'split_names': list(split_names),
        'target_per_split_tokens': target_per_split,
        'split_rows': split_rows,
        'cross_split_chunk_jaccard_stats': {
            'min': min(split_jaccards, default=0.0),
            'max': max(split_jaccards, default=0.0),
            'avg': (sum(split_jaccards) / len(split_jaccards)) if split_jaccards else 0.0,
        },
        'cross_split_pairs': cross_split_pairs,
    }
    return assignments, summary


def main() -> None:
    parser = argparse.ArgumentParser(description='Partition long-context candidate packs into low-overlap splits.')
    parser.add_argument('--packs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--summary-output', type=Path)
    parser.add_argument('--split-names', type=str, default='train,val,test')
    args = parser.parse_args()
    split_names = tuple(item.strip() for item in args.split_names.split(',') if item.strip())
    assignments, summary = partition_candidate_packs(
        packs_path=args.packs,
        split_names=split_names,
    )
    write_jsonl(args.output, assignments)
    write_json(args.summary_output or args.output.with_name('candidate_pack_split_summary.json'), summary)


if __name__ == '__main__':
    main()
