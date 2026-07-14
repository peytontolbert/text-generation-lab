from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from long_context_common import write_json, write_jsonl

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET_CARD_PATH = ROOT / 'runs' / 'local' / 'artifacts' / 'strict_long_context_train_ready_v1' / 'strict_long_context_training_dataset_card.json'
DEFAULT_OUTPUT_DIR = ROOT / 'runs' / 'local' / 'artifacts' / 'strict_long_context_retrieval_datasets_v1'
MAX_PAIRWISE_NEGATIVES_PER_POS = 4


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open('r', encoding='utf-8') as handle:
        for line in handle:
            if not line.strip():
                continue
            rows.append(json.loads(line))
    return rows


def _resolve_rows_path(rows_path: Path | None, dataset_card_path: Path | None) -> tuple[Path, Path | None]:
    if rows_path is not None:
        resolved_rows_path = rows_path.resolve()
        if not resolved_rows_path.exists():
            raise FileNotFoundError(f'missing_rows_path:{resolved_rows_path}')
        return resolved_rows_path, dataset_card_path.resolve() if dataset_card_path is not None else None
    resolved_dataset_card_path = (dataset_card_path or DEFAULT_DATASET_CARD_PATH).resolve()
    if not resolved_dataset_card_path.exists():
        raise FileNotFoundError(f'missing_dataset_card:{resolved_dataset_card_path}')
    dataset_card = _read_json(resolved_dataset_card_path)
    split_pipeline = dataset_card.get('split_pipeline') or {}
    splits = split_pipeline.get('splits') or {}
    resolved_rows_value = str(splits.get('rows_path') or '').strip()
    if not resolved_rows_value:
        raise ValueError(f'missing_split_pipeline_rows_path:{resolved_dataset_card_path}')
    resolved_rows_path = Path(resolved_rows_value).resolve()
    if not resolved_rows_path.exists():
        raise FileNotFoundError(f'missing_rows_path:{resolved_rows_path}')
    return resolved_rows_path, resolved_dataset_card_path


def _maybe_json(value: Any) -> Any:
    if isinstance(value, str):
        text = value.strip()
        if text.startswith('{') or text.startswith('['):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return value
    return value


def _as_list(value: Any) -> list[Any]:
    parsed = _maybe_json(value)
    return parsed if isinstance(parsed, list) else []


def _as_dict(value: Any) -> dict[str, Any]:
    parsed = _maybe_json(value)
    return parsed if isinstance(parsed, dict) else {}


def _retrieval_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for row in rows:
        if str(row.get('mixture_surface') or '') == 'retrieval_rows' or str(row.get('task_type') or '') == 'retrieval_supervision':
            selected.append(dict(row))
    return selected


def _chunk_support_map(row: dict[str, Any]) -> dict[str, dict[str, Any]]:
    mapping: dict[str, dict[str, Any]] = {}
    for item in _as_list(row.get('support_scores')):
        if not isinstance(item, dict):
            continue
        chunk_id = str(item.get('chunk_id') or '').strip()
        if not chunk_id:
            continue
        mapping[chunk_id] = dict(item)
    return mapping


def build_strict_retriever_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    retrieval_rows = _retrieval_rows(rows)
    out: list[dict[str, Any]] = []
    split_counts: dict[str, int] = {}
    join_type_counts: dict[str, int] = {}
    for row in retrieval_rows:
        split = str(row.get('split') or row.get('effective_split') or 'train')
        join_type = str(row.get('join_type') or '')
        support_map = _chunk_support_map(row)
        positive_ids = [str(value) for value in _as_list(row.get('positive_chunk_ids')) if str(value).strip()]
        hard_negative_ids = [str(value) for value in _as_list(row.get('hard_negative_chunk_ids')) if str(value).strip()]
        positives = [support_map.get(chunk_id, {'chunk_id': chunk_id}) for chunk_id in positive_ids]
        hard_negatives = [support_map.get(chunk_id, {'chunk_id': chunk_id}) for chunk_id in hard_negative_ids]
        out.append({
            'retriever_example_id': str(row.get('mixture_row_id') or row.get('row_id') or ''),
            'pack_id': str(row.get('pack_id') or ''),
            'split': split,
            'query_text': str(row.get('query_text') or ''),
            'target_text': str(row.get('target_text') or ''),
            'positive_chunk_ids': positive_ids,
            'hard_negative_chunk_ids': hard_negative_ids,
            'positive_chunks': positives,
            'hard_negative_chunks': hard_negatives,
            'join_type': join_type,
            'span_ratio': float(row.get('span_ratio') or 0.0),
            'source_type_count': int(row.get('source_type_count') or 0),
            'requires_test_join': bool(row.get('requires_test_join')),
            'requires_session_join': bool(row.get('requires_session_join')),
            'requires_external_concept_join': bool(row.get('requires_external_concept_join')),
            'locality_risk': bool(row.get('locality_risk')),
            'long_join_positive': bool(row.get('long_join_positive')),
            'metadata': _as_dict(row.get('metadata')),
        })
        split_counts[split] = split_counts.get(split, 0) + 1
        join_type_counts[join_type] = join_type_counts.get(join_type, 0) + 1
    summary = {
        'retriever_row_count': len(out),
        'split_counts': dict(sorted(split_counts.items())),
        'join_type_counts': dict(sorted(join_type_counts.items())),
    }
    return out, summary


