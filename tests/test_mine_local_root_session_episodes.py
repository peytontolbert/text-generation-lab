from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from mine_local_root_session_episodes import _repo_index_from_paths, mine_local_root_session_episodes  # noqa: E402


def test_mine_local_root_session_episodes_builds_strict_execution_grounded_context(tmp_path: Path) -> None:
    repo = tmp_path / 'repo_a'
    (repo / 'src').mkdir(parents=True)
    (repo / 'tests').mkdir(parents=True)
    (repo / 'src' / 'helpers.py').write_text('def compute_total(x):\n    return x + 1\n', encoding='utf-8')
    (repo / 'src' / 'engine.py').write_text('from src.helpers import compute_total\n\ndef run_order(x):\n    return compute_total(x)\n', encoding='utf-8')
    (repo / 'tests' / 'test_engine.py').write_text('from src.engine import run_order\n\ndef test_run_order():\n    assert run_order(1) == 2\n', encoding='utf-8')

    seeds = tmp_path / 'resolved.jsonl'
    seeds.write_text(
        json.dumps(
            {
                'seed_id': 's1',
                'local_repo_root': str(repo),
                'goal': 'repair_or_edit | patch_tool_used',
                'changes': [{'path': str(repo / 'src' / 'engine.py')}],
                'metadata': {'route': 'PATCH_PLUS_EXEC'},
            },
            sort_keys=True,
        )
        + '\n',
        encoding='utf-8',
    )

    episodes, summary = mine_local_root_session_episodes(resolved_local_seeds_path=seeds)
    assert summary['episode_count'] == 1
    episode = episodes[0]
    assert episode['repo_id'] == 'repo_a'
    assert 'src/engine.py' in episode['seed_paths']
    assert episode['candidate_file_count'] >= 3
    roles = {(row['path'], row['role']) for row in episode['context_rows']}
    assert ('src/engine.py', 'seed_change') in roles
    assert ('src/helpers.py', 'repo_graph_neighbor') in roles
    assert ('tests/test_engine.py', 'verification_constraint') in roles
    assert episode['source_metadata']['route'] == 'PATCH_PLUS_EXEC'
    assert episode['selected_tests'] == ['tests/test_engine.py']
    assert episode['target']['state_after']['verification_targets'] == ['tests/test_engine.py']
    assert 'Changed files:' in episode['goal']


def test_mine_local_root_session_episodes_skips_weak_patch_only_sessions(tmp_path: Path) -> None:
    repo = tmp_path / 'repo_budget'
    (repo / 'src').mkdir(parents=True)
    (repo / 'tests').mkdir(parents=True)
    (repo / 'src' / 'engine.py').write_text('def run_order(x):\n    return x\n', encoding='utf-8')
    (repo / 'tests' / 'test_engine.py').write_text('from src.engine import run_order\n\ndef test_run_order():\n    assert run_order(1) == 1\n', encoding='utf-8')

    seeds = tmp_path / 'resolved_budget.jsonl'
    seeds.write_text(
        json.dumps(
            {
                'seed_id': 'budget_1',
                'local_repo_root': str(repo),
                'goal': 'repair_or_edit | patch_tool_used',
                'changes': [{'path': str(repo / 'src' / 'engine.py')}],
                'metadata': {'route': 'PATCH_ONLY'},
            },
            sort_keys=True,
        )
        + '\n',
        encoding='utf-8',
    )

    episodes, summary = mine_local_root_session_episodes(
        resolved_local_seeds_path=seeds,
        root_file_limit=2,
        neighbor_dir_file_limit=2,
        max_total_candidates=5,
    )
    assert summary['episode_count'] == 0
    assert summary['route_counts']['SKIP_WEAK_EXECUTION_ROUTE'] == 1


