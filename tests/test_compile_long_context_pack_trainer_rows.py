from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from compile_long_context_pack_trainer_rows import compile_long_context_pack_trainer_rows  # noqa: E402


def test_compile_long_context_pack_trainer_rows_emits_three_training_views(tmp_path: Path) -> None:
    trainer_rows = tmp_path / 'trainer_rows.jsonl'
    trainer_rows.write_text(
        '\n'.join(
            [
                '{"pack_id":"p1","effective_split":"train","trainer_policy_mode":"family_cluster_constrained_training","overlap_family_id":"cluster_0001","prompt_text":"PACK_QUERIES:\\n[1] What is the final value of `alpha_active` after reconciling all evidence?","context_rows":[{"chunk_id":"c1","chunk_ordinal":1,"source_type":"repo","path":"src/engine.py","text":"alpha_active is enabled"}],"target_rows":[{"query_index":1,"candidate_id":"cand1","canonical_name":"alpha_state","final_state":{"alpha_active":true},"state_variable":"alpha_active"}],"pack_token_count":100,"chunk_count":1,"candidate_count":1}'
            ]
        ) + '\n',
        encoding='utf-8',
    )
    buckets, summary = compile_long_context_pack_trainer_rows(
        trainer_rows_path=trainer_rows,
        max_positive_chunks=4,
    )
    assert summary['trainer_rows'] == 1
    assert summary['full_context_rows'] == 1
    assert summary['retrieval_rows'] == 1
    assert summary['memory_rows'] == 1
    assert buckets['full_context_rows'][0]['task_type'] == 'full_context_state_reconstruction'
    assert buckets['retrieval_rows'][0]['positive_chunk_ids'] == ['c1']
    assert buckets['retrieval_rows'][0]['hard_negative_chunk_ids'] == []
    assert buckets['retrieval_rows'][0]['join_type'] == 'single_source'
    assert buckets['memory_rows'][0]['task_type'] == 'state_summary_compression'


def test_compile_long_context_pack_trainer_rows_filters_audit_only_direct_by_manifest(tmp_path: Path) -> None:
    strict_rows = tmp_path / 'strict_rows.jsonl'
    strict_rows.write_text(
        json.dumps(
            {
                'pack_id': 'strict-pack',
                'effective_split': 'train',
                'trainer_policy_mode': 'family_cluster_constrained_training',
                'overlap_family_id': 'cluster_strict',
                'prompt_text': 'strict prompt',
                'context_rows': [
                    {'chunk_id': 'strict-c1', 'chunk_ordinal': 1, 'source_type': 'repo', 'path': 'src/strict.py', 'text': 'strict_state is true'}
                ],
                'target_rows': [
                    {'query_index': 1, 'candidate_id': 'cand-strict', 'canonical_name': 'strict_state', 'final_state': {'strict_state': True}, 'state_variable': 'strict_state'}
                ],
                'pack_token_count': 100,
                'chunk_count': 1,
                'candidate_count': 1,
            },
            sort_keys=True,
        ) + '\n',
        encoding='utf-8',
    )
    audit_rows = tmp_path / 'audit_rows.jsonl'
    audit_rows.write_text(
        json.dumps(
            {
                'pack_id': 'audit-pack',
                'effective_split': 'train',
                'trainer_policy_mode': 'family_cluster_constrained_training',
                'overlap_family_id': 'cluster_audit',
                'prompt_text': 'audit prompt',
                'context_rows': [
                    {'chunk_id': 'audit-c1', 'chunk_ordinal': 1, 'source_type': 'paper', 'path': 'papers/audit.txt', 'text': 'audit_state is true'}
                ],
                'target_rows': [
                    {'query_index': 1, 'candidate_id': 'cand-audit', 'canonical_name': 'audit_state', 'final_state': {'audit_state': True}, 'state_variable': 'audit_state'}
                ],
                'pack_token_count': 100,
                'chunk_count': 1,
                'candidate_count': 1,
            },
            sort_keys=True,
        ) + '\n',
        encoding='utf-8',
    )
    manifest = tmp_path / 'strict_manifest.json'
    manifest.write_text(
        json.dumps(
            {
                'selected_shards': [
                    {
                        'name': 'strict_shard',
                        'acceptance_mode': 'strict_builder',
                        'ready_for_training': True,
                        'artifacts': {'training_rows_jsonl': str(strict_rows)},
                    },
                    {
                        'name': 'audit_shard',
                        'acceptance_mode': 'audit_only_direct',
                        'ready_for_training': True,
                        'artifacts': {'training_rows_jsonl': str(audit_rows)},
                    },
                ]
            },
            sort_keys=True,
        ),
        encoding='utf-8',
    )

    buckets, summary = compile_long_context_pack_trainer_rows(
        strict_shard_manifest_path=manifest,
        max_positive_chunks=4,
    )
    assert summary['trainer_rows'] == 1
    assert summary['source_summary']['included_shards'] == ['strict_shard']
    assert summary['source_summary']['excluded_shards'] == [{'name': 'audit_shard', 'reason': 'audit_only_direct_excluded'}]
    assert [row['pack_id'] for row in buckets['full_context_rows']] == ['strict-pack']

    buckets_with_audit, summary_with_audit = compile_long_context_pack_trainer_rows(
        strict_shard_manifest_path=manifest,
        include_audit_only_direct=True,
        max_positive_chunks=4,
    )
    assert summary_with_audit['trainer_rows'] == 2
    assert summary_with_audit['source_summary']['included_shards'] == ['strict_shard', 'audit_shard']
    assert summary_with_audit['source_summary']['excluded_shards'] == []
    assert [row['pack_id'] for row in buckets_with_audit['full_context_rows']] == ['strict-pack', 'audit-pack']



