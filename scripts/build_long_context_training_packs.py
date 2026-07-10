from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from long_context_common import read_jsonl, stable_id, write_json, write_jsonl


SOURCE_PRIORITY = {'local_repo': 0, 'repo': 1, 'paper': 2, 'dataset': 3}
ROLE_PRIORITY = {'verification_constraint': 0, 'seed_change': 1, 'test_neighbor': 2, 'repo_graph_neighbor': 3, 'cross_repo_analogue': 4, 'algorithm_grounding': 5, 'trace_analogue': 6}
from long_context_parquet import shard_path, write_parquet_shard


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


def _chunk_locator_from_context_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'chunk_id': str(row.get('chunk_id') or ''),
        'source_type': str(row.get('source_type') or ''),
        'source_id': str(row.get('source_id') or ''),
        'doc_id': str(row.get('doc_id') or row.get('path') or row.get('abs_path') or ''),
        'chunk_index': int(row.get('chunk_index') or 0),
        'token_count': int(row.get('token_count') or 0),
        'path': str(row.get('path') or ''),
        'language': row.get('language'),
        'modality': str(row.get('modality') or ''),
        'role': str(row.get('role') or ''),
        'retrieval_reason': str(row.get('retrieval_reason') or ''),
        'text': str(row.get('text') or ''),
    }


def _chunk_sort_key(row: dict[str, Any]) -> tuple[int, int, str, int, str]:
    return (
        SOURCE_PRIORITY.get(str(row.get('source_type') or ''), 9),
        ROLE_PRIORITY.get(str(row.get('role') or ''), 9),
        str(row.get('source_id') or ''),
        int(row.get('chunk_index') or 0),
        str(row.get('chunk_id') or ''),
    )


def _example_chunk_set(example: dict[str, Any]) -> set[str]:
    rendered = {str(chunk_id) for chunk_id in example.get('rendered_chunk_ids', []) if str(chunk_id)}
    if rendered:
        return rendered
    return {str(row.get('chunk_id') or '') for row in example.get('context_rows', []) if str(row.get('chunk_id') or '')}


def _pack_token_count(chunk_ids: set[str], chunk_token_counts: dict[str, int]) -> int:
    return sum(int(chunk_token_counts.get(chunk_id, 0)) for chunk_id in chunk_ids)


def _novel_token_count(base_chunk_ids: set[str], candidate_chunk_ids: set[str], chunk_token_counts: dict[str, int]) -> int:
    return sum(int(chunk_token_counts.get(chunk_id, 0)) for chunk_id in candidate_chunk_ids if chunk_id not in base_chunk_ids)


def _source_mix(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get('source_type') or 'unknown')
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _pick_seed(entries: list[dict[str, Any]]) -> dict[str, Any]:
    return max(entries, key=lambda row: (int(row.get('context_token_count', 0)), str(row.get('example_id') or '')))


def _overlap_score(base_chunks: set[str], candidate_chunks: set[str]) -> tuple[int, int]:
    overlap = len(base_chunks & candidate_chunks)
    novel = len(candidate_chunks - base_chunks)
    return overlap, -novel


def _use_fast_fill_strategy(*, target_pack_tokens: int, remaining_count: int) -> bool:
    return target_pack_tokens >= 1_000_000 or remaining_count >= 256


def _family_key(example: dict[str, Any], family_key_field: str | None) -> str:
    if not family_key_field:
        return ''
    value = example.get(family_key_field)
    if value is None and isinstance(example.get('metadata'), dict):
        value = dict(example.get('metadata') or {}).get(family_key_field)
    return str(value or '')


def _build_entries(examples: list[dict[str, Any]], family_key_field: str | None) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for row in examples:
        chunk_ids = _example_chunk_set(row)
        if not chunk_ids:
            continue
        entries.append(
            {
                'row': row,
                'chunk_ids': chunk_ids,
                'context_token_count': int(row.get('context_token_count', 0)),
                'example_id': str(row.get('example_id') or ''),
                'family_key': _family_key(row, family_key_field),
            }
        )
    return entries


