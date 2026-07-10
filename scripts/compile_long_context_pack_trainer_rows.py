from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from long_context_common import write_json
from materialize_trainer_setup import read_jsonl


def _full_context_target_text(target_rows: list[dict[str, Any]]) -> str:
    lines = []
    for row in target_rows:
        state_variable = str(row.get('state_variable') or '')
        final_state = row.get('final_state') if isinstance(row.get('final_state'), dict) else {}
        lines.append(json.dumps({'state_variable': state_variable, 'final_state': final_state}, sort_keys=True))
    return "\n".join(lines)


def _query_text(target_row: dict[str, Any]) -> str:
    query_index = int(target_row.get('query_index') or 0)
    state_variable = str(target_row.get('state_variable') or '')
    return f"[{query_index}] What is the final value of `{state_variable}` after reconciling all evidence?"


def _positive_chunk_ids(target_row: dict[str, Any], context_rows: list[dict[str, Any]], *, max_positive_chunks: int) -> list[str]:
    canonical = str(target_row.get('canonical_name') or '').lower()
    state_variable = str(target_row.get('state_variable') or '').lower()
    canonical_terms = [term for term in canonical.replace('_', ' ').split() if term]
    selected: list[str] = []
    for row in context_rows:
        hay = " ".join([str(row.get('path') or '').lower(), str(row.get('text') or '').lower()])
        if state_variable and state_variable in hay:
            selected.append(str(row.get('chunk_id') or ''))
            continue
        if canonical_terms and all(term in hay for term in canonical_terms):
            selected.append(str(row.get('chunk_id') or ''))
    if not selected:
        selected = [str(row.get('chunk_id') or '') for row in context_rows[: max(1, min(3, max_positive_chunks))]]
    return selected[:max_positive_chunks]


def _memory_target(row: dict[str, Any], target_rows: list[dict[str, Any]], context_rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'pack_id': str(row.get('pack_id') or ''),
        'trainer_policy_mode': str(row.get('trainer_policy_mode') or ''),
        'overlap_family_id': str(row.get('overlap_family_id') or ''),
        'candidate_count': int(row.get('candidate_count') or 0),
        'chunk_count': int(row.get('chunk_count') or 0),
        'state_variables': [str(item.get('state_variable') or '') for item in target_rows],
        'canonical_names': [str(item.get('canonical_name') or '') for item in target_rows],
        'source_types': sorted({str(item.get('source_type') or '') for item in context_rows}),
    }


