from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from partition_long_context_candidate_packs import partition_candidate_packs  # noqa: E402


def test_partition_candidate_packs_spreads_overlapping_packs_across_splits(tmp_path: Path) -> None:
    packs_path = tmp_path / 'candidate_packs.jsonl'
    packs_path.write_text(
        '\n'.join(
            [
                '{"pack_id":"p1","ordered_chunk_ids":["a","b","c","d"],"candidate_ids":["c1"],"pack_token_count":100,"chunk_count":4,"candidate_count":1}',
                '{"pack_id":"p2","ordered_chunk_ids":["a","b","x"],"candidate_ids":["c2"],"pack_token_count":90,"chunk_count":3,"candidate_count":1}',
                '{"pack_id":"p3","ordered_chunk_ids":["y","z"],"candidate_ids":["c3"],"pack_token_count":80,"chunk_count":2,"candidate_count":1}',
            ]
        ) + '\n',
        encoding='utf-8',
    )
    assignments, summary = partition_candidate_packs(
        packs_path=packs_path,
        split_names=('train', 'val'),
    )
    split_by_pack = {row['pack_id']: row['split'] for row in assignments}
    assert split_by_pack['p1'] != split_by_pack['p2']
    assert summary['pack_count'] == 3
    assert len(summary['split_rows']) == 2
    assert summary['cross_split_chunk_jaccard_stats']['max'] <= 0.5