def test_mine_local_root_session_episodes_attaches_matching_session_traces(tmp_path: Path) -> None:
    repo = tmp_path / 'repo_trace'
    (repo / 'src').mkdir(parents=True)
    (repo / 'tests').mkdir(parents=True)
    (repo / 'src' / 'engine.py').write_text('def run_order(x):\n    return x\n', encoding='utf-8')
    (repo / 'tests' / 'test_engine.py').write_text('from src.engine import run_order\n\ndef test_run_order():\n    assert run_order(1) == 1\n', encoding='utf-8')

    seeds = tmp_path / 'resolved_trace.jsonl'
    seeds.write_text(
        json.dumps(
            {
                'seed_id': 's_trace',
                'seed_type': 'session_episode_local_root',
                'source_root_label': 'codex_sessions',
                'session_id_hint': 'rollout-trace',
                'repo_hint': 'repo_trace',
                'local_repo_root': str(repo),
                'goal': 'repair_or_edit | verification_observed | patch_tool_used',
                'changes': [{'path': str(repo / 'src' / 'engine.py')}],
                'metadata': {'route': 'PATCH_PLUS_EXEC'},
            },
            sort_keys=True,
        )
        + '\n',
        encoding='utf-8',
    )
    traces = tmp_path / 'traces.jsonl'
    traces.write_text(
        json.dumps(
            {
                'trace_id': 'trace_1',
                'source_root_label': 'codex_sessions',
                'session_id_hint': 'rollout-trace',
                'repo_hint': 'repo_trace',
                'command_head': 'pytest',
                'exit_code': 1,
                'signal_kind': 'verification',
                'file_path_refs': ['src/engine.py', 'tests/test_engine.py'],
                'runtime_trace': {'failure_type': 'test_assertion_failure'},
                'summary_text': 'Session repo: repo_trace\nCommand head: pytest\nCommand: pytest -q tests/test_engine.py\nExit code: 1\nFailure type: test_assertion_failure\nReferenced paths: src/engine.py, tests/test_engine.py',
            },
            sort_keys=True,
        )
        + '\n',
        encoding='utf-8',
    )

    episodes, summary = mine_local_root_session_episodes(
        resolved_local_seeds_path=seeds,
        execution_traces_path=traces,
        max_trace_rows=2,
    )

    assert summary['episode_count'] == 1
    episode = episodes[0]
    trace_rows = [row for row in episode['context_rows'] if row['role'] == 'trace_analogue']
    assert len(trace_rows) == 1
    assert trace_rows[0]['source_type'] == 'dataset'
    assert trace_rows[0]['path'].endswith('trace_1.trace.txt')
    assert 'pytest' in trace_rows[0]['retrieval_reason']


def test_mine_local_root_session_episodes_excludes_unrelated_record_tests(tmp_path: Path) -> None:
    repo = tmp_path / 'repo_record_tests'
    (repo / 'src').mkdir(parents=True)
    (repo / 'tests').mkdir(parents=True)
    (repo / 'records' / 'archived' / 'tests').mkdir(parents=True)
    (repo / 'src' / 'engine.py').write_text('def tensor_loader(x):\n    return x + 1\n', encoding='utf-8')
    (repo / 'tests' / 'test_engine.py').write_text('from src.engine import tensor_loader\n\ndef test_engine():\n    assert tensor_loader(1) == 2\n', encoding='utf-8')
    (repo / 'records' / 'archived' / 'tests' / 'test_engine.py').write_text('def test_engine():\n    assert False\n', encoding='utf-8')

    seeds = tmp_path / 'resolved_record_tests.jsonl'
    seeds.write_text(
        json.dumps(
            {
                'seed_id': 's_record_tests',
                'seed_type': 'session_episode_local_root',
                'source_root_label': 'codex_sessions',
                'session_id_hint': 'rollout-record-tests',
                'repo_hint': 'repo_record_tests',
                'local_repo_root': str(repo),
                'goal': 'Modify repository files to preserve behavior under execution-backed maintenance.\nChanged files: src/engine.py\nVerification targets: tests/test_engine.py\nKey symbols: tensor_loader\nExecution route: PATCH_PLUS_EXEC',
                'changes': [{'path': str(repo / 'src' / 'engine.py')}],
                'metadata': {'route': 'PATCH_PLUS_EXEC'},
            },
            sort_keys=True,
        )
        + '\n',
        encoding='utf-8',
    )

    episodes, summary = mine_local_root_session_episodes(
        resolved_local_seeds_path=seeds,
        root_file_limit=20,
        neighbor_dir_file_limit=20,
        max_total_candidates=40,
    )

    assert summary['episode_count'] == 1
    episode = episodes[0]
    verification_rows = [row for row in episode['context_rows'] if row['role'] == 'verification_constraint']
    assert verification_rows
    assert all('records/' not in row['path'] for row in verification_rows)
    assert verification_rows[0]['path'] == 'tests/test_engine.py'