def test_compile_long_context_pack_trainer_rows_derives_structured_targets_and_support_positives(tmp_path: Path) -> None:
    trainer_rows = tmp_path / 'trainer_rows.jsonl'
    trainer_rows.write_text(
        json.dumps(
            {
                'pack_id': 'p_structured',
                'effective_split': 'train',
                'trainer_policy_mode': 'family_cluster_constrained_training',
                'overlap_family_id': 'cluster_structured',
                'prompt_text': 'PACK_QUERIES:\n[1] Recreate the verified transition.',
                'context_rows': [
                    {
                        'chunk_id': 'c_repo',
                        'chunk_ordinal': 1,
                        'source_type': 'repo',
                        'path': 'src/engine.py',
                        'role': 'seed_change',
                        'text': 'The fix updates src/engine.py and preserves verification route PATCH_PLUS_EXEC.',
                    },
                    {
                        'chunk_id': 'c_test',
                        'chunk_ordinal': 2,
                        'source_type': 'repo',
                        'path': 'tests/test_engine.py',
                        'role': 'verification_constraint',
                        'text': 'tests/test_engine.py verifies the patched behavior.',
                    },
                    {
                        'chunk_id': 'c_repo_cross',
                        'chunk_ordinal': 3,
                        'source_type': 'repo',
                        'path': 'src/engine_config.py',
                        'role': 'repo_graph_neighbor',
                        'text': 'EngineRunner PATCH_PLUS_EXEC compatibility note for src/engine.py.',
                    },
                    {
                        'chunk_id': 'c_paper_neg',
                        'chunk_ordinal': 4,
                        'source_type': 'paper',
                        'path': 'papers/engine_runner_attention.txt',
                        'role': 'supporting_paper',
                        'text': 'EngineRunner and PATCH_PLUS_EXEC are discussed abstractly without the repository verification target.',
                    },
                ],
                'target_rows': [
                    {
                        'query_index': 1,
                        'example_id': 'ex1',
                        'program_id': 'agentkernel',
                        'query_text': 'Repository: agentkernel\nChanged files: src/engine.py\nVerification targets: tests/test_engine.py',
                        'seed_paths': ['src/engine.py'],
                        'selected_tests': ['tests/test_engine.py'],
                        'seed_symbols': ['EngineRunner'],
                        'execution_route': 'PATCH_PLUS_EXEC',
                        'final_answer': 'Expected outcome: verification_targets_hold_under_patch_plus_exec',
                        'final_state_json': json.dumps({
                            'execution_route': 'PATCH_PLUS_EXEC',
                            'expected_changed_files': ['src/engine.py'],
                            'verification_targets': ['tests/test_engine.py'],
                            'key_symbols': ['EngineRunner'],
                        }, sort_keys=True),
                    }
                ],
                'pack_token_count': 512,
                'chunk_count': 3,
                'candidate_count': 1,
            },
            sort_keys=True,
        ) + '\n',
        encoding='utf-8',
    )
    buckets, summary = compile_long_context_pack_trainer_rows(trainer_rows_path=trainer_rows, max_positive_chunks=2)
    full_row = buckets['full_context_rows'][0]
    retrieval_row = buckets['retrieval_rows'][0]
    memory_row = buckets['memory_rows'][0]
    assert 'expected_changed_files' in full_row['target_text']
    assert 'verification_targets' in full_row['target_text']
    assert retrieval_row['query_text'].startswith('Repository: agentkernel')
    assert 'Transition target: verification_targets' in retrieval_row['query_text']
    assert 'Execution route: PATCH_PLUS_EXEC' in retrieval_row['query_text']
    assert 'Changed files: src/engine.py' in retrieval_row['query_text']
    assert 'Verification targets: tests/test_engine.py' in retrieval_row['query_text']
    assert 'Key symbols: EngineRunner' in retrieval_row['query_text']
    assert retrieval_row['positive_chunk_ids'] == ['c_test', 'c_repo']
    assert retrieval_row['hard_negative_chunk_ids'] == ['c_paper_neg']
    assert retrieval_row['join_type'] == 'repo+test'
    assert retrieval_row['support_scores'][0]['chunk_id'] == 'c_test'
    assert 'path_hit' in retrieval_row['support_scores'][0]['support_reasons']
    assert retrieval_row['support_scores'][2]['chunk_id'] == 'c_paper_neg'
    assert retrieval_row['metadata']['canonical_name'] == 'agentkernel'
    assert 'expected_changed_files' in retrieval_row['target_text']
    assert 'verification_targets' in memory_row['target_text']
    assert 'agentkernel' in memory_row['target_text']