def _family_seed_plan(entries: list[dict[str, Any]], *, max_packs: int | None) -> list[dict[str, Any]]:
    by_family: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        family = str(entry.get('family_key') or '')
        if not family:
            continue
        by_family.setdefault(family, []).append(entry)
    seeds = [_pick_seed(group) for group in by_family.values()]
    seeds.sort(key=lambda row: (int(row.get('context_token_count', 0)), str(row.get('family_key') or ''), str(row.get('example_id') or '')), reverse=True)
    if max_packs is not None:
        return seeds[:max_packs]
    return seeds


def _candidate_pool(
    entries: list[dict[str, Any]],
    *,
    pack_example_ids: set[str],
    consumed_ids: set[str],
    allow_example_reuse: bool,
) -> list[dict[str, Any]]:
    return [
        entry
        for entry in entries
        if entry['example_id'] not in pack_example_ids and (allow_example_reuse or entry['example_id'] not in consumed_ids)
    ]


def _choose_candidate(
    candidates: list[dict[str, Any]],
    *,
    pack_chunk_ids: set[str],
    pack_tokens: int,
    target_pack_tokens: int,
    seed_family_key: str,
) -> tuple[dict[str, Any] | None, int]:
    if not candidates:
        return None, pack_tokens
    if _use_fast_fill_strategy(target_pack_tokens=target_pack_tokens, remaining_count=len(candidates)):
        ranked_candidates: list[tuple[tuple[int, int, int, str], dict[str, Any], int]] = []
        for candidate_entry in candidates:
            candidate_chunk_ids = candidate_entry['chunk_ids']
            novel_tokens = _novel_token_count(pack_chunk_ids, candidate_chunk_ids, CHUNK_TOKEN_COUNTS)
            merged_tokens = pack_tokens + novel_tokens
            if merged_tokens > target_pack_tokens:
                continue
            ranked_candidates.append(
                (
                    (
                        novel_tokens,
                        int(bool(seed_family_key and candidate_entry.get('family_key') == seed_family_key)),
                        int(candidate_entry.get('context_token_count') or 0),
                        str(candidate_entry.get('example_id') or ''),
                    ),
                    candidate_entry,
                    merged_tokens,
                )
            )
        if not ranked_candidates:
            return None, pack_tokens
        ranked_candidates.sort(key=lambda item: item[0], reverse=True)
        _, chosen_entry, merged_tokens = ranked_candidates[0]
        return chosen_entry, merged_tokens

    ranked_candidates: list[tuple[tuple[int, int, int, int], dict[str, Any], int]] = []
    for candidate_entry in candidates:
        candidate_chunk_ids = candidate_entry['chunk_ids']
        novel_tokens = _novel_token_count(pack_chunk_ids, candidate_chunk_ids, CHUNK_TOKEN_COUNTS)
        merged_tokens = pack_tokens + novel_tokens
        if merged_tokens > target_pack_tokens:
            continue
        overlap_rank = _overlap_score(pack_chunk_ids, candidate_chunk_ids)
        same_family = int(bool(seed_family_key and candidate_entry.get('family_key') == seed_family_key))
        ranked_candidates.append(
            (
                (same_family, overlap_rank[0], overlap_rank[1], int(candidate_entry.get('context_token_count') or 0)),
                candidate_entry,
                merged_tokens,
            )
        )
    if not ranked_candidates:
        return None, pack_tokens
    ranked_candidates.sort(key=lambda item: (item[0], str(item[1].get('example_id') or '')), reverse=True)
    _, chosen_entry, merged_tokens = ranked_candidates[0]
    return chosen_entry, merged_tokens


