from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import build_long_context_candidate_packs as candidate_pack_builder  # noqa: E402
from build_long_context_candidate_packs import build_candidate_packs  # noqa: E402
from build_stage8801_long_context_corpus_index import build_chunk_and_mention_shards  # noqa: E402


def _make_index(root: Path) -> tuple[Path, list[str]]:
    papers = root / 'papers'
    repos = root / 'repositories'
    datasets = root / 'datasets'
    (papers / 'paper_a').mkdir(parents=True)
    (repos / 'repo_a').mkdir(parents=True)
    (datasets / 'trace_a').mkdir(parents=True)
    (papers / 'paper_a' / 'method.txt').write_text('online update improves convergence\n' * 8, encoding='utf-8')
    (repos / 'repo_a' / 'engine.py').write_text('def online_update():\n    return True\n' * 10, encoding='utf-8')
    (datasets / 'trace_a' / 'failure.txt').write_text('trace says regression after patch\n' * 8, encoding='utf-8')
    out = root / 'index'
    build_chunk_and_mention_shards(
        paper_roots=[papers],
        repo_roots=[repos],
        dataset_roots=[datasets],
        output_dir=out,
        paper_chunk_tokens=24,
        repo_chunk_tokens=24,
        trace_chunk_tokens=24,
        rows_per_shard=8,
    )
    import pyarrow.parquet as pq
    chunk_ids = []
    for shard in sorted((out / 'chunks').glob('*.parquet')):
        for row in pq.read_table(shard).to_pylist():
            chunk_ids.append(str(row['chunk_id']))
    return out, chunk_ids


def test_build_candidate_packs_groups_support_chunks_into_training_rows(tmp_path: Path) -> None:
    if importlib.util.find_spec('pyarrow') is None:
        pytest.skip('pyarrow not installed')
    index_dir, chunk_ids = _make_index(tmp_path)
    candidates = [
        {
            'candidate_id': 'cand1',
            'canonical_name': 'online_update',
            'supporting_chunk_ids': [chunk_ids[0], chunk_ids[1]],
            'final_state': {'online_update_active': True},
            'state_variable': 'online_update_active',
            'model_assisted_signals': {'provider': 'heuristic_proxy_v1'},
        },
        {
            'candidate_id': 'cand2',
            'canonical_name': 'controller_state',
            'supporting_chunk_ids': [chunk_ids[1], chunk_ids[2]],
            'final_state': {'controller_state_active': False},
            'state_variable': 'controller_state_active',
            'model_assisted_signals': {'provider': 'heuristic_proxy_v1'},
        },
    ]
    candidates_path = tmp_path / 'candidates.jsonl'
    candidates_path.write_text(''.join(json.dumps(row) + '\n' for row in candidates), encoding='utf-8')
    packs, pack_chunk_rows, training_rows, summary = build_candidate_packs(
        index_dir=index_dir,
        candidates_path=candidates_path,
        target_pack_tokens=120,
        min_pack_tokens=40,
    )
    assert packs
    assert training_rows
    assert summary['total_candidates_consumed'] == 2
    assert training_rows[0]['context_rows']
    assert training_rows[0]['target_rows']
    assert 'PACK_QUERIES:' in training_rows[0]['prompt_text']
    assert any(row['source_type'] == 'repo' for row in pack_chunk_rows)


