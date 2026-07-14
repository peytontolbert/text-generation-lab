from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from prepare_strict_long_context_retrieval_mixture import build_strict_long_context_retrieval_mixture_manifest  # noqa: E402


def test_prepare_strict_long_context_retrieval_mixture_builds_profile_manifest(tmp_path: Path) -> None:
    dataset_dir = tmp_path / 'retrieval_datasets'
    dataset_dir.mkdir(parents=True)
    surface_files = {
        'strict_long_context_retriever_rows.jsonl': [{'row_id': 'r1'}],
        'strict_long_context_reranker_pairwise_rows.jsonl': [{'row_id': 'p1'}],
        'strict_long_context_reranker_listwise_rows.jsonl': [{'row_id': 'l1'}],
        'strict_long_context_retriever_curriculum_rows.jsonl': [{'row_id': 'c1'}],
    }
    for name, rows in surface_files.items():
        (dataset_dir / name).write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')

    card_path = dataset_dir / 'strict_long_context_retrieval_datasets_card.json'
    card_path.write_text(
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

    out_dir = tmp_path / 'mixture'
    card = build_strict_long_context_retrieval_mixture_manifest(
        dataset_card_path=card_path,
        output_dir=out_dir,
        profile='reranker_balanced',
    )
    assert card['profile'] == 'reranker_balanced'
    manifest_path = out_dir / 'strict_long_context_retrieval_mixture_manifest.jsonl'
    rows = [json.loads(line) for line in manifest_path.read_text(encoding='utf-8').splitlines() if line.strip()]
    assert [row['surface'] for row in rows] == ['reranker_pairwise_rows', 'reranker_listwise_rows', 'retriever_curriculum_rows']
    assert rows[0]['weight'] == 1.0
    assert rows[1]['weight'] == 0.75
    assert rows[2]['filter_expr'] == 'long_join_positive==1 or locality_risk==1'


def test_prepare_strict_long_context_retrieval_mixture_builds_provenance_profile_manifest(tmp_path: Path) -> None:
    dataset_dir = tmp_path / 'retrieval_datasets'
    dataset_dir.mkdir(parents=True)
    surface_files = {
        'strict_long_context_retriever_rows.jsonl': [{'retriever_example_id': 'r1', 'metadata': {'label_source': 'mixed_grounded_verifier_route_long_join'}}],
        'strict_long_context_reranker_pairwise_rows.jsonl': [{'pairwise_example_id': 'p1', 'join_type': 'multi_repo'}],
        'strict_long_context_reranker_listwise_rows.jsonl': [{'listwise_example_id': 'l1', 'join_type': 'multi_repo'}],
        'strict_long_context_retriever_curriculum_rows.jsonl': [{'curriculum_example_id': 'c1', 'long_join_positive': True, 'locality_risk': False}],
    }
    for name, rows in surface_files.items():
        (dataset_dir / name).write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')

    card_path = dataset_dir / 'strict_long_context_retrieval_datasets_card.json'
    card_path.write_text(
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

    out_dir = tmp_path / 'mixture_provenance'
    card = build_strict_long_context_retrieval_mixture_manifest(
        dataset_card_path=card_path,
        output_dir=out_dir,
        profile='mixed_grounded_long_join',
    )
    assert card['profile'] == 'mixed_grounded_long_join'
    manifest_path = out_dir / 'strict_long_context_retrieval_mixture_manifest.jsonl'
    rows = [json.loads(line) for line in manifest_path.read_text(encoding='utf-8').splitlines() if line.strip()]
    assert [row['surface'] for row in rows] == ['retriever_rows', 'retriever_curriculum_rows', 'reranker_listwise_rows']
    assert rows[0]['filter_expr'] == 'metadata contains mixed_grounded_verifier_route_long_join'
    assert rows[1]['filter_expr'] == 'long_join_positive==1'
    assert rows[2]['filter_expr'] == 'join_type==multi_repo or join_type==repo+paper'


def test_prepare_strict_long_context_retrieval_mixture_can_resolve_from_bundle_card(tmp_path: Path) -> None:
    dataset_dir = tmp_path / 'retrieval_datasets'
    dataset_dir.mkdir(parents=True)
    surface_files = {
        'strict_long_context_retriever_rows.jsonl': [{'retriever_example_id': 'r1'}],
        'strict_long_context_reranker_pairwise_rows.jsonl': [{'pairwise_example_id': 'p1'}],
        'strict_long_context_reranker_listwise_rows.jsonl': [{'listwise_example_id': 'l1'}],
        'strict_long_context_retriever_curriculum_rows.jsonl': [{'curriculum_example_id': 'c1'}],
    }
    for name, rows in surface_files.items():
        (dataset_dir / name).write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')

    dataset_card = dataset_dir / 'strict_long_context_retrieval_training_dataset_card.json'
    dataset_card.write_text(
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
    bundle_card = tmp_path / 'bundle_card.json'
    bundle_card.write_text(
        json.dumps(
            {
                'retrieval_training_dataset_card_path': str(dataset_card.resolve()),
            },
            sort_keys=True,
        ),
        encoding='utf-8',
    )

    out_dir = tmp_path / 'mixture_bundle'
    card = build_strict_long_context_retrieval_mixture_manifest(
        bundle_card_path=bundle_card,
        output_dir=out_dir,
        profile='pure_grounded',
    )
    assert card['dataset_card_path'] == str(dataset_card.resolve())
    assert card['bundle_card_path'] == str(bundle_card.resolve())
    assert card['profile'] == 'pure_grounded'


def test_prepare_strict_long_context_retrieval_mixture_can_resolve_nested_training_card_from_bundle(tmp_path: Path) -> None:
    dataset_dir = tmp_path / 'retrieval_datasets'
    dataset_dir.mkdir(parents=True)
    surface_files = {
        'strict_long_context_retriever_rows.jsonl': [{'retriever_example_id': 'r1'}],
        'strict_long_context_reranker_pairwise_rows.jsonl': [{'pairwise_example_id': 'p1'}],
        'strict_long_context_reranker_listwise_rows.jsonl': [{'listwise_example_id': 'l1'}],
        'strict_long_context_retriever_curriculum_rows.jsonl': [{'curriculum_example_id': 'c1'}],
    }
    for name, rows in surface_files.items():
        (dataset_dir / name).write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')

    raw_dataset_card = dataset_dir / 'strict_long_context_retrieval_datasets_card.json'
    raw_dataset_card.write_text(
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
                'dataset_card_path': str(raw_dataset_card.resolve()),
                'default_sampled_manifests': {'pure_grounded': '/tmp/fake.jsonl'},
            },
            sort_keys=True,
        ),
        encoding='utf-8',
    )
    bundle_card = tmp_path / 'bundle_card.json'
    bundle_card.write_text(
        json.dumps(
            {
                'retrieval_training_dataset_card_path': str(training_dataset_card.resolve()),
            },
            sort_keys=True,
        ),
        encoding='utf-8',
    )

    out_dir = tmp_path / 'mixture_nested_bundle'
    card = build_strict_long_context_retrieval_mixture_manifest(
        bundle_card_path=bundle_card,
        output_dir=out_dir,
        profile='pure_grounded',
    )
    assert card['dataset_card_path'] == str(raw_dataset_card.resolve())
    assert card['bundle_card_path'] == str(bundle_card.resolve())
    assert card['profile'] == 'pure_grounded'
