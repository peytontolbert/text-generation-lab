from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from long_context_common import write_json, write_jsonl

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET_CARD_PATH = ROOT / 'runs' / 'local' / 'artifacts' / 'strict_long_context_train_ready_v1' / 'strict_long_context_training_dataset_card.json'
DEFAULT_OUTPUT_DIR = ROOT / 'runs' / 'local' / 'artifacts' / 'strict_long_context_step_judgment_datasets_v1'
MAX_NEGATIVE_PREFERENCES_PER_STATE = 4


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
        if chunk_id:
            mapping[chunk_id] = dict(item)
    return mapping


def _clamp_score(value: int) -> int:
    return max(0, min(4, int(value)))


def _score_positive_candidate(support: dict[str, Any], row: dict[str, Any]) -> dict[str, int]:
    reasons = set(str(reason) for reason in support.get('support_reasons') or [])
    path_hits = int(support.get('path_hits') or 0)
    lexical_hits = int(support.get('lexical_hits') or 0)
    role = str(support.get('role') or '')
    source_type = str(support.get('source_type') or '')
    verification_join = bool(row.get('requires_test_join'))
    external_join = bool(row.get('requires_external_concept_join'))

    progress = 4 if 'verifier_target_hit' in reasons else 3 + int(path_hits > 1 or lexical_hits > 4)
    technical_correctness = 4
    evidence_grounding = 4 if path_hits > 0 and lexical_hits > 0 else 3
    localization = 4 if path_hits > 0 else 3
    minimality = 4 if role in {'verification_constraint', 'seed_change'} else 3
    verification_value = 4 if ('verifier_target_hit' in reasons or verification_join) else 3
    scope_control = 4 if source_type != 'paper' else 3
    risk = 0 if path_hits > 0 else 1
    verbosity = 1 if not external_join else 2

    return {
        'progress': _clamp_score(progress),
        'technical_correctness': _clamp_score(technical_correctness),
        'evidence_grounding': _clamp_score(evidence_grounding),
        'localization': _clamp_score(localization),
        'minimality': _clamp_score(minimality),
        'verification_value': _clamp_score(verification_value),
        'scope_control': _clamp_score(scope_control),
        'risk': _clamp_score(risk),
        'verbosity': _clamp_score(verbosity),
    }


def _score_negative_candidate(support: dict[str, Any], row: dict[str, Any]) -> dict[str, int]:
    reasons = set(str(reason) for reason in support.get('support_reasons') or [])
    path_hits = int(support.get('path_hits') or 0)
    lexical_hits = int(support.get('lexical_hits') or 0)
    role = str(support.get('role') or '')
    source_type = str(support.get('source_type') or '')
    locality_risk = bool(row.get('locality_risk'))

    progress = 1 if path_hits > 0 and lexical_hits > 0 else 0
    technical_correctness = 1 if path_hits > 0 else 0
    evidence_grounding = 2 if lexical_hits > 0 else 1
    localization = 2 if path_hits > 0 else 1
    minimality = 2 if role in {'seed_change', 'repo_graph_neighbor'} else 1
    verification_value = 1 if 'verifier_target_hit' in reasons else 0
    scope_control = 1 if source_type == 'paper' or locality_risk else 2
    risk = 3 if source_type == 'paper' or lexical_hits > path_hits else 2
    verbosity = 2 if lexical_hits > 3 else 1

    return {
        'progress': _clamp_score(progress),
        'technical_correctness': _clamp_score(technical_correctness),
        'evidence_grounding': _clamp_score(evidence_grounding),
        'localization': _clamp_score(localization),
        'minimality': _clamp_score(minimality),
        'verification_value': _clamp_score(verification_value),
        'scope_control': _clamp_score(scope_control),
        'risk': _clamp_score(risk),
        'verbosity': _clamp_score(verbosity),
    }


def _candidate_action(row: dict[str, Any], support: dict[str, Any], *, candidate_label: str) -> dict[str, Any]:
    return {
        'type': 'retrieve_support_span',
        'query_text': str(row.get('query_text') or ''),
        'chunk_id': str(support.get('chunk_id') or ''),
        'source_type': str(support.get('source_type') or ''),
        'role': str(support.get('role') or ''),
        'path': str(support.get('path') or ''),
        'support_reasons': [str(reason) for reason in support.get('support_reasons') or []],
        'candidate_label': candidate_label,
    }


