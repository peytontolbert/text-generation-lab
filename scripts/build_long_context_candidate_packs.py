from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from long_context_common import read_jsonl, stable_id, write_json, write_jsonl
from long_context_parquet import shard_path, write_parquet_shard


def _parquet_safe_candidate_packs(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    safe_rows = []
    for row in rows:
        cloned = dict(row)
        cloned['candidates'] = [
            {k: (json.dumps(v, sort_keys=True) if k == 'model_assisted_signals' else v) for k, v in candidate.items()}
            for candidate in row.get('candidates', [])
        ]
        safe_rows.append(cloned)
    return safe_rows


def _parquet_safe_training_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    safe_rows = []
    for row in rows:
        cloned = dict(row)
        cloned['context_rows'] = [dict(item) for item in row.get('context_rows', [])]
        cloned['target_rows'] = [dict(item) for item in row.get('target_rows', [])]
        safe_rows.append(cloned)
    return safe_rows


def _read_chunk_rows(index_dir: Path) -> list[dict[str, Any]]:
    import pyarrow.parquet as pq

    rows: list[dict[str, Any]] = []
    for shard in sorted((index_dir / 'chunks').glob('*.parquet')):
        rows.extend(pq.read_table(shard).to_pylist())
    return rows


def _chunk_locator(row: dict[str, Any]) -> dict[str, Any]:
    metadata = json.loads(row.get('metadata_json') or '{}')
    return {
        'chunk_id': str(row.get('chunk_id') or ''),
        'source_type': str(row.get('source_type') or ''),
        'source_id': str(row.get('source_id') or ''),
        'doc_id': str(row.get('doc_id') or ''),
        'chunk_index': int(row.get('chunk_index') or 0),
        'token_count': int(row.get('token_count') or 0),
        'path': str(metadata.get('path') or ''),
        'language': metadata.get('language'),
        'modality': str(row.get('modality') or ''),
        'text': str(row.get('text') or ''),
    }


def _source_mix(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get('source_type') or 'unknown')
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _candidate_sort_key(prepared_row: dict[str, Any]) -> tuple[int, str]:
    return (int(prepared_row['support_tokens']), prepared_row['candidate_id'])


def _candidate_limit_ok(pack: dict[str, Any], max_candidates_per_pack: int | None) -> bool:
    return max_candidates_per_pack is None or len(pack['candidates']) < max_candidates_per_pack


def _novel_chunk_ids(candidate: dict[str, Any], pack_chunk_ids: set[str]) -> list[str]:
    return [cid for cid in candidate['chunk_ids'] if cid not in pack_chunk_ids]


def _novel_tokens(candidate: dict[str, Any], pack_chunk_ids: set[str], chunk_token_counts: dict[str, int]) -> int:
    return sum(chunk_token_counts[cid] for cid in _novel_chunk_ids(candidate, pack_chunk_ids))


def _recompute_pack_token_count(pack: dict[str, Any], chunk_token_counts: dict[str, int]) -> int:
    return sum(chunk_token_counts[cid] for cid in pack['chunk_ids'])


def _add_candidate_to_pack(pack: dict[str, Any], candidate: dict[str, Any], chunk_token_counts: dict[str, int]) -> None:
    pack['candidates'].append(candidate)
    pack['chunk_ids'].update(_novel_chunk_ids(candidate, pack['chunk_ids']))
    pack['pack_tokens'] = _recompute_pack_token_count(pack, chunk_token_counts)


def _rebuild_pack(pack: dict[str, Any], chunk_token_counts: dict[str, int]) -> None:
    chunk_ids: set[str] = set()
    for candidate in pack['candidates']:
        chunk_ids.update(candidate['chunk_ids'])
    pack['chunk_ids'] = chunk_ids
    pack['pack_tokens'] = _recompute_pack_token_count(pack, chunk_token_counts)


def _initial_pack_assignment(
    prepared: list[dict[str, Any]],
    *,
    target_pack_tokens: int,
    min_tokens: int,
    max_candidates_per_pack: int | None,
    chunk_token_counts: dict[str, int],
) -> list[dict[str, Any]]:
    packs: list[dict[str, Any]] = []
    for candidate in sorted(prepared, key=_candidate_sort_key, reverse=True):
        best_idx: int | None = None
        best_score: tuple[int, int, int, int, str] | None = None
        for idx, pack in enumerate(packs):
            if not _candidate_limit_ok(pack, max_candidates_per_pack):
                continue
            novel_tokens = _novel_tokens(candidate, pack['chunk_ids'], chunk_token_counts)
            merged_tokens = int(pack['pack_tokens']) + novel_tokens
            if merged_tokens > target_pack_tokens:
                continue
            score = (
                1 if int(pack['pack_tokens']) < min_tokens else 0,
                merged_tokens,
                -novel_tokens,
                -len(pack['candidates']),
                str(pack['seed_candidate_id']),
            )
            if best_score is None or score > best_score:
                best_idx = idx
                best_score = score
        if best_idx is None:
            packs.append(
                {
                    'seed_candidate_id': candidate['candidate_id'],
                    'candidates': [candidate],
                    'chunk_ids': set(candidate['chunk_ids']),
                    'pack_tokens': sum(chunk_token_counts[cid] for cid in candidate['chunk_ids']),
                }
            )
        else:
            _add_candidate_to_pack(packs[best_idx], candidate, chunk_token_counts)
    return packs


def _rebalance_underfilled_packs(
    packs: list[dict[str, Any]],
    *,
    target_pack_tokens: int,
    min_tokens: int,
    max_candidates_per_pack: int | None,
    chunk_token_counts: dict[str, int],
) -> None:
    while True:
        underfilled = [pack for pack in packs if int(pack['pack_tokens']) < min_tokens]
        if not underfilled:
            return
        receiver = min(underfilled, key=lambda pack: int(pack['pack_tokens']))
        best_move: tuple[int, int, dict[str, Any]] | None = None
        for donor_idx, donor in enumerate(packs):
            if donor is receiver or len(donor['candidates']) <= 1:
                continue
            for candidate_idx, candidate in enumerate(list(donor['candidates'])):
                donor_candidates = [item for idx, item in enumerate(donor['candidates']) if idx != candidate_idx]
                donor_chunk_ids: set[str] = set()
                for item in donor_candidates:
                    donor_chunk_ids.update(item['chunk_ids'])
                donor_after = sum(chunk_token_counts[cid] for cid in donor_chunk_ids)
                if donor_after < min_tokens:
                    continue
                if not _candidate_limit_ok(receiver, max_candidates_per_pack):
                    continue
                receiver_novel = _novel_tokens(candidate, receiver['chunk_ids'], chunk_token_counts)
                receiver_after = int(receiver['pack_tokens']) + receiver_novel
                if receiver_after > target_pack_tokens:
                    continue
                score = (1 if receiver_after >= min_tokens else 0, receiver_after, donor_after)
                if best_move is None or score > best_move[:3]:
                    best_move = (score[0], score[1], score[2], donor_idx, candidate_idx, candidate)  # type: ignore[assignment]
        if best_move is None:
            return
        _, _, _, donor_idx, candidate_idx, candidate = best_move
        donor = packs[donor_idx]
        donor['candidates'].pop(candidate_idx)
        _rebuild_pack(donor, chunk_token_counts)
        _add_candidate_to_pack(receiver, candidate, chunk_token_counts)


def build_candidate_packs(
    *,
    index_dir: Path,
    candidates_path: Path,
    target_pack_tokens: int,
    min_pack_tokens: int | None = None,
    max_candidates_per_pack: int | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    chunk_rows = _read_chunk_rows(index_dir)
    chunk_by_id = {str(row.get('chunk_id')): row for row in chunk_rows}
    chunk_token_counts = {str(row.get('chunk_id')): int(row.get('token_count', 0)) for row in chunk_rows}
    candidate_rows = read_jsonl(candidates_path)

    prepared = []
    for row in candidate_rows:
        chunk_ids = [str(cid) for cid in row.get('supporting_chunk_ids', []) if str(cid) in chunk_by_id]
        if len(chunk_ids) < 2:
            continue
        unique_chunk_ids = tuple(
            sorted(
                set(chunk_ids),
                key=lambda cid: (str(chunk_by_id[cid].get('source_id') or ''), int(chunk_by_id[cid].get('chunk_index') or 0), cid),
            )
        )
        support_tokens = sum(chunk_token_counts[cid] for cid in unique_chunk_ids)
        prepared.append(
            {
                'row': row,
                'chunk_ids': unique_chunk_ids,
                'support_tokens': support_tokens,
                'candidate_id': str(row.get('candidate_id') or ''),
            }
        )
    min_tokens = int(min_pack_tokens or max(1, target_pack_tokens // 2))

    pack_states = _initial_pack_assignment(
        prepared,
        target_pack_tokens=target_pack_tokens,
        min_tokens=min_tokens,
        max_candidates_per_pack=max_candidates_per_pack,
        chunk_token_counts=chunk_token_counts,
    )
    _rebalance_underfilled_packs(
        pack_states,
        target_pack_tokens=target_pack_tokens,
        min_tokens=min_tokens,
        max_candidates_per_pack=max_candidates_per_pack,
        chunk_token_counts=chunk_token_counts,
    )
    pack_states.sort(key=lambda pack: (int(pack['pack_tokens']), str(pack['seed_candidate_id'])), reverse=True)

    packs: list[dict[str, Any]] = []
    pack_chunk_rows: list[dict[str, Any]] = []
    training_rows: list[dict[str, Any]] = []
    for pack_index, pack in enumerate(pack_states, start=1):
        ordered_chunk_rows = [
            _chunk_locator(chunk_by_id[cid])
            for cid in sorted(
                pack['chunk_ids'],
                key=lambda cid: (str(chunk_by_id[cid].get('source_id') or ''), int(chunk_by_id[cid].get('chunk_index') or 0), cid),
            )
        ]
        pack_candidates = sorted(pack['candidates'], key=_candidate_sort_key, reverse=True)
        pack_id = stable_id('lccp', f'pack_{pack_index}', str(target_pack_tokens), '|'.join(row['candidate_id'] for row in pack_candidates))
        candidate_payload = []
        prompt_lines = [
            'You are given a very long evidence pack assembled from papers, repositories, and traces.',
            'Answer each query using only the supplied evidence.',
            '',
            'PACK_QUERIES:',
        ]
        target_rows = []
        for query_index, prepared_row in enumerate(pack_candidates, start=1):
            row = prepared_row['row']
            state_variable = str(row.get('state_variable') or f"{row.get('canonical_name')}_active")
            query_text = f"[{query_index}] What is the final value of `{state_variable}` after reconciling all evidence?"
            prompt_lines.append(query_text)
            candidate_payload.append(
                {
                    'candidate_id': prepared_row['candidate_id'],
                    'canonical_name': str(row.get('canonical_name') or ''),
                    'support_token_count': int(prepared_row['support_tokens']),
                    'supporting_chunk_ids': list(prepared_row['chunk_ids']),
                    'query_text': query_text,
                    'final_state': dict(row.get('final_state') or {}),
                    'model_assisted_signals': dict(row.get('model_assisted_signals') or {}),
                }
            )
            target_rows.append(
                {
                    'query_index': query_index,
                    'candidate_id': prepared_row['candidate_id'],
                    'canonical_name': str(row.get('canonical_name') or ''),
                    'final_state': dict(row.get('final_state') or {}),
                    'state_variable': state_variable,
                }
            )
        pack_row = {
            'pack_id': pack_id,
            'target_pack_tokens': int(target_pack_tokens),
            'min_pack_tokens': int(min_tokens),
            'pack_token_count': int(pack['pack_tokens']),
            'meets_min_pack_tokens': bool(int(pack['pack_tokens']) >= min_tokens),
            'chunk_count': len(ordered_chunk_rows),
            'candidate_count': len(candidate_payload),
            'candidate_ids': [row['candidate_id'] for row in candidate_payload],
            'ordered_chunk_ids': [row['chunk_id'] for row in ordered_chunk_rows],
            'candidates': candidate_payload,
            'source_mix': _source_mix(ordered_chunk_rows),
        }
        packs.append(pack_row)
        training_rows.append(
            {
                'pack_id': pack_id,
                'prompt_text': '\n'.join(prompt_lines),
                'target_rows': target_rows,
                'context_rows': [
                    {
                        'chunk_ordinal': ordinal,
                        'chunk_id': row['chunk_id'],
                        'source_type': row['source_type'],
                        'path': row['path'],
                        'token_count': row['token_count'],
                        'text': row['text'],
                    }
                    for ordinal, row in enumerate(ordered_chunk_rows, start=1)
                ],
                'pack_token_count': int(pack['pack_tokens']),
                'chunk_count': len(ordered_chunk_rows),
                'candidate_count': len(candidate_payload),
            }
        )
        for ordinal, chunk_row in enumerate(ordered_chunk_rows, start=1):
            pack_chunk_rows.append({'pack_id': pack_id, 'chunk_ordinal': ordinal, **chunk_row})

    underfilled_pack_ids = [str(pack.get('pack_id') or '') for pack in packs if not pack.get('meets_min_pack_tokens', False)]
    summary = {
        'pack_count': len(packs),
        'target_pack_tokens': int(target_pack_tokens),
        'min_pack_tokens': int(min_tokens),
        'total_candidates_consumed': sum(len(pack.get('candidates', [])) for pack in packs),
        'total_unique_chunks_across_packs': len({row.get('chunk_id') for row in pack_chunk_rows}),
        'training_row_count': len(training_rows),
        'packs_meeting_min_tokens': len(packs) - len(underfilled_pack_ids),
        'underfilled_pack_count': len(underfilled_pack_ids),
        'underfilled_pack_ids': underfilled_pack_ids,
        'pack_token_count_stats': {
            'min': min((int(pack.get('pack_token_count', 0)) for pack in packs), default=0),
            'max': max((int(pack.get('pack_token_count', 0)) for pack in packs), default=0),
            'avg': (sum(int(pack.get('pack_token_count', 0)) for pack in packs) / len(packs)) if packs else 0.0,
        },
    }
    return packs, pack_chunk_rows, training_rows, summary


def main() -> None:
    parser = argparse.ArgumentParser(description='Build long-context training packs directly from candidate support chunks.')
    parser.add_argument('--index-dir', type=Path, required=True)
    parser.add_argument('--candidates', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--target-pack-tokens', type=int, required=True)
    parser.add_argument('--min-pack-tokens', type=int)
    parser.add_argument('--max-candidates-per-pack', type=int)
    parser.add_argument(
        '--fail-on-underfilled-pack',
        action='store_true',
        help='Exit with an error if any produced pack is below min-pack-tokens.',
    )
    args = parser.parse_args()
    packs, pack_chunk_rows, training_rows, summary = build_candidate_packs(
        index_dir=args.index_dir,
        candidates_path=args.candidates,
        target_pack_tokens=args.target_pack_tokens,
        min_pack_tokens=args.min_pack_tokens,
        max_candidates_per_pack=args.max_candidates_per_pack,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.output_dir / 'candidate_packs.jsonl', packs)
    write_jsonl(args.output_dir / 'candidate_pack_training_rows.jsonl', training_rows)
    write_json(args.output_dir / 'candidate_packs_summary.json', summary)
    write_parquet_shard(shard_path(args.output_dir / 'parquet', 'candidate_packs', 0), _parquet_safe_candidate_packs(packs))
    write_parquet_shard(shard_path(args.output_dir / 'parquet', 'candidate_pack_chunks', 0), pack_chunk_rows)
    write_parquet_shard(shard_path(args.output_dir / 'parquet', 'candidate_pack_training_rows', 0), _parquet_safe_training_rows(training_rows))
    if args.fail_on_underfilled_pack and summary.get('underfilled_pack_count', 0):
        raise SystemExit(
            f"Produced {summary['underfilled_pack_count']} underfilled pack(s): {', '.join(summary['underfilled_pack_ids'])}"
        )


if __name__ == '__main__':
    main()