def test_mine_local_root_session_episodes_excludes_unrelated_verification_artifacts(tmp_path: Path) -> None:
    repo = tmp_path / 'repo_verify_filter'
    (repo / 'src').mkdir(parents=True)
    (repo / 'configs').mkdir(parents=True)
    (repo / 'helpful_repos' / 'foreign' / 'logs').mkdir(parents=True)
    (repo / 'src' / 'engine.py').write_text('def tensor_loader(x):\n    return x + 1\n', encoding='utf-8')
    (repo / 'configs' / 'tensor_loader_smoke.yaml').write_text('entry: tensor_loader\ncheck: verify tensor loader batch output\n', encoding='utf-8')
    (repo / 'helpful_repos' / 'foreign' / 'logs' / 'tensor_loader_smoke.txt').write_text('tensor_loader smoke output\n', encoding='utf-8')

    seeds = tmp_path / 'resolved_verify_filter.jsonl'
    seeds.write_text(
        json.dumps(
            {
                'seed_id': 's_verify_filter',
                'seed_type': 'session_episode_local_root',
                'source_root_label': 'codex_sessions',
                'session_id_hint': 'rollout-verify-filter',
                'repo_hint': 'repo_verify_filter',
                'local_repo_root': str(repo),
                'goal': 'Modify repository files to preserve behavior under execution-backed maintenance.\nChanged files: src/engine.py\nVerification targets: configs/tensor_loader_smoke.yaml\nKey symbols: tensor_loader\nExecution route: PATCH_PLUS_EXEC',
                'changes': [{'path': str(repo / 'src' / 'engine.py')}],
                'metadata': {'route': 'PATCH_PLUS_EXEC'},
            },
            sort_keys=True,
        )
        + '\n',
        encoding='utf-8',
    )

    episodes, summary = mine_local_root_session_episodes(
        resolved_local_seeds_path=seeds,
        root_file_limit=20,
        neighbor_dir_file_limit=20,
        max_total_candidates=40,
    )

    assert summary['episode_count'] == 1
    episode = episodes[0]
    verification_rows = [row for row in episode['context_rows'] if row['role'] == 'verification_constraint']
    assert verification_rows
    assert verification_rows[0]['path'] == 'configs/tensor_loader_smoke.yaml'
    assert all('helpful_repos/' not in row['path'] for row in verification_rows)


def test_mine_local_root_session_episodes_rejects_generic_verification_artifact_without_focus_overlap(tmp_path: Path) -> None:
    repo = tmp_path / 'repo_generic_verify'
    (repo / 'src').mkdir(parents=True)
    (repo / 'data').mkdir(parents=True)
    (repo / 'src' / 'train_gpt_upgrade.py').write_text('def train_upgrade(x):\n    return x + 1\n', encoding='utf-8')
    (repo / 'data' / 'tokenizer_specs.json').write_text('{"tokenizer": "bpe", "spec": "generic"}\n', encoding='utf-8')

    seeds = tmp_path / 'resolved_generic_verify.jsonl'
    seeds.write_text(
        json.dumps(
            {
                'seed_id': 's_generic_verify',
                'seed_type': 'session_episode_local_root',
                'source_root_label': 'codex_sessions',
                'session_id_hint': 'rollout-generic-verify',
                'repo_hint': 'repo_generic_verify',
                'local_repo_root': str(repo),
                'goal': 'repair_or_edit | patch_tool_used',
                'changes': [{'path': str(repo / 'src' / 'train_gpt_upgrade.py')}],
                'metadata': {'route': 'PATCH_PLUS_EXEC'},
            },
            sort_keys=True,
        )
        + '\n',
        encoding='utf-8',
    )

    episodes, summary = mine_local_root_session_episodes(
        resolved_local_seeds_path=seeds,
        root_file_limit=20,
        neighbor_dir_file_limit=20,
        max_total_candidates=40,
    )

    assert summary['episode_count'] == 0
    assert summary['route_counts']['SKIP_NO_SELECTED_TESTS'] == 1


