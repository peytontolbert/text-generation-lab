from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from audit_long_context_candidate_packs import audit_candidate_packs  # noqa: E402


def test_audit_candidate_packs_reports_chunk_overlap_and_zero_candidate_overlap(tmp_path: Path) -> None:
    packs_path = tmp_path / 'candidate_packs.jsonl'
    packs_path.write_text(
        '\n'.join(
            [
                '{"pack_id":"p1","ordered_chunk_ids":["a","b","c"],"candidate_ids":["c1","c2"],"pack_token_count":100,"chunk_count":3,"candidate_count":2}',
                '{"pack_id":"p2","ordered_chunk_ids":["b","c","d"],"candidate_ids":["c3"],"pack_token_count":120,"chunk_count":3,"candidate_count":1}',
                '{"pack_id":"p3","ordered_chunk_ids":["x","y"],"candidate_ids":["c4"],"pack_token_count":80,"chunk_count":2,"candidate_count":1}',
            ]
        ) + '\n',
        encoding='utf-8',
    )
    pair_rows, summary = audit_candidate_packs(
        packs_path=packs_path,
        chunk_jaccard_warn_threshold=0.25,
        candidate_overlap_warn_threshold=1,
    )
    assert summary['pack_count'] == 3
    assert summary['pair_count'] == 3
    assert summary['flagged_pair_count'] == 1
    assert round(summary['chunk_jaccard_stats']['max'], 6) == 0.5
    assert summary['candidate_intersection_stats']['max'] == 0
    assert pair_rows[0]['left_pack_id'] == 'p1'
    assert pair_rows[0]['right_pack_id'] == 'p2'
    assert pair_rows[0]['flagged'] is True
