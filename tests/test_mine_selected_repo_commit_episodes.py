from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from long_context_parquet import write_parquet_shard  # noqa: E402
from mine_selected_repo_commit_episodes import build_selected_repo_commit_episodes  # noqa: E402


def test_build_selected_repo_commit_episodes_matches_prefixed_paths_and_emits_verified_target(tmp_path: Path) -> None:
    if importlib.util.find_spec('pyarrow') is None:
        pytest.skip('pyarrow not installed')
    index_dir = tmp_path / 'index'
    chunks_dir = index_dir / 'chunks'
    chunks_dir.mkdir(parents=True)
    write_parquet_shard(
        chunks_dir / 'chunks-000000.parquet',
        [
            {
                'chunk_id': 'c1',
                'source_type': 'repo',
                'source_id': 'repo_alpha',
                'doc_id': 'repo_alpha/src/engine.py',
                'chunk_index': 0,
                'token_count': 40,
                'text': 'from src.helpers import compute_total\n\ndef run_order(x):\n    return compute_total(x)\n',
                'metadata_json': '{"path":"repo_alpha/src/engine.py"}',
            },
            {
                'chunk_id': 'c2',
                'source_type': 'repo',
                'source_id': 'repo_alpha',
                'doc_id': 'repo_alpha/src/helpers.py',
                'chunk_index': 0,
                'token_count': 35,
                'text': 'def compute_total(x):\n    return x + 1\n',
                'metadata_json': '{"path":"repo_alpha/src/helpers.py"}',
            },
            {
                'chunk_id': 'c3',
                'source_type': 'repo',
                'source_id': 'repo_alpha',
                'doc_id': 'repo_alpha/tests/test_engine.py',
                'chunk_index': 0,
                'token_count': 30,
                'text': 'from src.engine import run_order\n\ndef test_run_order():\n    assert run_order(1) == 2\n',
                'metadata_json': '{"path":"repo_alpha/tests/test_engine.py"}',
            },
            {
                'chunk_id': 'p1',
                'source_type': 'paper',
                'source_id': 'paper_attention_ops',
                'doc_id': 'methods',
                'chunk_index': 0,
                'token_count': 30,
                'text': 'compute_total semantics are preserved in the execution engine.',
                'metadata_json': '{"path":"paper/methods.txt"}',
            },
        ],
    )
    seeds = tmp_path / 'seeds.jsonl'
    seeds.write_text(
        json.dumps(
            {
                'seed_id': 's1',
                'seed_type': 'external_repo_commit',
                'repo_id': 'repo_alpha',
                'goal': 'Fix run_order behavior',
                'changes': [{'path': 'repo_alpha/src/engine.py', 'symbol': 'run_order'}],
                'metadata': {'commit_sha': 'abc123', 'commit_subject': 'Fix run_order behavior'},
            }
        ) + '\n',
        encoding='utf-8',
    )
    episodes, summary = build_selected_repo_commit_episodes(index_dir=index_dir, seeds_path=seeds)
    assert summary['episode_count'] == 1
    episode = episodes[0]
    assert episode['seed_paths'] == ['src/engine.py']
    roles = {(row['path'], row['role']) for row in episode['context_rows']}
    assert ('repo_alpha/src/engine.py', 'seed_change') in roles
    assert ('repo_alpha/src/helpers.py', 'repo_graph_neighbor') in roles
    assert ('repo_alpha/tests/test_engine.py', 'verification_constraint') in roles
    assert ('paper/methods.txt', 'algorithm_grounding') in roles
    assert episode['source_metadata']['route'] == 'COMMIT_PLUS_VERIFY'
    assert episode['selected_tests'] == ['tests/test_engine.py']
    assert episode['target']['state_after']['verification_targets'] == ['tests/test_engine.py']
    assert episode['target']['state_after']['execution_route'] == 'COMMIT_PLUS_VERIFY'