def test_mine_local_root_session_episodes_supports_broad_verification_discovery(tmp_path: Path) -> None:
    repo = tmp_path / 'repo_verify'
    (repo / 'src').mkdir(parents=True)
    (repo / 'configs').mkdir(parents=True)
    (repo / 'src' / 'engine.py').write_text('def tensor_loader(x):\n    return x + 1\n', encoding='utf-8')
    (repo / 'configs' / 'tensor_loader_smoke.yaml').write_text('entry: tensor_loader\ncheck: verify tensor loader batch output\n', encoding='utf-8')

    seeds = tmp_path / 'resolved_verify.jsonl'
    seeds.write_text(
        json.dumps(
            {
                'seed_id': 's_verify',
                'seed_type': 'session_episode_local_root',
                'source_root_label': 'codex_sessions',
                'session_id_hint': 'rollout-verify',
                'repo_hint': 'repo_verify',
                'local_repo_root': str(repo),
                'goal': 'Modify repository files to preserve behavior under execution-backed maintenance.\nChanged files: src/engine.py\nVerification targets: configs/tensor_loader_smoke.yaml\nKey symbols: tensor_loader\nExecution route: PATCH_PLUS_EXEC',
                'changes': [{'path': str(repo / 'src' / 'engine.py')}],
                'metadata': {'route': 'PATCH_PLUS_EXEC'},
            },
            sort_keys=True,
        )
        + '\n',
        encoding='utf-8',
    )

    episodes, summary = mine_local_root_session_episodes(
        resolved_local_seeds_path=seeds,
        root_file_limit=1,
        neighbor_dir_file_limit=1,
        max_total_candidates=2,
    )

    assert summary['episode_count'] == 1
    assert summary['route_counts']['PASS_BROAD_VERIFICATION_DISCOVERY'] == 1
    episode = episodes[0]
    assert episode['test_selection_route'] == 'PASS_BROAD_VERIFICATION_DISCOVERY'
    verification_rows = [row for row in episode['context_rows'] if row['role'] == 'verification_constraint']
    assert verification_rows
    assert verification_rows[0]['path'] == 'configs/tensor_loader_smoke.yaml'
    assert 'verification_marker' in verification_rows[0]['retrieval_reason']


