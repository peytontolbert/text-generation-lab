from __future__ import annotations

import argparse
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from long_context_common import read_jsonl, write_json, write_jsonl


def _jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def cluster_candidate_packs(
    *,
    packs_path: Path,
    min_chunk_jaccard: float = 0.25,
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
            }
        )
    adjacency: dict[str, set[str]] = defaultdict(set)
    edge_rows: list[dict[str, Any]] = []
    for left_index in range(len(prepared)):
        left = prepared[left_index]
        for right_index in range(left_index + 1, len(prepared)):
            right = prepared[right_index]
            chunk_jaccard = _jaccard(left['chunk_ids'], right['chunk_ids'])
            if chunk_jaccard < min_chunk_jaccard:
                continue
            intersection = len(left['chunk_ids'] & right['chunk_ids'])
            adjacency[left['pack_id']].add(right['pack_id'])
            adjacency[right['pack_id']].add(left['pack_id'])
            edge_rows.append(
                {
                    'left_pack_id': left['pack_id'],
                    'right_pack_id': right['pack_id'],
                    'chunk_jaccard': round(chunk_jaccard, 6),
                    'chunk_intersection_count': intersection,
                }
            )
    visited: set[str] = set()
    cluster_rows: list[dict[str, Any]] = []
    pack_by_id = {row['pack_id']: row for row in prepared}
    for row in prepared:
        pack_id = row['pack_id']
        if pack_id in visited:
            continue
        queue = deque([pack_id])
        visited.add(pack_id)
        members: list[str] = []
        cluster_chunk_ids: set[str] = set()
        cluster_token_count = 0
        cluster_candidate_count = 0
        while queue:
            current = queue.popleft()
            members.append(current)
            current_row = pack_by_id[current]
            cluster_chunk_ids.update(current_row['chunk_ids'])
            cluster_token_count += current_row['pack_token_count']
            cluster_candidate_count += len(current_row['candidate_ids'])
            for neighbor in sorted(adjacency.get(current, set())):
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                queue.append(neighbor)
        cluster_rows.append(
            {
                'cluster_id': f'cluster_{len(cluster_rows) + 1:04d}',
                'pack_count': len(members),
                'pack_ids': sorted(members),
                'cluster_token_count': cluster_token_count,
                'cluster_candidate_count': cluster_candidate_count,
                'cluster_chunk_union_count': len(cluster_chunk_ids),
            }
        )
    cluster_rows.sort(key=lambda row: (row['pack_count'], row['cluster_token_count'], row['cluster_id']), reverse=True)
    summary = {
        'pack_count': len(prepared),
        'cluster_count': len(cluster_rows),
        'min_chunk_jaccard': float(min_chunk_jaccard),
        'edge_count': len(edge_rows),
        'largest_cluster_pack_count': max((row['pack_count'] for row in cluster_rows), default=0),
        'largest_cluster_token_count': max((row['cluster_token_count'] for row in cluster_rows), default=0),
        'singleton_cluster_count': sum(1 for row in cluster_rows if row['pack_count'] == 1),
        'clusters': cluster_rows,
        'top_edges': sorted(edge_rows, key=lambda row: (row['chunk_jaccard'], row['chunk_intersection_count']), reverse=True)[: min(20, len(edge_rows))],
    }
    return edge_rows, summary


def main() -> None:
    parser = argparse.ArgumentParser(description='Cluster long-context candidate packs into overlap families.')
    parser.add_argument('--packs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--summary-output', type=Path)
    parser.add_argument('--min-chunk-jaccard', type=float, default=0.25)
    args = parser.parse_args()
    edge_rows, summary = cluster_candidate_packs(
        packs_path=args.packs,
        min_chunk_jaccard=args.min_chunk_jaccard,
    )
    write_jsonl(args.output, edge_rows)
    write_json(args.summary_output or args.output.with_name('candidate_pack_cluster_summary.json'), summary)


if __name__ == '__main__':
    main()