def _pack_training_row(pack_row: dict[str, Any], ordered_chunk_rows: list[dict[str, Any]]) -> dict[str, Any]:
    prompt_lines = [
        'You are given a very long context assembled from papers, repositories, and traces.',
        'Answer all pack queries using only the provided evidence.',
        '',
        'PACK_QUERIES:',
    ]
    target_rows = []
    for index, example in enumerate(pack_row.get('examples', []), start=1):
        query = dict(example.get('query') or {})
        targets = dict(example.get('targets') or {})
        prompt_lines.append(f"[{index}] {str(query.get('text') or '')}")
        target_rows.append(
            {
                'query_index': index,
                'example_id': str(example.get('example_id') or ''),
                'program_id': str(example.get('program_id') or ''),
                'final_answer': targets.get('final_answer'),
                'final_state_json': str(targets.get('final_state_json') or json.dumps(dict(targets.get('final_state') or {}), sort_keys=True)),
            }
        )
    context_rows = []
    for ordinal, row in enumerate(ordered_chunk_rows, start=1):
        context_row = {
            'chunk_ordinal': ordinal,
            'chunk_id': row['chunk_id'],
            'source_type': row['source_type'],
            'source_id': row.get('source_id', ''),
            'doc_id': row.get('doc_id', ''),
            'path': row['path'],
            'token_count': row['token_count'],
            'text': row['text'],
        }
        for optional_key in ('role', 'retrieval_reason', 'language', 'modality'):
            value = row.get(optional_key)
            if value not in (None, ''):
                context_row[optional_key] = value
        context_rows.append(context_row)
    return {
        'pack_id': pack_row['pack_id'],
        'prompt_text': '\n'.join(prompt_lines),
        'target_rows': target_rows,
        'context_rows': context_rows,
        'pack_token_count': int(pack_row.get('pack_token_count', 0)),
        'chunk_count': int(pack_row.get('chunk_count', 0)),
        'example_count': int(pack_row.get('example_count', 0)),
    }


CHUNK_TOKEN_COUNTS: dict[str, int] = {}


