from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from materialize_long_context_pack_training import (  # noqa: E402
    build_long_context_pack_trainer_rows,
    materialize_long_context_pack_training,
)


def _write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding='utf-8')
    return path


def _write_jsonl(path: Path, rows: list[dict]) -> Path:
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')
    return path


def test_build_long_context_pack_trainer_rows_family_aware_mode_forces_train_split(tmp_path: Path) -> None:
    training_rows = _write_jsonl(
        tmp_path / 'training_rows.jsonl',
        [
            {'pack_id': 'p1', 'prompt_text': 'q1', 'context_rows': [{'chunk_id': 'a'}], 'target_rows': [{'candidate_id': 'c1'}], 'pack_token_count': 100, 'chunk_count': 1, 'candidate_count': 1},
            {'pack_id': 'p2', 'prompt_text': 'q2', 'context_rows': [{'chunk_id': 'b'}], 'target_rows': [{'candidate_id': 'c2'}], 'pack_token_count': 90, 'chunk_count': 1, 'candidate_count': 1},
        ],
    )
    splits = _write_jsonl(
        tmp_path / 'splits.jsonl',
        [
            {'pack_id': 'p1', 'split': 'train'},
            {'pack_id': 'p2', 'split': 'val'},
        ],
    )
    cluster = _write_json(
        tmp_path / 'cluster.json',
        {'clusters': [{'cluster_id': 'cluster_0001', 'pack_count': 2, 'cluster_token_count': 190, 'cluster_chunk_union_count': 2, 'pack_ids': ['p1', 'p2']}]},
    )
    gate = _write_json(
        tmp_path / 'gate.json',
        {'trainer_policy': {'recommended_training_mode': 'family_cluster_constrained_training', 'independent_heldout_eval_allowed': False, 'family_aware_training_required': True}},
    )
    rows, audit = build_long_context_pack_trainer_rows(
        training_rows_path=training_rows,
        split_assignments_path=splits,
        cluster_summary_path=cluster,
        gate_path=gate,
    )
    assert audit['effective_split_counts'] == {'train': 2}
    assert all(row['effective_split'] == 'train' for row in rows)
    assert all(row['eval_eligible'] is False for row in rows)
    assert {row['overlap_family_id'] for row in rows} == {'cluster_0001'}


def test_build_long_context_pack_trainer_rows_independent_eval_preserves_requested_split(tmp_path: Path) -> None:
    training_rows = _write_jsonl(
        tmp_path / 'training_rows.jsonl',
        [{'pack_id': 'p1', 'prompt_text': 'q1', 'context_rows': [], 'target_rows': [], 'pack_token_count': 100, 'chunk_count': 1, 'candidate_count': 1}],
    )
    splits = _write_jsonl(tmp_path / 'splits.jsonl', [{'pack_id': 'p1', 'split': 'test'}])
    cluster = _write_json(
        tmp_path / 'cluster.json',
        {'clusters': [{'cluster_id': 'cluster_0001', 'pack_count': 1, 'cluster_token_count': 100, 'cluster_chunk_union_count': 1, 'pack_ids': ['p1']}]},
    )
    gate = _write_json(
        tmp_path / 'gate.json',
        {'trainer_policy': {'recommended_training_mode': 'standard_pack_training', 'independent_heldout_eval_allowed': True, 'family_aware_training_required': False}},
    )
    rows, audit = build_long_context_pack_trainer_rows(
        training_rows_path=training_rows,
        split_assignments_path=splits,
        cluster_summary_path=cluster,
        gate_path=gate,
    )
    assert audit['effective_split_counts'] == {'test': 1}
    assert rows[0]['effective_split'] == 'test'
    assert rows[0]['eval_eligible'] is True


def test_materialize_long_context_pack_training_writes_outputs(tmp_path: Path) -> None:
    training_rows = _write_jsonl(
        tmp_path / 'training_rows.jsonl',
        [{'pack_id': 'p1', 'prompt_text': 'q1', 'context_rows': [], 'target_rows': [], 'pack_token_count': 100, 'chunk_count': 1, 'candidate_count': 1}],
    )
    splits = _write_jsonl(tmp_path / 'splits.jsonl', [{'pack_id': 'p1', 'split': 'train'}])
    cluster = _write_json(
        tmp_path / 'cluster.json',
        {'clusters': [{'cluster_id': 'cluster_0001', 'pack_count': 1, 'cluster_token_count': 100, 'cluster_chunk_union_count': 1, 'pack_ids': ['p1']}]},
    )
    gate = _write_json(
        tmp_path / 'gate.json',
        {'trainer_policy': {'recommended_training_mode': 'single_family_train_only_or_more_mining_required', 'independent_heldout_eval_allowed': False, 'family_aware_training_required': True}},
    )
    result = materialize_long_context_pack_training(
        training_rows_path=training_rows,
        split_assignments_path=splits,
        cluster_summary_path=cluster,
        gate_path=gate,
        output_dir=tmp_path / 'out',
    )
    assert result['passed'] is True
    assert (tmp_path / 'out' / 'trainer_rows.jsonl').exists()
    assert (tmp_path / 'out' / 'trainer_audit.json').exists()
    assert (tmp_path / 'out' / 'trainer_input.json').exists()