def build_strict_step_judgment_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    retrieval_rows = _retrieval_rows(rows)
    out: list[dict[str, Any]] = []
    split_counts: dict[str, int] = {}
    label_counts: dict[str, int] = {}
    for row in retrieval_rows:
        split = str(row.get('split') or row.get('effective_split') or 'train')
        support_map = _chunk_support_map(row)
        metadata = _as_dict(row.get('metadata'))
        positive_ids = [str(value) for value in _as_list(row.get('positive_chunk_ids')) if str(value).strip()]
        negative_ids = [str(value) for value in _as_list(row.get('hard_negative_chunk_ids')) if str(value).strip()]
        if not positive_ids:
            continue

        state_id = str(row.get('mixture_row_id') or row.get('row_id') or '')
        state = {
            'task': str(row.get('query_text') or ''),
            'target_text': str(row.get('target_text') or ''),
            'pack_id': str(row.get('pack_id') or ''),
            'join_type': str(row.get('join_type') or ''),
            'span_ratio': float(row.get('span_ratio') or 0.0),
            'source_type_count': int(row.get('source_type_count') or 0),
            'requires_test_join': bool(row.get('requires_test_join')),
            'requires_session_join': bool(row.get('requires_session_join')),
            'requires_external_concept_join': bool(row.get('requires_external_concept_join')),
            'locality_risk': bool(row.get('locality_risk')),
            'long_join_positive': bool(row.get('long_join_positive')),
        }

        for index, chunk_id in enumerate(positive_ids, start=1):
            support = support_map.get(chunk_id, {'chunk_id': chunk_id})
            candidate_label = 'preferred' if index == 1 else 'acceptable_redundant'
            out.append({
                'judgment_example_id': f'{state_id}::pos::{index}',
                'state_id': state_id,
                'pack_id': state['pack_id'],
                'split': split,
                'state': state,
                'candidate': _candidate_action(row, support, candidate_label=candidate_label),
                'scores': _score_positive_candidate(support, row),
                'label': candidate_label,
                'provenance': {
                    'task_family': 'software_maintenance_long_context_candidate_judgment',
                    'label_source': 'heuristic_retrieval_candidate_rubric',
                    'grounding_source': 'retrieval_support_scores',
                    'requires_hard_verifier': True,
                    'heuristic_only': True,
                    'label_leakage_risk': str((metadata.get('label_leakage_risk') or 'high')),
                },
                'metadata': metadata,
            })
            label_counts[candidate_label] = label_counts.get(candidate_label, 0) + 1
            split_counts[split] = split_counts.get(split, 0) + 1

        for index, chunk_id in enumerate(negative_ids, start=1):
            support = support_map.get(chunk_id, {'chunk_id': chunk_id})
            candidate_label = 'rejected'
            out.append({
                'judgment_example_id': f'{state_id}::neg::{index}',
                'state_id': state_id,
                'pack_id': state['pack_id'],
                'split': split,
                'state': state,
                'candidate': _candidate_action(row, support, candidate_label=candidate_label),
                'scores': _score_negative_candidate(support, row),
                'label': candidate_label,
                'provenance': {
                    'task_family': 'software_maintenance_long_context_candidate_judgment',
                    'label_source': 'heuristic_retrieval_candidate_rubric',
                    'grounding_source': 'retrieval_support_scores',
                    'requires_hard_verifier': True,
                    'heuristic_only': True,
                    'label_leakage_risk': str((metadata.get('label_leakage_risk') or 'high')),
                },
                'metadata': metadata,
            })
            label_counts[candidate_label] = label_counts.get(candidate_label, 0) + 1
            split_counts[split] = split_counts.get(split, 0) + 1

    summary = {
        'judgment_row_count': len(out),
        'split_counts': dict(sorted(split_counts.items())),
        'label_counts': dict(sorted(label_counts.items())),
    }
    return out, summary