def compile_long_context_pack_trainer_rows(
    *,
    trainer_rows_path: Path,
    max_positive_chunks: int = 8,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    trainer_rows = read_jsonl(trainer_rows_path)
    full_context_rows: list[dict[str, Any]] = []
    retrieval_rows: list[dict[str, Any]] = []
    memory_rows: list[dict[str, Any]] = []
    split_counts: Counter[str] = Counter()
    mode_counts: Counter[str] = Counter()

    for row in trainer_rows:
        pack_id = str(row.get('pack_id') or '')
        effective_split = str(row.get('effective_split') or 'train')
        trainer_policy_mode = str(row.get('trainer_policy_mode') or '')
        prompt_text = str(row.get('prompt_text') or '')
        context_rows = list(row.get('context_rows') or [])
        target_rows = list(row.get('target_rows') or [])
        split_counts[effective_split] += 1
        mode_counts[trainer_policy_mode] += 1

        full_context_rows.append(
            {
                'row_id': f'full::{pack_id}',
                'pack_id': pack_id,
                'task_type': 'full_context_state_reconstruction',
                'effective_split': effective_split,
                'trainer_policy_mode': trainer_policy_mode,
                'overlap_family_id': str(row.get('overlap_family_id') or ''),
                'prompt_text': prompt_text,
                'context_rows': context_rows,
                'target_text': _full_context_target_text(target_rows),
                'metadata': {
                    'candidate_count': int(row.get('candidate_count') or 0),
                    'chunk_count': int(row.get('chunk_count') or 0),
                    'pack_token_count': int(row.get('pack_token_count') or 0),
                },
            }
        )

        for target_row in target_rows:
            retrieval_rows.append(
                {
                    'row_id': f"retrieval::{pack_id}::{int(target_row.get('query_index') or 0)}",
                    'pack_id': pack_id,
                    'task_type': 'retrieval_supervision',
                    'effective_split': effective_split,
                    'trainer_policy_mode': trainer_policy_mode,
                    'overlap_family_id': str(row.get('overlap_family_id') or ''),
                    'query_text': _query_text(target_row),
                    'positive_chunk_ids': _positive_chunk_ids(target_row, context_rows, max_positive_chunks=max_positive_chunks),
                    'target_text': json.dumps({'final_state': target_row.get('final_state') or {}, 'state_variable': target_row.get('state_variable') or ''}, sort_keys=True),
                    'metadata': {
                        'canonical_name': str(target_row.get('canonical_name') or ''),
                        'query_index': int(target_row.get('query_index') or 0),
                    },
                }
            )

        memory_rows.append(
            {
                'row_id': f'memory::{pack_id}',
                'pack_id': pack_id,
                'task_type': 'state_summary_compression',
                'effective_split': effective_split,
                'trainer_policy_mode': trainer_policy_mode,
                'overlap_family_id': str(row.get('overlap_family_id') or ''),
                'input_text': f"Summarize the persistent working memory for pack {pack_id}.",
                'target_text': json.dumps(_memory_target(row, target_rows, context_rows), sort_keys=True),
                'metadata': {
                    'candidate_count': int(row.get('candidate_count') or 0),
                    'chunk_count': int(row.get('chunk_count') or 0),
                },
            }
        )

    buckets = {
        'full_context_rows': full_context_rows,
        'retrieval_rows': retrieval_rows,
        'memory_rows': memory_rows,
    }
    summary = {
        'trainer_rows': len(trainer_rows),
        'full_context_rows': len(full_context_rows),
        'retrieval_rows': len(retrieval_rows),
        'memory_rows': len(memory_rows),
        'effective_split_counts': dict(sorted(split_counts.items())),
        'trainer_policy_mode_counts': dict(sorted(mode_counts.items())),
        'max_positive_chunks': int(max_positive_chunks),
        'full_context_format': 'structured_prompt_plus_context_rows',
    }
    return buckets, summary


def stream_compile_long_context_pack_trainer_rows(
    *,
    trainer_rows_path: Path,
    output_dir: Path,
    max_positive_chunks: int = 8,
) -> dict[str, Any]:
    trainer_rows = read_jsonl(trainer_rows_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    full_context_path = output_dir / 'full_context_rows.jsonl'
    retrieval_path = output_dir / 'retrieval_rows.jsonl'
    memory_path = output_dir / 'memory_rows.jsonl'
    for path in (full_context_path, retrieval_path, memory_path):
        if path.exists():
            path.unlink()

    split_counts: Counter[str] = Counter()
    mode_counts: Counter[str] = Counter()
    retrieval_count = 0

    with full_context_path.open('a', encoding='utf-8') as full_handle, retrieval_path.open('a', encoding='utf-8') as retrieval_handle, memory_path.open('a', encoding='utf-8') as memory_handle:
        for row in trainer_rows:
            pack_id = str(row.get('pack_id') or '')
            effective_split = str(row.get('effective_split') or 'train')
            trainer_policy_mode = str(row.get('trainer_policy_mode') or '')
            prompt_text = str(row.get('prompt_text') or '')
            context_rows = list(row.get('context_rows') or [])
            target_rows = list(row.get('target_rows') or [])
            split_counts[effective_split] += 1
            mode_counts[trainer_policy_mode] += 1

            full_handle.write(json.dumps({
                'row_id': f'full::{pack_id}',
                'pack_id': pack_id,
                'task_type': 'full_context_state_reconstruction',
                'effective_split': effective_split,
                'trainer_policy_mode': trainer_policy_mode,
                'overlap_family_id': str(row.get('overlap_family_id') or ''),
                'prompt_text': prompt_text,
                'context_rows': context_rows,
                'target_text': _full_context_target_text(target_rows),
                'metadata': {
                    'candidate_count': int(row.get('candidate_count') or 0),
                    'chunk_count': int(row.get('chunk_count') or 0),
                    'pack_token_count': int(row.get('pack_token_count') or 0),
                },
            }, sort_keys=True) + '\n')

            for target_row in target_rows:
                retrieval_count += 1
                retrieval_handle.write(json.dumps({
                    'row_id': f"retrieval::{pack_id}::{int(target_row.get('query_index') or 0)}",
                    'pack_id': pack_id,
                    'task_type': 'retrieval_supervision',
                    'effective_split': effective_split,
                    'trainer_policy_mode': trainer_policy_mode,
                    'overlap_family_id': str(row.get('overlap_family_id') or ''),
                    'query_text': _query_text(target_row),
                    'positive_chunk_ids': _positive_chunk_ids(target_row, context_rows, max_positive_chunks=max_positive_chunks),
                    'target_text': json.dumps({'final_state': target_row.get('final_state') or {}, 'state_variable': target_row.get('state_variable') or ''}, sort_keys=True),
                    'metadata': {
                        'canonical_name': str(target_row.get('canonical_name') or ''),
                        'query_index': int(target_row.get('query_index') or 0),
                    },
                }, sort_keys=True) + '\n')

            memory_handle.write(json.dumps({
                'row_id': f'memory::{pack_id}',
                'pack_id': pack_id,
                'task_type': 'state_summary_compression',
                'effective_split': effective_split,
                'trainer_policy_mode': trainer_policy_mode,
                'overlap_family_id': str(row.get('overlap_family_id') or ''),
                'input_text': f"Summarize the persistent working memory for pack {pack_id}.",
                'target_text': json.dumps(_memory_target(row, target_rows, context_rows), sort_keys=True),
                'metadata': {
                    'candidate_count': int(row.get('candidate_count') or 0),
                    'chunk_count': int(row.get('chunk_count') or 0),
                },
            }, sort_keys=True) + '\n')

    summary = {
        'trainer_rows': len(trainer_rows),
        'full_context_rows': len(trainer_rows),
        'retrieval_rows': retrieval_count,
        'memory_rows': len(trainer_rows),
        'effective_split_counts': dict(sorted(split_counts.items())),
        'trainer_policy_mode_counts': dict(sorted(mode_counts.items())),
        'max_positive_chunks': int(max_positive_chunks),
        'full_context_format': 'structured_prompt_plus_context_rows',
    }
    write_json(output_dir / 'compile_card.json', summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description='Compile long-context pack trainer rows into model-consumable training shards.')
    parser.add_argument('--trainer-rows', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--max-positive-chunks', type=int, default=8)
    args = parser.parse_args()
    stream_compile_long_context_pack_trainer_rows(
        trainer_rows_path=args.trainer_rows,
        output_dir=args.output_dir,
        max_positive_chunks=args.max_positive_chunks,
    )


if __name__ == '__main__':
    main()
