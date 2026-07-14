from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from prepare_strict_long_context_step_judgment_datasets import (  # noqa: E402
    build_strict_step_judgment_rows,
    build_strict_step_preference_rows,
    prepare_strict_long_context_step_judgment_datasets,
)


def test_prepare_strict_long_context_step_judgment_datasets_builds_rubric_rows(tmp_path: Path) -> None:
    rows_path = tmp_path / 'split_rows.jsonl'
    rows_path.write_text(
        json.dumps(
            {
                'mixture_surface': 'retrieval_rows',
                'mixture_row_id': 'retrieval_rows::r1',
                'row_id': 'retrieval::r1',
                'pack_id': 'pack_a',
                'split': 'train',
                'effective_split': 'train',
                'query_text': 'Repository: demo\nTransition target: verification_targets\nVerification targets: tests/test_demo.py',
                'target_text': json.dumps({'canonical_name': 'demo', 'state_variable': 'verification_targets', 'final_state': {'verification_targets': ['tests/test_demo.py']}}, sort_keys=True),
                'positive_chunk_ids': json.dumps(['c_pos_1', 'c_pos_2']),
                'hard_negative_chunk_ids': json.dumps(['c_neg_1']),
                'support_scores': json.dumps(
                    [
                        {'chunk_id': 'c_pos_1', 'score': 12, 'path_hits': 1, 'lexical_hits': 2, 'role_bonus': 4, 'source_type': 'repo', 'role': 'verification_constraint', 'path': 'tests/test_demo.py', 'support_reasons': ['path_hit', 'verifier_target_hit']},
                        {'chunk_id': 'c_pos_2', 'score': 8, 'path_hits': 1, 'lexical_hits': 1, 'role_bonus': 2, 'source_type': 'repo', 'role': 'seed_change', 'path': 'src/demo.py', 'support_reasons': ['path_hit', 'changed_file_hit']},
                        {'chunk_id': 'c_neg_1', 'score': 4, 'path_hits': 0, 'lexical_hits': 4, 'role_bonus': 0, 'source_type': 'paper', 'role': 'supporting_paper', 'path': 'papers/demo.txt', 'support_reasons': ['lexical_hit']},
                    ],
                    sort_keys=True,
                ),
                'join_type': 'repo+paper',
                'span_ratio': 0.42,
                'source_type_count': 2,
                'requires_test_join': True,
                'requires_session_join': False,
                'requires_external_concept_join': True,
                'locality_risk': False,
                'long_join_positive': True,
                'metadata': json.dumps({'canonical_name': 'demo', 'query_index': 1, 'label_leakage_risk': 'high'}, sort_keys=True),
                'task_type': 'retrieval_supervision',
            },
            sort_keys=True,
        ) + '\n',
        encoding='utf-8',
    )

    rows = [json.loads(line) for line in rows_path.read_text(encoding='utf-8').splitlines() if line.strip()]
    judgment_rows, judgment_summary = build_strict_step_judgment_rows(rows)
    preference_rows, preference_summary = build_strict_step_preference_rows(judgment_rows)

    assert judgment_summary['judgment_row_count'] == 3
    assert judgment_summary['label_counts'] == {
        'acceptable_redundant': 1,
        'preferred': 1,
        'rejected': 1,
    }
    assert judgment_rows[0]['candidate']['type'] == 'retrieve_support_span'
    assert judgment_rows[0]['scores']['progress'] == 4
    assert judgment_rows[0]['scores']['verification_value'] == 4
    assert judgment_rows[0]['provenance']['heuristic_only'] is True
    assert judgment_rows[1]['label'] == 'acceptable_redundant'
    assert judgment_rows[2]['label'] == 'rejected'
    assert judgment_rows[2]['scores']['risk'] >= 2

    assert preference_summary['preference_row_count'] == 2
    assert preference_summary['preference_counts'] == {
        'preferred_over_acceptable': 1,
        'preferred_over_rejected': 1,
    }
    assert preference_rows[0]['preference_type'] == 'preferred_over_acceptable'
    assert preference_rows[1]['preference_type'] == 'preferred_over_rejected'

    card = prepare_strict_long_context_step_judgment_datasets(rows_path=rows_path, output_dir=tmp_path / 'out')
    assert Path(card['judgment_rows_path']).exists()
    assert Path(card['preference_rows_path']).exists()
    assert card['quality_contract']['heuristic_only'] is True


def test_prepare_strict_long_context_step_judgment_datasets_resolves_rows_from_dataset_card(tmp_path: Path) -> None:
    rows_path = tmp_path / 'split_rows.jsonl'
    rows_path.write_text(
        json.dumps(
            {
                'mixture_surface': 'retrieval_rows',
                'mixture_row_id': 'retrieval_rows::r1',
                'row_id': 'retrieval::r1',
                'pack_id': 'pack_a',
                'split': 'train',
                'effective_split': 'train',
                'query_text': 'Repository: demo\nTransition target: verification_targets\nVerification targets: tests/test_demo.py',
                'target_text': json.dumps({'canonical_name': 'demo', 'state_variable': 'verification_targets', 'final_state': {'verification_targets': ['tests/test_demo.py']}}, sort_keys=True),
                'positive_chunk_ids': json.dumps(['c_pos_1']),
                'hard_negative_chunk_ids': json.dumps(['c_neg_1']),
                'support_scores': json.dumps(
                    [
                        {'chunk_id': 'c_pos_1', 'score': 12, 'path_hits': 1, 'lexical_hits': 2, 'role_bonus': 4, 'source_type': 'repo', 'role': 'verification_constraint', 'path': 'tests/test_demo.py', 'support_reasons': ['path_hit', 'verifier_target_hit']},
                        {'chunk_id': 'c_neg_1', 'score': 4, 'path_hits': 0, 'lexical_hits': 4, 'role_bonus': 0, 'source_type': 'paper', 'role': 'supporting_paper', 'path': 'papers/demo.txt', 'support_reasons': ['lexical_hit']},
                    ],
                    sort_keys=True,
                ),
                'join_type': 'repo+paper',
                'span_ratio': 0.42,
                'source_type_count': 2,
                'requires_test_join': True,
                'requires_session_join': False,
                'requires_external_concept_join': True,
                'locality_risk': False,
                'long_join_positive': True,
                'metadata': json.dumps({'canonical_name': 'demo', 'query_index': 1, 'label_leakage_risk': 'high'}, sort_keys=True),
                'task_type': 'retrieval_supervision',
            },
            sort_keys=True,
        ) + '\n',
        encoding='utf-8',
    )
    dataset_card = tmp_path / 'dataset_card.json'
    dataset_card.write_text(
        json.dumps(
            {
                'split_pipeline': {
                    'splits': {
                        'rows_path': str(rows_path.resolve()),
                    }
                }
            },
            sort_keys=True,
        ),
        encoding='utf-8',
    )
    card = prepare_strict_long_context_step_judgment_datasets(dataset_card_path=dataset_card, output_dir=tmp_path / 'out_card')
    assert card['rows_path'] == str(rows_path.resolve())
    assert card['dataset_card_path'] == str(dataset_card.resolve())
