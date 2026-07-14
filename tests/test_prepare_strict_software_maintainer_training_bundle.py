from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from prepare_strict_software_maintainer_training_bundle import prepare_strict_software_maintainer_training_bundle  # noqa: E402


def _write_training_rows(path: Path, *, pack_id: str, chunk_id: str, state_variable: str) -> None:
    row = {
        'pack_id': pack_id,
        'effective_split': 'train',
        'trainer_policy_mode': 'family_cluster_constrained_training',
        'overlap_family_id': f'cluster::{pack_id}',
        'prompt_text': f'Prompt for {pack_id}',
        'context_rows': [
            {
                'chunk_id': chunk_id,
                'chunk_ordinal': 1,
                'source_type': 'repo',
                'path': f'src/{pack_id}.py',
                'text': f'{state_variable} is true',
            }
        ],
        'target_rows': [
            {
                'query_index': 1,
                'candidate_id': f'cand::{pack_id}',
                'canonical_name': state_variable,
                'final_state': {state_variable: True},
                'state_variable': state_variable,
            }
        ],
        'pack_token_count': 128,
        'chunk_count': 1,
        'candidate_count': 1,
    }
    path.write_text(json.dumps(row, sort_keys=True) + '\n', encoding='utf-8')


def _write_pack_audit(path: Path, *, pack_id: str) -> None:
    row = {
        'pack_id': pack_id,
        'accepted': True,
        'state_delta_ready_fraction': 1.0,
        'evidence_anchor_ready_fraction': 1.0,
    }
    path.write_text(json.dumps(row, sort_keys=True) + '\n', encoding='utf-8')


def test_prepare_strict_software_maintainer_training_bundle_references_both_cards(tmp_path: Path) -> None:
    strict_rows = tmp_path / 'strict_rows.jsonl'
    strict_audit = tmp_path / 'strict_audit.jsonl'
    _write_training_rows(strict_rows, pack_id='strict-pack', chunk_id='strict-c1', state_variable='strict_state')
    _write_pack_audit(strict_audit, pack_id='strict-pack')
    manifest = tmp_path / 'strict_manifest.json'
    manifest.write_text(
        json.dumps(
            {
                'selected_shards': [
                    {
                        'name': 'strict_shard',
                        'acceptance_mode': 'strict_builder',
                        'ready_for_training': True,
                        'artifacts': {'training_rows_jsonl': str(strict_rows), 'pack_audit_jsonl': str(strict_audit)},
                    }
                ]
            },
            sort_keys=True,
        ),
        encoding='utf-8',
    )

    long_cfg = tmp_path / 'long_context_entrypoint.json'
    long_cfg.write_text(
        json.dumps(
            {
                'dataset_defaults': {
                    'strict_shard_manifest': str(manifest.resolve()),
                    'include_audit_only_direct': False,
                    'output_dir': str((tmp_path / 'long_out').resolve()),
                    'export_parquet': False,
                    'max_positive_chunks': 4,
                    'rows_per_shard': 100,
                    'compression': 'zstd',
                    'prepare_split_pipeline': False,
                    'min_state_delta_ready_fraction': 0.0,
                    'min_evidence_anchor_ready_fraction': 0.0,
                }
            },
            sort_keys=True,
        ),
        encoding='utf-8',
    )

    dataset_dir = tmp_path / 'retrieval_datasets'
    dataset_dir.mkdir(parents=True)
    rows = {
        'strict_long_context_retriever_rows.jsonl': [
            {'retriever_example_id': 'r_grounded', 'split': 'train', 'metadata': {'label_source': 'grounded_verifier_route'}, 'long_join_positive': True, 'locality_risk': False},
            {'retriever_example_id': 'r_mixed', 'split': 'eval', 'metadata': {'label_source': 'mixed_grounded_verifier_route_long_join'}, 'long_join_positive': True, 'locality_risk': False},
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

    retrieval_source_card = dataset_dir / 'strict_long_context_retrieval_datasets_card.json'
    retrieval_source_card.write_text(
        json.dumps(
            {
                'retriever_rows_path': str((dataset_dir / 'strict_long_context_retriever_rows.jsonl').resolve()),
                'reranker_pairwise_rows_path': str((dataset_dir / 'strict_long_context_reranker_pairwise_rows.jsonl').resolve()),
                'reranker_listwise_rows_path': str((dataset_dir / 'strict_long_context_reranker_listwise_rows.jsonl').resolve()),
                'retriever_curriculum_rows_path': str((dataset_dir / 'strict_long_context_retriever_curriculum_rows.jsonl').resolve()),
                'retriever_summary': {'retriever_row_count': 2},
                'reranker_summary': {'pairwise_row_count': 1},
                'listwise_summary': {'listwise_row_count': 1},
                'curriculum_summary': {'curriculum_row_count': 1},
            },
            sort_keys=True,
        ),
        encoding='utf-8',
    )

    retrieval_mixture_cfg = tmp_path / 'retrieval_mixture_launcher.json'
    retrieval_mixture_cfg.write_text(
        json.dumps(
            {
                'launcher_defaults': {
                    'output_dir': str((tmp_path / 'retrieval_out').resolve()),
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

    retrieval_cfg = tmp_path / 'retrieval_entrypoint.json'
    retrieval_cfg.write_text(
        json.dumps(
            {
                'dataset_defaults': {
                    'dataset_card': str(retrieval_source_card.resolve()),
                    'mixture_launcher_config': str(retrieval_mixture_cfg.resolve()),
                    'output_dir': str((tmp_path / 'retrieval_out').resolve()),
                    'include_opt_in_profiles': False,
                    'seed': 0,
                }
            },
            sort_keys=True,
        ),
        encoding='utf-8',
    )

    bundle_cfg = tmp_path / 'bundle_entrypoint.json'
    bundle_cfg.write_text(
        json.dumps(
            {
                'bundle_defaults': {
                    'long_context_config': str(long_cfg.resolve()),
                    'retrieval_config': str(retrieval_cfg.resolve()),
                    'output_dir': str((tmp_path / 'bundle_out').resolve()),
                }
            },
            sort_keys=True,
        ),
        encoding='utf-8',
    )

    result = prepare_strict_software_maintainer_training_bundle(config_path=bundle_cfg)
    assert Path(result['long_context_training_dataset_card_path']).is_file()
    assert Path(result['retrieval_training_dataset_card_path']).is_file()
    assert Path(result['trainer_default_long_context_dataset_card']).is_file()
    assert Path(result['trainer_default_long_context_filtered_shard_manifest']).is_file()
    assert result['trainer_default_long_context_sampled_manifest'] == ''
    assert set(result['trainer_default_retrieval_manifests']) == {'pure_grounded', 'mixed_grounded_long_join'}
    assert result['retrieval_opt_in_profiles'] == ['heuristic_residual']
