from __future__ import annotations

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
    assert buckets['memory_rows'][0]['task_type'] == 'state_summary_compression'