def test_build_selected_repo_commit_episodes_resolves_unique_suffix_paths(tmp_path: Path) -> None:
    if importlib.util.find_spec('pyarrow') is None:
        pytest.skip('pyarrow not installed')
    index_dir = tmp_path / 'index'
    chunks_dir = index_dir / 'chunks'
    chunks_dir.mkdir(parents=True)
    write_parquet_shard(
        chunks_dir / 'chunks-000000.parquet',
        [
            {
                'chunk_id': 'c1',
                'source_type': 'repo',
                'source_id': 'repo_alpha',
                'doc_id': 'repo_alpha/pkg/src/engine.py',
                'chunk_index': 0,
                'token_count': 40,
                'text': 'def run_order(x):\n    return x + 1\n',
                'metadata_json': '{"path":"pkg/src/engine.py"}',
            },
            {
                'chunk_id': 'c2',
                'source_type': 'repo',
                'source_id': 'repo_alpha',
                'doc_id': 'repo_alpha/tests/test_engine.py',
                'chunk_index': 0,
                'token_count': 30,
                'text': 'from pkg.src.engine import run_order\n\ndef test_run_order():\n    assert run_order(1) == 2\n',
                'metadata_json': '{"path":"tests/test_engine.py"}',
            },
        ],
    )
    seeds = tmp_path / 'seeds.jsonl'
    seeds.write_text(
        json.dumps(
            {
                'seed_id': 's1',
                'seed_type': 'external_repo_commit',
                'repo_id': 'repo_alpha',
                'goal': 'Fix run_order behavior',
                'changes': [{'path': 'repo_alpha/src/engine.py', 'symbol': 'run_order'}],
                'metadata': {'commit_sha': 'abc123', 'commit_subject': 'Fix run_order behavior'},
            }
        ) + '\n',
        encoding='utf-8',
    )
    episodes, summary = build_selected_repo_commit_episodes(index_dir=index_dir, seeds_path=seeds, include_papers=False)
    assert summary['episode_count'] == 1
    episode = episodes[0]
    assert episode['seed_paths'] == ['src/engine.py']
    roles = {(row['path'], row['role']) for row in episode['context_rows']}
    assert ('pkg/src/engine.py', 'seed_change') in roles
    assert ('tests/test_engine.py', 'verification_constraint') in roles



def test_build_selected_repo_commit_episodes_supports_broad_discovery_with_grounded_test_text(tmp_path: Path) -> None:
    if importlib.util.find_spec('pyarrow') is None:
        pytest.skip('pyarrow not installed')
    index_dir = tmp_path / 'index'
    chunks_dir = index_dir / 'chunks'
    chunks_dir.mkdir(parents=True)
    write_parquet_shard(
        chunks_dir / 'chunks-000000.parquet',
        [
            {
                'chunk_id': 'c1',
                'source_type': 'repo',
                'source_id': 'repo_beta',
                'doc_id': 'repo_beta/src/engine.py',
                'chunk_index': 0,
                'token_count': 40,
                'text': 'def run_order(x):\n    return compute_total(x)\n',
                'metadata_json': '{"path":"src/engine.py"}',
            },
            {
                'chunk_id': 'c2',
                'source_type': 'repo',
                'source_id': 'repo_beta',
                'doc_id': 'repo_beta/src/helpers.py',
                'chunk_index': 0,
                'token_count': 35,
                'text': 'def compute_total(x):\n    return x + 1\n',
                'metadata_json': '{"path":"src/helpers.py"}',
            },
            {
                'chunk_id': 'c3',
                'source_type': 'repo',
                'source_id': 'repo_beta',
                'doc_id': 'repo_beta/tests/test_runtime_behavior.py',
                'chunk_index': 0,
                'token_count': 45,
                'text': 'from src.engine import run_order\n\n\ndef test_runtime_behavior():\n    assert run_order(1) == 2\n',
                'metadata_json': '{"path":"tests/test_runtime_behavior.py"}',
            },
        ],
    )
    seeds = tmp_path / 'seeds.jsonl'
    seeds.write_text(
        json.dumps(
            {
                'seed_id': 's1',
                'seed_type': 'external_repo_commit',
                'repo_id': 'repo_beta',
                'goal': 'Repair runtime behavior for run_order using compute_total semantics',
                'changes': [{'path': 'src/engine.py'}],
                'metadata': {'commit_sha': 'def456', 'commit_subject': 'Repair runtime behavior'},
            }
        ) + '\n',
        encoding='utf-8',
    )
    episodes, summary = build_selected_repo_commit_episodes(index_dir=index_dir, seeds_path=seeds, include_papers=False, allow_broad_discovery=True)
    assert summary['episode_count'] == 1
    assert summary['route_counts']['NEEDS_BROAD_TEST_DISCOVERY'] == 1
    assert summary['route_counts']['PASS_BROAD_TEST_DISCOVERY'] == 1
    episode = episodes[0]
    assert episode['selected_tests'] == ['tests/test_runtime_behavior.py']
    assert episode['test_selection_route'] == 'PASS_BROAD_TEST_DISCOVERY'
    verification_rows = [row for row in episode['context_rows'] if row['role'] == 'verification_constraint']
    assert verification_rows
    assert verification_rows[0]['path'] == 'tests/test_runtime_behavior.py'
    assert 'lexical_overlap' in verification_rows[0]['retrieval_reason'] or 'shared_seed_symbol' in verification_rows[0]['retrieval_reason']