def test_mine_local_root_session_episodes_supports_broad_test_discovery(tmp_path: Path) -> None:
    repo = tmp_path / 'repo_broad'
    (repo / 'src').mkdir(parents=True)
    (repo / 'tests').mkdir(parents=True)
    (repo / 'src' / 'engine.py').write_text('def tensor_loader(x):\n    return x + 1\n', encoding='utf-8')
    (repo / 'tests' / 'test_runtime_behavior.py').write_text('from src.engine import tensor_loader\n\ndef test_runtime_behavior():\n    assert tensor_loader(1) == 2\n', encoding='utf-8')

    seeds = tmp_path / 'resolved_broad.jsonl'
    seeds.write_text(
        json.dumps(
            {
                'seed_id': 's_broad',
                'seed_type': 'session_episode_local_root',
                'source_root_label': 'codex_sessions',
                'session_id_hint': 'rollout-broad',
                'repo_hint': 'repo_broad',
                'local_repo_root': str(repo),
                'goal': 'Modify repository files to preserve behavior under execution-backed maintenance.\nChanged files: src/engine.py\nVerification targets: tests/test_runtime_behavior.py\nKey symbols: tensor_loader\nExecution route: PATCH_PLUS_EXEC',
                'changes': [{'path': str(repo / 'src' / 'engine.py')}],
                'metadata': {'route': 'PATCH_PLUS_EXEC'},
            },
            sort_keys=True,
        )
        + '\n',
        encoding='utf-8',
    )

    episodes, summary = mine_local_root_session_episodes(
        resolved_local_seeds_path=seeds,
        root_file_limit=1,
        neighbor_dir_file_limit=1,
        max_total_candidates=2,
    )

    assert summary['episode_count'] == 1
    assert summary['route_counts']['PASS_BROAD_TEST_DISCOVERY'] == 1
    episode = episodes[0]
    verification_rows = [row for row in episode['context_rows'] if row['role'] == 'verification_constraint']
    assert verification_rows
    assert verification_rows[0]['path'] == 'tests/test_runtime_behavior.py'
    assert 'lexical_overlap' in verification_rows[0]['retrieval_reason'] or 'shared_seed_symbol' in verification_rows[0]['retrieval_reason']


def test_repo_index_from_paths_records_python_parse_failures(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / 'repo_parse_fail'
    (repo / 'src').mkdir(parents=True)
    target = repo / 'src' / 'broken.py'
    target.write_text("x = 1\n", encoding='utf-8')

    def _raise(*args, **kwargs):
        raise RecursionError('too deep')

    monkeypatch.setattr('mine_local_root_session_episodes.extract_python_symbols', _raise)
    rows = _repo_index_from_paths(repo, [target])
    info = rows['src/broken.py']
    assert info['analysis_status'] == 'parse_failed'
    assert info['analysis_error_type'] == 'RecursionError'
    assert info['defined_symbols'] == []
    assert info['imported_symbols'] == []
    assert info['called_symbols'] == []

def test_mine_local_root_session_episodes_prefers_trace_verification_targets(tmp_path: Path) -> None:
    repo = tmp_path / 'repo_trace_verify'
    (repo / 'src').mkdir(parents=True)
    (repo / 'tests').mkdir(parents=True)
    (repo / 'src' / 'engine.py').write_text('def run_order(x):\n    return x\n', encoding='utf-8')
    (repo / 'tests' / 'test_engine.py').write_text('from src.engine import run_order\n\ndef test_run_order():\n    assert run_order(1) == 1\n', encoding='utf-8')

    seeds = tmp_path / 'resolved_trace_verify.jsonl'
    seeds.write_text(
        json.dumps(
            {
                'seed_id': 's_trace_verify',
                'seed_type': 'session_episode_local_root',
                'source_root_label': 'codex_sessions',
                'session_id_hint': 'rollout-trace-verify',
                'repo_hint': 'repo_trace_verify',
                'local_repo_root': str(repo),
                'goal': 'Modify repository files to preserve behavior under execution-backed maintenance.\nChanged files: src/engine.py\nVerification targets: tests/test_engine.py\nExecution route: PATCH_PLUS_EXEC',
                'changes': [{'path': str(repo / 'src' / 'engine.py')}],
                'metadata': {
                    'route': 'PATCH_PLUS_EXEC',
                    'trace_verification_targets': ['tests/test_engine.py'],
                },
            },
            sort_keys=True,
        )
        + '\n',
        encoding='utf-8',
    )

    episodes, summary = mine_local_root_session_episodes(
        resolved_local_seeds_path=seeds,
        root_file_limit=20,
        neighbor_dir_file_limit=20,
        max_total_candidates=40,
    )

    assert summary['episode_count'] == 1
    assert summary['route_counts']['PASS_TRACE_VERIFICATION_TARGETS'] == 1
    episode = episodes[0]
    assert episode['selected_tests'] == ['tests/test_engine.py']
    assert episode['test_selection_route'] == 'PASS_TRACE_VERIFICATION_TARGETS'