def test_build_candidate_packs_marks_underfilled_residual_pack(tmp_path: Path) -> None:
    if importlib.util.find_spec('pyarrow') is None:
        pytest.skip('pyarrow not installed')
    index_dir, chunk_ids = _make_index(tmp_path)
    candidates = [
        {
            'candidate_id': 'cand1',
            'canonical_name': 'online_update',
            'supporting_chunk_ids': [chunk_ids[0], chunk_ids[1]],
            'final_state': {'online_update_active': True},
            'state_variable': 'online_update_active',
            'model_assisted_signals': {'provider': 'heuristic_proxy_v1'},
        },
        {
            'candidate_id': 'cand2',
            'canonical_name': 'controller_state',
            'supporting_chunk_ids': [chunk_ids[2], chunk_ids[3]],
            'final_state': {'controller_state_active': False},
            'state_variable': 'controller_state_active',
            'model_assisted_signals': {'provider': 'heuristic_proxy_v1'},
        },
    ]
    candidates_path = tmp_path / 'candidates.jsonl'
    candidates_path.write_text(''.join(json.dumps(row) + '\n' for row in candidates), encoding='utf-8')
    packs, _pack_chunk_rows, _training_rows, summary = build_candidate_packs(
        index_dir=index_dir,
        candidates_path=candidates_path,
        target_pack_tokens=1,
        min_pack_tokens=999999,
        max_candidates_per_pack=1,
    )
    assert len(packs) == 2
    assert all(not pack['meets_min_pack_tokens'] for pack in packs)
    assert summary['underfilled_pack_count'] == 2
    assert summary['packs_meeting_min_tokens'] == 0
    assert len(summary['underfilled_pack_ids']) == 2


def test_build_candidate_packs_rebalances_overlap_tail(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    chunk_rows = [
        {'chunk_id': 'a', 'source_type': 'paper', 'source_id': 's1', 'doc_id': 'd1', 'chunk_index': 0, 'token_count': 40, 'metadata_json': '{}', 'modality': 'text', 'text': 'a'},
        {'chunk_id': 'b', 'source_type': 'paper', 'source_id': 's1', 'doc_id': 'd1', 'chunk_index': 1, 'token_count': 40, 'metadata_json': '{}', 'modality': 'text', 'text': 'b'},
        {'chunk_id': 'c', 'source_type': 'repo', 'source_id': 's2', 'doc_id': 'd2', 'chunk_index': 0, 'token_count': 40, 'metadata_json': '{}', 'modality': 'code', 'text': 'c'},
        {'chunk_id': 'd', 'source_type': 'repo', 'source_id': 's2', 'doc_id': 'd2', 'chunk_index': 1, 'token_count': 40, 'metadata_json': '{}', 'modality': 'code', 'text': 'd'},
        {'chunk_id': 'e', 'source_type': 'repo', 'source_id': 's3', 'doc_id': 'd3', 'chunk_index': 0, 'token_count': 40, 'metadata_json': '{}', 'modality': 'code', 'text': 'e'},
        {'chunk_id': 'f', 'source_type': 'repo', 'source_id': 's3', 'doc_id': 'd3', 'chunk_index': 1, 'token_count': 40, 'metadata_json': '{}', 'modality': 'code', 'text': 'f'},
    ]
    candidates = [
        {'candidate_id': 'cand_a', 'canonical_name': 'alpha_state', 'supporting_chunk_ids': ['a', 'b', 'c'], 'final_state': {'alpha_state_active': True}, 'state_variable': 'alpha_state_active', 'model_assisted_signals': {}},
        {'candidate_id': 'cand_b', 'canonical_name': 'beta_state', 'supporting_chunk_ids': ['c', 'd'], 'final_state': {'beta_state_active': True}, 'state_variable': 'beta_state_active', 'model_assisted_signals': {}},
        {'candidate_id': 'cand_c', 'canonical_name': 'gamma_state', 'supporting_chunk_ids': ['e', 'f'], 'final_state': {'gamma_state_active': True}, 'state_variable': 'gamma_state_active', 'model_assisted_signals': {}},
    ]
    monkeypatch.setattr(candidate_pack_builder, '_read_chunk_rows', lambda _index_dir: chunk_rows)
    monkeypatch.setattr(candidate_pack_builder, 'read_jsonl', lambda _path: candidates)
    packs, _pack_chunk_rows, _training_rows, summary = candidate_pack_builder.build_candidate_packs(
        index_dir=tmp_path / 'index',
        candidates_path=tmp_path / 'candidates.jsonl',
        target_pack_tokens=160,
        min_pack_tokens=120,
    )
    assert len(packs) == 2
    assert summary['underfilled_pack_count'] == 0
    assert summary['packs_meeting_min_tokens'] == 2
    assert all(pack['pack_token_count'] >= 120 for pack in packs)
    assert sorted(pack['pack_token_count'] for pack in packs) == [120, 160]
