from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from materialize_strict_long_context_retrieval_mixture_rows import materialize_strict_long_context_retrieval_mixture_rows  # noqa: E402
from sample_strict_long_context_retrieval_mixture_rows import sample_strict_long_context_retrieval_mixture_rows  # noqa: E402


def test_retrieval_mixture_materialize_and_sample_applies_filters(tmp_path: Path) -> None:
    source = tmp_path / 'retriever_rows.jsonl'
    source.write_text(
        ''.join(
            json.dumps(row) + '\n'
            for row in [
                {'retriever_example_id': 'r1', 'split': 'train', 'join_type': 'repo+test', 'long_join_positive': True, 'locality_risk': False},
                {'retriever_example_id': 'r2', 'split': 'eval', 'join_type': 'repo+test', 'long_join_positive': False, 'locality_risk': True},
                {'retriever_example_id': 'r3', 'split': 'strict_eval', 'join_type': 'multi_repo', 'long_join_positive': True, 'locality_risk': False},
            ]
        ),
        encoding='utf-8',
    )
    manifest = tmp_path / 'manifest.jsonl'
    manifest.write_text(
        json.dumps({
            'surface': 'retriever_rows',
            'task_family': 'retriever_supervision',
            'path': str(source),
            'row_count': 3,
            'weight': 1.0,
            'dataset_card_path': str(tmp_path / 'card.json'),
            'profile': 'conservative_retriever',
            'filter_expr': 'long_join_positive==True',
        }) + '\n',
        encoding='utf-8',
    )

    materialized = materialize_strict_long_context_retrieval_mixture_rows(mixture_manifest_path=manifest, output_dir=tmp_path / 'materialized')
    materialized_rows = [json.loads(line) for line in Path(materialized['rows_path']).read_text(encoding='utf-8').splitlines() if line.strip()]
    assert [row['retriever_example_id'] for row in materialized_rows] == ['r1', 'r3']

    sampled = sample_strict_long_context_retrieval_mixture_rows(
        rows_path=Path(materialized['rows_path']),
        output_dir=tmp_path / 'sampled',
        max_train_rows=1,
        max_eval_rows=1,
        max_strict_rows=1,
        seed=0,
    )
    sampled_rows = [json.loads(line) for line in Path(sampled['manifest_path']).read_text(encoding='utf-8').splitlines() if line.strip()]
    assert len(sampled_rows) == 2
    assert {row['split'] for row in sampled_rows} == {'train', 'strict_eval'}