def _row_labels(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'join_type': str(row.get('join_type') or ''),
        'span_ratio': float(row.get('span_ratio') or 0.0),
        'source_type_count': int(row.get('source_type_count') or 0),
        'requires_test_join': bool(row.get('requires_test_join')),
        'requires_session_join': bool(row.get('requires_session_join')),
        'requires_external_concept_join': bool(row.get('requires_external_concept_join')),
        'locality_risk': bool(row.get('locality_risk')),
        'long_join_positive': bool(row.get('long_join_positive')),
    }




def _interleave_candidate_ids(positive_ids: list[str], hard_negative_ids: list[str]) -> list[tuple[str, int]]:
    ordered: list[tuple[str, int]] = []
    max_len = max(len(positive_ids), len(hard_negative_ids))
    for index in range(max_len):
        if index < len(positive_ids):
            ordered.append((positive_ids[index], 1))
        if index < len(hard_negative_ids):
            ordered.append((hard_negative_ids[index], 0))
    return ordered

def build_strict_reranker_pairwise_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    retrieval_rows = _retrieval_rows(rows)
    out: list[dict[str, Any]] = []
    split_counts: dict[str, int] = {}
    for row in retrieval_rows:
        split = str(row.get('split') or row.get('effective_split') or 'train')
        support_map = _chunk_support_map(row)
        labels = _row_labels(row)
        positive_ids = [str(value) for value in _as_list(row.get('positive_chunk_ids')) if str(value).strip()]
        hard_negative_ids = [str(value) for value in _as_list(row.get('hard_negative_chunk_ids')) if str(value).strip()]
        if not positive_ids or not hard_negative_ids:
            continue
        example_root = str(row.get('mixture_row_id') or row.get('row_id') or '')
        limited_negatives = hard_negative_ids[:MAX_PAIRWISE_NEGATIVES_PER_POS]
        for pos_index, positive_id in enumerate(positive_ids, start=1):
            for neg_index, negative_id in enumerate(limited_negatives, start=1):
                out.append({
                    'pairwise_example_id': f'{example_root}::p{pos_index}::n{neg_index}',
                    'retriever_example_id': example_root,
                    'pack_id': str(row.get('pack_id') or ''),
                    'split': split,
                    'query_text': str(row.get('query_text') or ''),
                    'preferred_chunk_id': positive_id,
                    'rejected_chunk_id': negative_id,
                    'preferred_chunk': support_map.get(positive_id, {'chunk_id': positive_id}),
                    'rejected_chunk': support_map.get(negative_id, {'chunk_id': negative_id}),
                    'label': 'preferred_over_negative',
                    **labels,
                })
                split_counts[split] = split_counts.get(split, 0) + 1
    summary = {
        'pairwise_row_count': len(out),
        'split_counts': dict(sorted(split_counts.items())),
    }
    return out, summary


def build_strict_reranker_listwise_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    retrieval_rows = _retrieval_rows(rows)
    out: list[dict[str, Any]] = []
    split_counts: dict[str, int] = {}
    candidate_counts: list[int] = []
    for row in retrieval_rows:
        split = str(row.get('split') or row.get('effective_split') or 'train')
        support_map = _chunk_support_map(row)
        labels = _row_labels(row)
        positive_ids = [str(value) for value in _as_list(row.get('positive_chunk_ids')) if str(value).strip()]
        hard_negative_ids = [str(value) for value in _as_list(row.get('hard_negative_chunk_ids')) if str(value).strip()]
        ordered_candidates = _interleave_candidate_ids(positive_ids, hard_negative_ids)
        if not ordered_candidates:
            continue
        candidates = []
        for index, (chunk_id, label) in enumerate(ordered_candidates, start=1):
            candidates.append({
                'candidate_index': index,
                'chunk_id': chunk_id,
                'label': label,
                'support': support_map.get(chunk_id, {'chunk_id': chunk_id}),
            })
        out.append({
            'listwise_example_id': f"{str(row.get('mixture_row_id') or row.get('row_id') or '')}::list",
            'retriever_example_id': str(row.get('mixture_row_id') or row.get('row_id') or ''),
            'pack_id': str(row.get('pack_id') or ''),
            'split': split,
            'query_text': str(row.get('query_text') or ''),
            'candidates': candidates,
            'positive_chunk_ids': positive_ids,
            'hard_negative_chunk_ids': hard_negative_ids,
            **labels,
        })
        split_counts[split] = split_counts.get(split, 0) + 1
        candidate_counts.append(len(candidates))
    summary = {
        'listwise_row_count': len(out),
        'split_counts': dict(sorted(split_counts.items())),
        'avg_candidate_count': round(sum(candidate_counts) / max(1, len(candidate_counts)), 4),
    }
    return out, summary