def test_build_selected_repo_commit_episodes_supports_broad_verification_artifact_discovery(tmp_path: Path) -> None:
    if importlib.util.find_spec('pyarrow') is None:
        pytest.skip('pyarrow not installed')
    index_dir = tmp_path / 'index'
    chunks_dir = index_dir / 'chunks'
    chunks_dir.mkdir(parents=True)
    write_parquet_shard(
        chunks_dir / 'chunks-000000.parquet',
        [
            {
                'chunk_id': 'c1',
                'source_type': 'repo',
                'source_id': 'repo_gamma',
                'doc_id': 'repo_gamma/src/trainer.py',
                'chunk_index': 0,
                'token_count': 40,
                'text': 'def train_epoch(model):\n    return model.step()\n',
                'metadata_json': '{"path":"src/trainer.py"}',
            },
            {
                'chunk_id': 'c2',
                'source_type': 'repo',
                'source_id': 'repo_gamma',
                'doc_id': 'repo_gamma/full_eval.py',
                'chunk_index': 0,
                'token_count': 45,
                'text': 'from src.trainer import train_epoch\n\n\ndef run_full_eval(model):\n    return train_epoch(model)\n',
                'metadata_json': '{"path":"full_eval.py"}',
            },
        ],
    )
    seeds = tmp_path / 'seeds.jsonl'
    seeds.write_text(
        json.dumps(
            {
                'seed_id': 's1',
                'seed_type': 'external_repo_commit',
                'repo_id': 'repo_gamma',
                'goal': 'Repair training evaluation behavior for train_epoch',
                'changes': [{'path': 'src/trainer.py'}],
                'metadata': {'commit_sha': 'ghi789', 'commit_subject': 'Repair train epoch'},
            }
        ) + '\n',
        encoding='utf-8',
    )
    episodes, summary = build_selected_repo_commit_episodes(index_dir=index_dir, seeds_path=seeds, include_papers=False, allow_broad_discovery=True)
    assert summary['episode_count'] == 1
    assert summary['route_counts']['NEEDS_BROAD_TEST_DISCOVERY'] == 1
    assert summary['route_counts']['PASS_BROAD_VERIFICATION_DISCOVERY'] == 1
    episode = episodes[0]
    assert episode['selected_tests'] == ['full_eval.py']
    assert episode['test_selection_route'] == 'PASS_BROAD_VERIFICATION_DISCOVERY'
    verification_rows = [row for row in episode['context_rows'] if row['role'] == 'verification_constraint']
    assert verification_rows[0]['path'] == 'full_eval.py'


def test_build_selected_repo_commit_episodes_supports_explicit_local_repo_mode(tmp_path: Path) -> None:
    repo_root = tmp_path / 'repos'
    repo = repo_root / 'repo_local'
    (repo / 'src').mkdir(parents=True)
    (repo / 'tests').mkdir(parents=True)
    (repo / 'src' / 'engine.py').write_text('from src.helpers import compute_total\n\ndef run_order(x):\n    return compute_total(x)\n', encoding='utf-8')
    (repo / 'src' / 'helpers.py').write_text('def compute_total(x):\n    return x + 1\n', encoding='utf-8')
    (repo / 'tests' / 'test_engine.py').write_text('from src.engine import run_order\n\ndef test_run_order():\n    assert run_order(1) == 2\n', encoding='utf-8')

    seeds = tmp_path / 'seeds_local.jsonl'
    seeds.write_text(
        json.dumps(
            {
                'seed_id': 's_local',
                'seed_type': 'external_repo_commit',
                'repo_id': 'repo_local',
                'goal': 'Fix run_order behavior',
                'changes': [{'path': 'repo_local/src/engine.py', 'symbol': 'run_order'}],
                'metadata': {'commit_sha': 'abc123', 'commit_subject': 'Fix run_order behavior'},
            }
        ) + '\n',
        encoding='utf-8',
    )

    episodes, summary = build_selected_repo_commit_episodes(
        repositories_root=repo_root,
        seeds_path=seeds,
        include_papers=False,
        root_file_limit=20,
        neighbor_dir_file_limit=20,
        max_total_candidates=50,
    )

    assert summary['source_mode'] == 'repositories_root'
    assert summary['episode_count'] == 1
    episode = episodes[0]
    assert episode['seed_paths'] == ['src/engine.py']
    assert episode['selected_tests'] == ['tests/test_engine.py']
    assert episode['source_metadata']['source_mode'] == 'repositories_root'
    roles = {(row['path'], row['role']) for row in episode['context_rows']}
    assert ('src/engine.py', 'seed_change') in roles
    assert ('src/helpers.py', 'repo_graph_neighbor') in roles
    assert ('tests/test_engine.py', 'verification_constraint') in roles


def test_build_selected_repo_commit_episodes_rejects_papers_in_local_repo_mode(tmp_path: Path) -> None:
    repo_root = tmp_path / 'repos'
    repo_root.mkdir(parents=True)
    seeds = tmp_path / 'seeds_local.jsonl'
    seeds.write_text(
        json.dumps(
            {
                'seed_id': 's_local',
                'seed_type': 'external_repo_commit',
                'repo_id': 'repo_local',
                'goal': 'Fix run_order behavior',
                'changes': [{'path': 'repo_local/src/engine.py'}],
            }
        ) + '\n',
        encoding='utf-8',
    )

    with pytest.raises(ValueError, match='papers_require_index_dir'):
        build_selected_repo_commit_episodes(repositories_root=repo_root, seeds_path=seeds, include_papers=True)