def build_strict_step_preference_rows(judgment_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in judgment_rows:
        grouped.setdefault(str(row.get('state_id') or ''), []).append(row)

    out: list[dict[str, Any]] = []
    split_counts: dict[str, int] = {}
    preference_counts: dict[str, int] = {}
    for state_id, rows in grouped.items():
        positives = [row for row in rows if row.get('label') in {'preferred', 'acceptable_redundant'}]
        negatives = [row for row in rows if row.get('label') == 'rejected']
        preferred = next((row for row in positives if row.get('label') == 'preferred'), None)
        if preferred is None:
            continue

        for index, row in enumerate([candidate for candidate in positives if candidate.get('label') == 'acceptable_redundant'], start=1):
            split = str(preferred.get('split') or 'train')
            out.append({
                'preference_example_id': f'{state_id}::pref::acceptable::{index}',
                'state_id': state_id,
                'pack_id': str(preferred.get('pack_id') or ''),
                'split': split,
                'state': preferred.get('state'),
                'chosen_candidate': preferred.get('candidate'),
                'rejected_candidate': row.get('candidate'),
                'chosen_scores': preferred.get('scores'),
                'rejected_scores': row.get('scores'),
                'preference_type': 'preferred_over_acceptable',
                'provenance': preferred.get('provenance'),
            })
            split_counts[split] = split_counts.get(split, 0) + 1
            preference_counts['preferred_over_acceptable'] = preference_counts.get('preferred_over_acceptable', 0) + 1

        for index, row in enumerate(negatives[:MAX_NEGATIVE_PREFERENCES_PER_STATE], start=1):
            split = str(preferred.get('split') or 'train')
            out.append({
                'preference_example_id': f'{state_id}::pref::rejected::{index}',
                'state_id': state_id,
                'pack_id': str(preferred.get('pack_id') or ''),
                'split': split,
                'state': preferred.get('state'),
                'chosen_candidate': preferred.get('candidate'),
                'rejected_candidate': row.get('candidate'),
                'chosen_scores': preferred.get('scores'),
                'rejected_scores': row.get('scores'),
                'preference_type': 'preferred_over_rejected',
                'provenance': preferred.get('provenance'),
            })
            split_counts[split] = split_counts.get(split, 0) + 1
            preference_counts['preferred_over_rejected'] = preference_counts.get('preferred_over_rejected', 0) + 1

    summary = {
        'preference_row_count': len(out),
        'split_counts': dict(sorted(split_counts.items())),
        'preference_counts': dict(sorted(preference_counts.items())),
    }
    return out, summary


def prepare_strict_long_context_step_judgment_datasets(*, rows_path: Path | None = None, dataset_card_path: Path | None = DEFAULT_DATASET_CARD_PATH, output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    resolved_rows_path, resolved_dataset_card_path = _resolve_rows_path(rows_path, dataset_card_path)
    rows = _read_jsonl(resolved_rows_path)
    if not rows:
        raise ValueError('empty_rows')
    judgment_rows, judgment_summary = build_strict_step_judgment_rows(rows)
    preference_rows, preference_summary = build_strict_step_preference_rows(judgment_rows)
    output_dir.mkdir(parents=True, exist_ok=True)
    judgment_path = output_dir / 'strict_long_context_step_judgment_rows.jsonl'
    preference_path = output_dir / 'strict_long_context_step_preference_rows.jsonl'
    card_path = output_dir / 'strict_long_context_step_judgment_datasets_card.json'
    write_jsonl(judgment_path, judgment_rows)
    write_jsonl(preference_path, preference_rows)
    card = {
        'rows_path': str(resolved_rows_path),
        'dataset_card_path': str(resolved_dataset_card_path) if resolved_dataset_card_path is not None else None,
        'output_dir': str(output_dir),
        'judgment_rows_path': str(judgment_path),
        'preference_rows_path': str(preference_path),
        'judgment_summary': judgment_summary,
        'preference_summary': preference_summary,
        'rubric_axes': [
            'progress',
            'technical_correctness',
            'evidence_grounding',
            'localization',
            'minimality',
            'verification_value',
            'scope_control',
            'risk',
            'verbosity',
        ],
        'quality_contract': {
            'heuristic_only': True,
            'requires_hard_verifier': True,
            'intended_use': 'candidate_ranking_and_preference_distillation_for_long_context_software_maintenance',
        },
    }
    write_json(card_path, card)
    return card


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Prepare rubric-based step judgment datasets from strict long-context retrieval rows.')
    parser.add_argument('--dataset-card', type=Path, default=DEFAULT_DATASET_CARD_PATH)
    parser.add_argument('--rows', type=Path)
    parser.add_argument('--output-dir', type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    prepare_strict_long_context_step_judgment_datasets(rows_path=args.rows, dataset_card_path=args.dataset_card, output_dir=args.output_dir)


if __name__ == '__main__':
    main()
