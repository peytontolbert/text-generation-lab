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


def audit_candidate_packs(
    *,
    packs_path: Path,
    chunk_jaccard_warn_threshold: float = 0.25,
    candidate_overlap_warn_threshold: int = 1,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    packs = read_jsonl(packs_path)
    pair_rows: list[dict[str, Any]] = []
    chunk_jaccards: list[float] = []
    chunk_intersections: list[int] = []
    candidate_intersections: list[int] = []
    flagged_pairs = 0

    for left_index in range(len(packs)):
        left = packs[left_index]
        left_chunk_ids = set(str(item) for item in left.get('ordered_chunk_ids', []))
        left_candidate_ids = set(str(item) for item in left.get('candidate_ids', []))
        for right_index in range(left_index + 1, len(packs)):
            right = packs[right_index]
            right_chunk_ids = set(str(item) for item in right.get('ordered_chunk_ids', []))
            right_candidate_ids = set(str(item) for item in right.get('candidate_ids', []))
            chunk_intersection = len(left_chunk_ids & right_chunk_ids)
            candidate_intersection = len(left_candidate_ids & right_candidate_ids)
            chunk_jaccard = _jaccard(left_chunk_ids, right_chunk_ids)
            flagged = chunk_jaccard >= chunk_jaccard_warn_threshold or candidate_intersection >= candidate_overlap_warn_threshold
            if flagged:
                flagged_pairs += 1
            row = {
                'left_pack_id': str(left.get('pack_id') or ''),
                'right_pack_id': str(right.get('pack_id') or ''),
                'left_pack_token_count': int(left.get('pack_token_count') or 0),
                'right_pack_token_count': int(right.get('pack_token_count') or 0),
                'left_chunk_count': int(left.get('chunk_count') or 0),
                'right_chunk_count': int(right.get('chunk_count') or 0),
                'left_candidate_count': int(left.get('candidate_count') or 0),
                'right_candidate_count': int(right.get('candidate_count') or 0),
                'chunk_intersection_count': chunk_intersection,
                'candidate_intersection_count': candidate_intersection,
                'chunk_jaccard': round(chunk_jaccard, 6),
                'flagged': flagged,
            }
            pair_rows.append(row)
            chunk_jaccards.append(chunk_jaccard)
            chunk_intersections.append(chunk_intersection)
            candidate_intersections.append(candidate_intersection)

    pair_rows.sort(
        key=lambda row: (
            bool(row.get('flagged')),
            float(row.get('chunk_jaccard') or 0.0),
            int(row.get('chunk_intersection_count') or 0),
            str(row.get('left_pack_id') or ''),
            str(row.get('right_pack_id') or ''),
        ),
        reverse=True,
    )
    summary = {
        'pack_count': len(packs),
        'pair_count': len(pair_rows),
        'chunk_jaccard_warn_threshold': float(chunk_jaccard_warn_threshold),
        'candidate_overlap_warn_threshold': int(candidate_overlap_warn_threshold),
        'flagged_pair_count': flagged_pairs,
        'chunk_jaccard_stats': {
            'min': min(chunk_jaccards, default=0.0),
            'max': max(chunk_jaccards, default=0.0),
            'avg': (sum(chunk_jaccards) / len(chunk_jaccards)) if chunk_jaccards else 0.0,
        },
        'chunk_intersection_stats': {
            'min': min(chunk_intersections, default=0),
            'max': max(chunk_intersections, default=0),
            'avg': (sum(chunk_intersections) / len(chunk_intersections)) if chunk_intersections else 0.0,
        },
        'candidate_intersection_stats': {
            'min': min(candidate_intersections, default=0),
            'max': max(candidate_intersections, default=0),
            'avg': (sum(candidate_intersections) / len(candidate_intersections)) if candidate_intersections else 0.0,
        },
        'top_flagged_pairs': pair_rows[: min(10, len(pair_rows))],
    }
    return pair_rows, summary


def main() -> None:
    parser = argparse.ArgumentParser(description='Audit overlap across long-context candidate packs.')
    parser.add_argument('--packs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--summary-output', type=Path)
    parser.add_argument('--chunk-jaccard-warn-threshold', type=float, default=0.25)
    parser.add_argument('--candidate-overlap-warn-threshold', type=int, default=1)
    args = parser.parse_args()
    pair_rows, summary = audit_candidate_packs(
        packs_path=args.packs,
        chunk_jaccard_warn_threshold=args.chunk_jaccard_warn_threshold,
        candidate_overlap_warn_threshold=args.candidate_overlap_warn_threshold,
    )
    write_jsonl(args.output, pair_rows)
    write_json(args.summary_output or args.output.with_name('candidate_pack_overlap_summary.json'), summary)


if __name__ == '__main__':
    main()
