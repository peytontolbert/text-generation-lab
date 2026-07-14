from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from prepare_strict_long_context_retrieval_training_dataset import prepare_strict_long_context_retrieval_training_dataset  # noqa: E402


def test_prepare_strict_long_context_retrieval_training_dataset_defaults_to_bundle_profiles(tmp_path: Path) -> None:
    dataset_dir = tmp_path / 'retrieval_datasets'
    dataset_dir.mkdir(parents=True)
    rows = {
        'strict_long_context_retriever_rows.jsonl': [
            {'retriever_example_id': 'r_grounded', 'split': 'train', 'metadata': {'label_source': 'grounded_verifier_route'}, 'long_join_positive': True, 'locality_risk': False},
            {'retriever_example_id': 'r_mixed', 'split': 'eval', 'metadata': {'label_source': 'mixed_grounded_verifier_route_long_join'}, 'long_join_positive': True, 'locality_risk': False},
            {'retriever_example_id': 'r_heur', 'split': 'strict_eval', 'metadata': {'label_source': 'heuristic_target_overlap'}, 'long_join_positive': False, 'locality_risk': True},
        ],
        'strict_long_context_reranker_pairwise_rows.jsonl': [
            {'pairwise_example_id': 'p1', 'split': 'train', 'join_type': 'multi_repo'},
        ],
        'strict_long_context_reranker_listwise_rows.jsonl': [
            {'listwise_example_id': 'l1', 'split': 'train', 'join_type': 'multi_repo'},
        ],
        'strict_long_context_retriever_curriculum_rows.jsonl': [
            {'curriculum_example_id': 'c1', 'split': 'train', 'long_join_positive': True, 'locality_risk': False},
            {'curriculum_example_id': 'c2', 'split': 'strict_eval', 'long_join_positive': False, 'locality_risk': True},
        ],
    }
    for name, values in rows.items():
        (dataset_dir / name).write_text(''.join(json.dumps(row) + '\n' for row in values), encoding='utf-8')

    source_card = dataset_dir / 'strict_long_context_retrieval_datasets_card.json'
    source_card.write_text(
        json.dumps(
            {
                'retriever_rows_path': str((dataset_dir / 'strict_long_context_retriever_rows.jsonl').resolve()),
                'reranker_pairwise_rows_path': str((dataset_dir / 'strict_long_context_reranker_pairwise_rows.jsonl').resolve()),
                'reranker_listwise_rows_path': str((dataset_dir / 'strict_long_context_reranker_listwise_rows.jsonl').resolve()),
                'retriever_curriculum_rows_path': str((dataset_dir / 'strict_long_context_retriever_curriculum_rows.jsonl').resolve()),
                'retriever_summary': {'retriever_row_count': 3},
                'reranker_summary': {'pairwise_row_count': 1},
                'listwise_summary': {'listwise_row_count': 1},
                'curriculum_summary': {'curriculum_row_count': 2},
            },
            sort_keys=True,
        ),
        encoding='utf-8',
    )

    mixture_cfg = tmp_path / 'mixture_launcher.json'
    mixture_cfg.write_text(
        json.dumps(
            {
                'launcher_defaults': {
                    'output_dir': str((tmp_path / 'out').resolve()),
                    'profile': 'pure_grounded',
                    'default_train_profiles': ['pure_grounded', 'mixed_grounded_long_join'],
                    'opt_in_profiles': ['heuristic_residual'],
                },
                'profiles': [
                    {
                        'name': 'pure_grounded',
                        'description': 'pure',
                        'surfaces': [
                            {'name': 'retriever_rows', 'task_family': 'retriever_supervision', 'weight': 1.0, 'filter_expr': 'metadata contains grounded_verifier_route'},
                            {'name': 'retriever_curriculum_rows', 'task_family': 'retriever_curriculum', 'weight': 0.4, 'filter_expr': 'long_join_positive==1'},
                        ],
                    },
                    {
                        'name': 'mixed_grounded_long_join',
                        'description': 'mixed',
                        'surfaces': [
                            {'name': 'retriever_rows', 'task_family': 'retriever_supervision', 'weight': 1.0, 'filter_expr': 'metadata contains mixed_grounded_verifier_route_long_join'},
                            {'name': 'retriever_curriculum_rows', 'task_family': 'retriever_curriculum', 'weight': 0.75, 'filter_expr': 'long_join_positive==1'},
                            {'name': 'reranker_listwise_rows', 'task_family': 'reranker_listwise', 'weight': 0.35, 'filter_expr': 'join_type==multi_repo or join_type==repo+paper'},
                        ],
                    },
                    {
                        'name': 'heuristic_residual',
                        'description': 'heuristic',
                        'surfaces': [
                            {'name': 'retriever_rows', 'task_family': 'retriever_supervision', 'weight': 0.5, 'filter_expr': 'metadata contains heuristic_target_overlap'},
                        ],
                    },
                ],
            },
            sort_keys=True,
        ),
        encoding='utf-8',
    )

    entry_cfg = tmp_path / 'retrieval_entrypoint.json'
    entry_cfg.write_text(
        json.dumps(
            {
                'dataset_defaults': {
                    'dataset_card': str(source_card.resolve()),
                    'mixture_launcher_config': str(mixture_cfg.resolve()),
                    'output_dir': str((tmp_path / 'out').resolve()),
                    'include_opt_in_profiles': False,
                    'seed': 0,
                }
            },
            sort_keys=True,
        ),
        encoding='utf-8',
    )

    result = prepare_strict_long_context_retrieval_training_dataset(config_path=entry_cfg)
    assert result['trainer_default_profiles'] == ['pure_grounded', 'mixed_grounded_long_join']
    assert set(result['default_sampled_manifests']) == {'pure_grounded', 'mixed_grounded_long_join'}
    assert result['opt_in_profiles'] == ['heuristic_residual']
    assert Path(result['profile_bundle_card_path']).is_file()