def _curriculum_slices(row: dict[str, Any]) -> list[str]:
    join_type = str(row.get('join_type') or 'unknown')
    return [
        f'join_type::{join_type}',
        f'long_join_positive::{int(bool(row.get("long_join_positive")))}',
        f'locality_risk::{int(bool(row.get("locality_risk")))}',
        f'join_type::{join_type}::long_join::{int(bool(row.get("long_join_positive")))}::locality::{int(bool(row.get("locality_risk")))}',
    ]


def build_strict_retriever_curriculum_rows(retriever_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    out: list[dict[str, Any]] = []
    slice_counts: dict[str, int] = {}
    split_counts: dict[str, int] = {}
    for row in retriever_rows:
        split = str(row.get('split') or 'train')
        for curriculum_slice in _curriculum_slices(row):
            out.append({
                'curriculum_example_id': f"{row['retriever_example_id']}::{curriculum_slice}",
                'retriever_example_id': row['retriever_example_id'],
                'pack_id': row['pack_id'],
                'split': split,
                'curriculum_slice': curriculum_slice,
                'query_text': row['query_text'],
                'positive_chunk_ids': list(row.get('positive_chunk_ids') or []),
                'hard_negative_chunk_ids': list(row.get('hard_negative_chunk_ids') or []),
                'join_type': row.get('join_type'),
                'span_ratio': row.get('span_ratio'),
                'source_type_count': row.get('source_type_count'),
                'requires_test_join': row.get('requires_test_join'),
                'requires_session_join': row.get('requires_session_join'),
                'requires_external_concept_join': row.get('requires_external_concept_join'),
                'locality_risk': row.get('locality_risk'),
                'long_join_positive': row.get('long_join_positive'),
            })
            slice_counts[curriculum_slice] = slice_counts.get(curriculum_slice, 0) + 1
            split_counts[split] = split_counts.get(split, 0) + 1
    summary = {
        'curriculum_row_count': len(out),
        'split_counts': dict(sorted(split_counts.items())),
        'slice_counts': dict(sorted(slice_counts.items())),
    }
    return out, summary


def prepare_strict_long_context_retrieval_datasets(*, rows_path: Path | None = None, dataset_card_path: Path | None = DEFAULT_DATASET_CARD_PATH, output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    resolved_rows_path, resolved_dataset_card_path = _resolve_rows_path(rows_path, dataset_card_path)
    rows = _read_jsonl(resolved_rows_path)
    if not rows:
        raise ValueError('empty_rows')
    retriever_rows, retriever_summary = build_strict_retriever_rows(rows)
    reranker_rows, reranker_summary = build_strict_reranker_pairwise_rows(rows)
    listwise_rows, listwise_summary = build_strict_reranker_listwise_rows(rows)
    curriculum_rows, curriculum_summary = build_strict_retriever_curriculum_rows(retriever_rows)
    output_dir.mkdir(parents=True, exist_ok=True)
    retriever_path = output_dir / 'strict_long_context_retriever_rows.jsonl'
    reranker_path = output_dir / 'strict_long_context_reranker_pairwise_rows.jsonl'
    listwise_path = output_dir / 'strict_long_context_reranker_listwise_rows.jsonl'
    curriculum_path = output_dir / 'strict_long_context_retriever_curriculum_rows.jsonl'
    card_path = output_dir / 'strict_long_context_retrieval_datasets_card.json'
    write_jsonl(retriever_path, retriever_rows)
    write_jsonl(reranker_path, reranker_rows)
    write_jsonl(listwise_path, listwise_rows)
    write_jsonl(curriculum_path, curriculum_rows)
    card = {
        'rows_path': str(resolved_rows_path),
        'dataset_card_path': str(resolved_dataset_card_path) if resolved_dataset_card_path is not None else None,
        'output_dir': str(output_dir),
        'retriever_rows_path': str(retriever_path),
        'reranker_pairwise_rows_path': str(reranker_path),
        'reranker_listwise_rows_path': str(listwise_path),
        'retriever_curriculum_rows_path': str(curriculum_path),
        'retriever_summary': retriever_summary,
        'reranker_summary': reranker_summary,
        'listwise_summary': listwise_summary,
        'curriculum_summary': curriculum_summary,
    }
    write_json(card_path, card)
    return card


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Prepare dedicated retriever and reranker datasets from strict long-context retrieval rows.')
    parser.add_argument('--dataset-card', type=Path, default=DEFAULT_DATASET_CARD_PATH)
    parser.add_argument('--rows', type=Path)
    parser.add_argument('--output-dir', type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    prepare_strict_long_context_retrieval_datasets(rows_path=args.rows, dataset_card_path=args.dataset_card, output_dir=args.output_dir)


if __name__ == '__main__':
    main()