def build_long_context_packs(
    *,
    index_dir: Path | None,
    examples_path: Path,
    target_pack_tokens: int,
    min_pack_tokens: int | None = None,
    max_examples_per_pack: int | None = None,
    allow_example_reuse: bool = False,
    family_key_field: str | None = None,
    max_packs: int | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    global CHUNK_TOKEN_COUNTS

    examples = read_jsonl(examples_path)
    direct_context_mode = any(isinstance(row.get('context_rows'), list) and row.get('context_rows') for row in examples)
    if direct_context_mode:
        chunk_by_id: dict[str, dict[str, Any]] = {}
        chunk_token_counts: dict[str, int] = {}
        for example in examples:
            for row in example.get('context_rows', []):
                chunk = _chunk_locator_from_context_row(dict(row))
                chunk_id = str(chunk.get('chunk_id') or '')
                if not chunk_id or chunk_id in chunk_by_id:
                    continue
                chunk_by_id[chunk_id] = chunk
                chunk_token_counts[chunk_id] = int(chunk.get('token_count') or 0)
    else:
        if index_dir is None:
            raise ValueError('index_dir_required_when_examples_lack_context_rows')
        chunk_rows = _read_chunk_rows(index_dir)
        chunk_by_id = {str(row.get('chunk_id')): _chunk_locator(row) for row in chunk_rows}
        chunk_token_counts = {str(row.get('chunk_id')): int(row.get('token_count', 0)) for row in chunk_rows}
    CHUNK_TOKEN_COUNTS = chunk_token_counts

    entries = _build_entries(examples, family_key_field)
    min_tokens = int(min_pack_tokens or max(1, target_pack_tokens // 2))

    packs: list[dict[str, Any]] = []
    pack_chunk_rows: list[dict[str, Any]] = []
    training_rows: list[dict[str, Any]] = []
    consumed_ids: set[str] = set()
    emitted_chunk_signatures: set[tuple[str, ...]] = set()
    duplicate_pack_count = 0
    pack_index = 0

    if allow_example_reuse and family_key_field:
        seed_plan = _family_seed_plan(entries, max_packs=max_packs)
        if not seed_plan:
            seed_plan = sorted(entries, key=lambda row: (int(row.get('context_token_count', 0)), str(row.get('example_id') or '')), reverse=True)
    else:
        seed_plan = []

    def emit_pack(seed_entry: dict[str, Any]) -> None:
        nonlocal pack_index
        pack_index += 1
        seed_family_key = str(seed_entry.get('family_key') or '')
        pack_examples = [seed_entry['row']]
        pack_example_ids = {seed_entry['example_id']}
        pack_chunk_ids = set(seed_entry['chunk_ids'])
        pack_tokens = _pack_token_count(pack_chunk_ids, chunk_token_counts)

        while pack_tokens < target_pack_tokens:
            candidates = _candidate_pool(
                entries,
                pack_example_ids=pack_example_ids,
                consumed_ids=consumed_ids,
                allow_example_reuse=allow_example_reuse,
            )
            chosen_entry, merged_tokens = _choose_candidate(
                candidates,
                pack_chunk_ids=pack_chunk_ids,
                pack_tokens=pack_tokens,
                target_pack_tokens=target_pack_tokens,
                seed_family_key=seed_family_key,
            )
            if chosen_entry is None:
                break
            pack_examples.append(chosen_entry['row'])
            pack_example_ids.add(chosen_entry['example_id'])
            pack_chunk_ids |= chosen_entry['chunk_ids']
            pack_tokens = merged_tokens
            if max_examples_per_pack is not None and len(pack_examples) >= max_examples_per_pack:
                break

        if pack_tokens < min_tokens:
            candidates = _candidate_pool(
                entries,
                pack_example_ids=pack_example_ids,
                consumed_ids=consumed_ids,
                allow_example_reuse=allow_example_reuse,
            )
            if candidates:
                chosen_entry = _pick_seed(candidates)
                pack_examples.append(chosen_entry['row'])
                pack_example_ids.add(chosen_entry['example_id'])
                chosen_chunk_ids = chosen_entry['chunk_ids']
                pack_tokens += _novel_token_count(pack_chunk_ids, chosen_chunk_ids, chunk_token_counts)
                pack_chunk_ids |= chosen_chunk_ids

        if not allow_example_reuse:
            consumed_ids.update(pack_example_ids)

        pack_id = stable_id('lcp', f'pack_{pack_index}', str(target_pack_tokens), '|'.join(str(row.get('example_id')) for row in pack_examples))
        ordered_chunk_rows = [
            chunk_by_id[chunk_id]
            for chunk_id in sorted(
                pack_chunk_ids,
                key=lambda cid: _chunk_sort_key(chunk_by_id[cid]),
            )
            if chunk_id in chunk_by_id
        ]
        pack_examples_payload = [
            {
                'example_id': str(example.get('example_id') or ''),
                'program_id': str(example.get('program_id') or ''),
                'context_token_count': int(example.get('context_token_count', 0)),
                'query': dict(example.get('query') or {}),
                'targets': {
                    'final_answer': dict(example.get('targets') or {}).get('final_answer'),
                    'final_state_json': str(dict(example.get('targets') or {}).get('final_state_json') or json.dumps(dict(dict(example.get('targets') or {}).get('final_state') or {}), sort_keys=True)),
                },
                'difficulty': dict(example.get('difficulty') or {}),
                'quality': dict(example.get('quality') or {}),
                'family_key': _family_key(example, family_key_field),
            }
            for example in pack_examples
        ]
        chunk_signature = tuple(row['chunk_id'] for row in ordered_chunk_rows)
        nonlocal duplicate_pack_count
        if chunk_signature in emitted_chunk_signatures:
            duplicate_pack_count += 1
            return
        emitted_chunk_signatures.add(chunk_signature)
        pack_row = {
            'pack_id': pack_id,
            'target_pack_tokens': int(target_pack_tokens),
            'min_pack_tokens': int(min_tokens),
            'pack_token_count': int(pack_tokens),
            'chunk_count': len(ordered_chunk_rows),
            'example_count': len(pack_examples_payload),
            'example_ids': [row['example_id'] for row in pack_examples_payload],
            'program_ids': [row['program_id'] for row in pack_examples_payload],
            'ordered_chunk_ids': [row['chunk_id'] for row in ordered_chunk_rows],
            'examples': pack_examples_payload,
            'source_mix': _source_mix(ordered_chunk_rows),
            'seed_family_key': seed_family_key,
        }
        packs.append(pack_row)
        training_rows.append(_pack_training_row(pack_row, ordered_chunk_rows))
        for ordinal, chunk_row in enumerate(ordered_chunk_rows, start=1):
            pack_chunk_rows.append(
                {
                    'pack_id': pack_id,
                    'chunk_ordinal': ordinal,
                    **chunk_row,
                }
            )

    if seed_plan:
        for seed_entry in seed_plan:
            emit_pack(seed_entry)
    else:
        while True:
            available = [entry for entry in entries if entry['example_id'] not in consumed_ids]
            if not available:
                break
            emit_pack(_pick_seed(available))
            if max_packs is not None and len(packs) >= max_packs:
                break

    summary = {
        'pack_count': len(packs),
        'target_pack_tokens': int(target_pack_tokens),
        'min_pack_tokens': int(min_tokens),
        'total_examples_consumed': sum(len(pack.get('examples', [])) for pack in packs),
        'total_unique_chunks_across_packs': len({chunk.get('chunk_id') for chunk in pack_chunk_rows}),
        'training_row_count': len(training_rows),
        'chunk_source_mode': 'direct_context_rows' if direct_context_mode else 'indexed_chunks',
        'duplicate_pack_count': int(duplicate_pack_count),
        'allow_example_reuse': bool(allow_example_reuse),
        'family_key_field': str(family_key_field or ''),
        'max_packs': int(max_packs) if max_packs is not None else None,
        'pack_token_count_stats': {
            'min': min((int(pack.get('pack_token_count', 0)) for pack in packs), default=0),
            'max': max((int(pack.get('pack_token_count', 0)) for pack in packs), default=0),
            'avg': (sum(int(pack.get('pack_token_count', 0)) for pack in packs) / len(packs)) if packs else 0.0,
        },
    }
    return packs, pack_chunk_rows, training_rows, summary


def main() -> None:
    parser = argparse.ArgumentParser(description='Build multi-example long-context training packs from rendered examples and corpus chunks.')
    parser.add_argument('--index-dir', type=Path)
    parser.add_argument('--examples', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--target-pack-tokens', type=int, required=True)
    parser.add_argument('--min-pack-tokens', type=int)
    parser.add_argument('--max-examples-per-pack', type=int)
    parser.add_argument('--allow-example-reuse', action='store_true')
    parser.add_argument('--family-key-field', type=str)
    parser.add_argument('--max-packs', type=int)
    args = parser.parse_args()

    packs, pack_chunk_rows, training_rows, summary = build_long_context_packs(
        index_dir=args.index_dir,
        examples_path=args.examples,
        target_pack_tokens=args.target_pack_tokens,
        min_pack_tokens=args.min_pack_tokens,
        max_examples_per_pack=args.max_examples_per_pack,
        allow_example_reuse=args.allow_example_reuse,
        family_key_field=args.family_key_field,
        max_packs=args.max_packs,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.output_dir / 'long_context_packs.jsonl', packs)
    write_jsonl(args.output_dir / 'long_context_pack_training_rows.jsonl', training_rows)
    write_json(args.output_dir / 'long_context_packs_summary.json', summary)
    write_parquet_shard(shard_path(args.output_dir / 'parquet', 'long_context_packs', 0), packs)
    write_parquet_shard(shard_path(args.output_dir / 'parquet', 'long_context_pack_chunks', 0), pack_chunk_rows)
    write_parquet_shard(shard_path(args.output_dir / 'parquet', 'long_context_pack_training_rows', 0), training_rows)


if __name__ == '__main__':
    main()