def test_prepare_strict_long_context_retrieval_training_dataset_can_resolve_from_bundle_card(tmp_path: Path) -> None:
    dataset_dir = tmp_path / 'retrieval_datasets'
    dataset_dir.mkdir(parents=True)
    rows = {
        'strict_long_context_retriever_rows.jsonl': [
            {'retriever_example_id': 'r_grounded', 'split': 'train', 'metadata': {'label_source': 'grounded_verifier_route'}, 'long_join_positive': True, 'locality_risk': False},
        ],
        'strict_long_context_reranker_pairwise_rows.jsonl': [
            {'pairwise_example_id': 'p1', 'split': 'train', 'join_type': 'multi_repo'},
        ],
        'strict_long_context_reranker_listwise_rows.jsonl': [
            {'listwise_example_id': 'l1', 'split': 'train', 'join_type': 'multi_repo'},
        ],
        'strict_long_context_retriever_curriculum_rows.jsonl': [
            {'curriculum_example_id': 'c1', 'split': 'train', 'long_join_positive': True, 'locality_risk': False},
        ],
    }
    for name, values in rows.items():
        (dataset_dir / name).write_text(''.join(json.dumps(row) + '\n' for row in values), encoding='utf-8')

    source_card = dataset_dir / 'strict_long_context_retrieval_datasets_card.json'
    source_card.write_text(
        json.dumps(
            {
                'retriever_rows_path': str((dataset_dir / 'strict_long_context_retriever_rows.jsonl').resolve()),
                'reranker_pairwise_rows_path': str((dataset_dir / 'strict_long_context_reranker_pairwise_rows.jsonl').resolve()),
                'reranker_listwise_rows_path': str((dataset_dir / 'strict_long_context_reranker_listwise_rows.jsonl').resolve()),
                'retriever_curriculum_rows_path': str((dataset_dir / 'strict_long_context_retriever_curriculum_rows.jsonl').resolve()),
                'retriever_summary': {'retriever_row_count': 1},
                'reranker_summary': {'pairwise_row_count': 1},
                'listwise_summary': {'listwise_row_count': 1},
                'curriculum_summary': {'curriculum_row_count': 1},
            },
            sort_keys=True,
        ),
        encoding='utf-8',
    )
    training_dataset_card = tmp_path / 'strict_long_context_retrieval_training_dataset_card.json'
    training_dataset_card.write_text(
        json.dumps(
            {
                'dataset_card_path': str(source_card.resolve()),
            },
            sort_keys=True,
        ),
        encoding='utf-8',
    )
    bundle_card = tmp_path / 'strict_software_maintainer_training_bundle_card.json'
    bundle_card.write_text(
        json.dumps(
            {
                'retrieval_training_dataset_card_path': str(training_dataset_card.resolve()),
            },
            sort_keys=True,
        ),
        encoding='utf-8',
    )

    mixture_cfg = tmp_path / 'mixture_launcher.json'
    mixture_cfg.write_text(
        json.dumps(
            {
                'launcher_defaults': {
                    'output_dir': str((tmp_path / 'out').resolve()),
                    'profile': 'pure_grounded',
                    'default_train_profiles': ['pure_grounded'],
                    'opt_in_profiles': [],
                },
                'profiles': [
                    {
                        'name': 'pure_grounded',
                        'description': 'pure',
                        'surfaces': [
                            {'name': 'retriever_rows', 'task_family': 'retriever_supervision', 'weight': 1.0, 'filter_expr': 'metadata contains grounded_verifier_route'},
                        ],
                    },
                ],
            },
            sort_keys=True,
        ),
        encoding='utf-8',
    )
    entry_cfg = tmp_path / 'retrieval_entrypoint.json'
    entry_cfg.write_text(
        json.dumps(
            {
                'dataset_defaults': {
                    'bundle_card': str(bundle_card.resolve()),
                    'mixture_launcher_config': str(mixture_cfg.resolve()),
                    'output_dir': str((tmp_path / 'out').resolve()),
                    'include_opt_in_profiles': False,
                    'seed': 0,
                }
            },
            sort_keys=True,
        ),
        encoding='utf-8',
    )

    result = prepare_strict_long_context_retrieval_training_dataset(config_path=entry_cfg)
    assert result['dataset_card_path'] is None
    assert result['bundle_card_path'] == str(bundle_card.resolve())
    assert result['trainer_default_profiles'] == ['pure_grounded']
    assert Path(result['profile_bundle_card_path']).is_file()
