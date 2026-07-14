from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from prepare_strict_long_context_retrieval_datasets import (  # noqa: E402
    build_strict_reranker_listwise_rows,
    build_strict_reranker_pairwise_rows,
    build_strict_retriever_curriculum_rows,
    build_strict_retriever_rows,
    prepare_strict_long_context_retrieval_datasets,
)


def test_prepare_strict_long_context_retrieval_datasets_builds_retriever_and_pairwise_rows(tmp_path: Path) -> None:
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
                'query_text': 'Repository: demo\nTransition target: verification_targets',
                'target_text': json.dumps({'canonical_name': 'demo', 'state_variable': 'verification_targets', 'final_state': {'verification_targets': ['tests/test_demo.py']}}, sort_keys=True),
                'positive_chunk_ids': json.dumps(['c_pos_1', 'c_pos_2']),
                'hard_negative_chunk_ids': json.dumps(['c_neg_1']),
                'support_scores': json.dumps(
                    [
                        {'chunk_id': 'c_pos_1', 'score': 12, 'path_hits': 1, 'lexical_hits': 2, 'role_bonus': 4, 'source_type': 'repo', 'role': 'verification_constraint', 'support_reasons': ['path_hit', 'verifier_target_hit']},
                        {'chunk_id': 'c_pos_2', 'score': 8, 'path_hits': 1, 'lexical_hits': 1, 'role_bonus': 2, 'source_type': 'repo', 'role': 'seed_change', 'support_reasons': ['path_hit', 'changed_file_hit']},
                        {'chunk_id': 'c_neg_1', 'score': 4, 'path_hits': 0, 'lexical_hits': 4, 'role_bonus': 0, 'source_type': 'paper', 'role': 'supporting_paper', 'support_reasons': ['lexical_hit']},
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
                'metadata': json.dumps({'canonical_name': 'demo', 'query_index': 1}, sort_keys=True),
                'task_type': 'retrieval_supervision',
            },
            sort_keys=True,
        ) + '\n',
        encoding='utf-8',
    )

    rows = [json.loads(line) for line in rows_path.read_text(encoding='utf-8').splitlines() if line.strip()]
    retriever_rows, retriever_summary = build_strict_retriever_rows(rows)
    reranker_rows, reranker_summary = build_strict_reranker_pairwise_rows(rows)
    listwise_rows, listwise_summary = build_strict_reranker_listwise_rows(rows)

    assert retriever_summary['retriever_row_count'] == 1
    assert retriever_rows[0]['positive_chunks'][0]['chunk_id'] == 'c_pos_1'
    assert retriever_rows[0]['hard_negative_chunks'][0]['chunk_id'] == 'c_neg_1'
    assert retriever_rows[0]['join_type'] == 'repo+paper'
    assert retriever_rows[0]['requires_external_concept_join'] is True
    assert retriever_rows[0]['long_join_positive'] is True

    assert reranker_summary['pairwise_row_count'] == 2
    assert reranker_rows[0]['preferred_chunk_id'] == 'c_pos_1'
    assert reranker_rows[0]['rejected_chunk_id'] == 'c_neg_1'
    assert reranker_rows[0]['join_type'] == 'repo+paper'

    assert listwise_summary['listwise_row_count'] == 1
    assert len(listwise_rows[0]['candidates']) == 3
    assert [candidate['label'] for candidate in listwise_rows[0]['candidates']] == [1, 0, 1]

    curriculum_rows, curriculum_summary = build_strict_retriever_curriculum_rows(retriever_rows)
    assert curriculum_summary['curriculum_row_count'] == 4
    assert 'join_type::repo+paper' in curriculum_summary['slice_counts']
    assert 'long_join_positive::1' in curriculum_summary['slice_counts']
    assert any(row['curriculum_slice'].startswith('join_type::repo+paper::long_join::1') for row in curriculum_rows)

    card = prepare_strict_long_context_retrieval_datasets(rows_path=rows_path, output_dir=tmp_path / 'out')
    assert Path(card['retriever_rows_path']).exists()
    assert Path(card['reranker_pairwise_rows_path']).exists()
    assert Path(card['reranker_listwise_rows_path']).exists()
    assert Path(card['retriever_curriculum_rows_path']).exists()


def test_prepare_strict_long_context_retrieval_datasets_resolves_rows_from_dataset_card(tmp_path: Path) -> None:
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
                'query_text': 'Repository: demo\nTransition target: verification_targets',
                'target_text': json.dumps({'canonical_name': 'demo', 'state_variable': 'verification_targets', 'final_state': {'verification_targets': ['tests/test_demo.py']}}, sort_keys=True),
                'positive_chunk_ids': json.dumps(['c_pos_1']),
                'hard_negative_chunk_ids': json.dumps(['c_neg_1']),
                'support_scores': json.dumps(
                    [
                        {'chunk_id': 'c_pos_1', 'score': 12, 'path_hits': 1, 'lexical_hits': 2, 'role_bonus': 4, 'source_type': 'repo', 'role': 'verification_constraint', 'support_reasons': ['path_hit', 'verifier_target_hit']},
                        {'chunk_id': 'c_neg_1', 'score': 4, 'path_hits': 0, 'lexical_hits': 4, 'role_bonus': 0, 'source_type': 'paper', 'role': 'supporting_paper', 'support_reasons': ['lexical_hit']},
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
                'metadata': json.dumps({'canonical_name': 'demo', 'query_index': 1}, sort_keys=True),
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
    card = prepare_strict_long_context_retrieval_datasets(dataset_card_path=dataset_card, output_dir=tmp_path / 'out_card')
    assert card['rows_path'] == str(rows_path.resolve())
    assert card['dataset_card_path'] == str(dataset_card.resolve())
