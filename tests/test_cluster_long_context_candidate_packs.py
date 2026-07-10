from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from cluster_long_context_candidate_packs import cluster_candidate_packs  # noqa: E402


def test_cluster_candidate_packs_groups_high_overlap_pairs(tmp_path: Path) -> None:
    packs_path = tmp_path / 'candidate_packs.jsonl'
    packs_path.write_text(
        '\n'.join(
            [
                '{"pack_id":"p1","ordered_chunk_ids":["a","b","c","d"],"candidate_ids":["c1"],"pack_token_count":100}',
                '{"pack_id":"p2","ordered_chunk_ids":["a","b","c","x"],"candidate_ids":["c2"],"pack_token_count":90}',
                '{"pack_id":"p3","ordered_chunk_ids":["y","z"],"candidate_ids":["c3"],"pack_token_count":80}',
            ]
        ) + '\n',
        encoding='utf-8',
    )
    edge_rows, summary = cluster_candidate_packs(
        packs_path=packs_path,
        min_chunk_jaccard=0.5,
    )
    assert len(edge_rows) == 1
    assert summary['cluster_count'] == 2
    assert summary['largest_cluster_pack_count'] == 2
    assert summary['singleton_cluster_count'] == 1
