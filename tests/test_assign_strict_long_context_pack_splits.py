from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from assign_strict_long_context_pack_splits import assign_strict_long_context_pack_splits  # noqa: E402


def _rows_for_pack(pack_id: str, retrieval_count: int, token_count: int, *, source_id: str = 'repo_a', source_type: str = 'local_repo') -> list[dict]:
    context_rows = [
        {
            'chunk_id': f'{pack_id}_chunk_0',
            'source_id': source_id,
            'source_type': source_type,
            'role': 'verification_constraint',
        }
    ]
    rows = [
        {
            'mixture_row_id': f'full_context_rows::full::{pack_id}',
            'mixture_surface': 'full_context_rows',
            'pack_id': pack_id,
            'context_rows': context_rows,
            'metadata': json.dumps({'pack_token_count': token_count}, sort_keys=True),
        },
        {
            'mixture_row_id': f'memory_rows::memory::{pack_id}',
            'mixture_surface': 'memory_rows',
            'pack_id': pack_id,
            'metadata': json.dumps({'pack_token_count': token_count}, sort_keys=True),
        },
    ]
    for i in range(retrieval_count):
        rows.append(
            {
                'mixture_row_id': f'retrieval_rows::retrieval::{pack_id}::{i}',
                'mixture_surface': 'retrieval_rows',
                'pack_id': pack_id,
                'metadata': json.dumps({'pack_token_count': token_count}, sort_keys=True),
            }
        )
    return rows


def test_assign_strict_long_context_pack_splits_creates_heldout_packs(tmp_path: Path) -> None:
    rows = []
    for idx, retrieval_count in enumerate([10, 9, 8, 7, 6, 5, 4, 3, 2, 1]):
        rows.extend(_rows_for_pack(f'pack_{idx}', retrieval_count, token_count=1000 - idx, source_id=f'repo_{idx}'))
    rows_path = tmp_path / 'rows.jsonl'
    rows_path.write_text('\n'.join(json.dumps(row, sort_keys=True) for row in rows) + '\n', encoding='utf-8')

    result = assign_strict_long_context_pack_splits(
        rows_path=rows_path,
        output_dir=tmp_path / 'out',
    )
    split_rows = [json.loads(line) for line in Path(result['rows_path']).read_text(encoding='utf-8').splitlines() if line.strip()]
    split_by_pack = {}
    for row in split_rows:
        split_by_pack.setdefault(row['pack_id'], row['effective_split'])
        assert split_by_pack[row['pack_id']] == row['effective_split']
        assert row['pack_group_key']
    assert set(split_by_pack.values()) == {'train', 'eval', 'strict_eval'}
    assert result['split_cards']['eval']['packs'] >= 1
    assert result['split_cards']['strict_eval']['packs'] >= 1
    card = json.loads(Path(result['card_path']).read_text(encoding='utf-8'))
    assert all(pack['source_signature'] for pack in card['pack_stats'])


def test_assign_decodes_exported_context_rows_and_rejects_blank_identity(tmp_path: Path) -> None:
    rows = []
    for idx in range(5):
        pack_rows = _rows_for_pack(f"serialized_{idx}", 3, 1000 - idx, source_id=f"repo_{idx}")
        pack_rows[0]["context_rows"] = json.dumps(pack_rows[0]["context_rows"], sort_keys=True)
        rows.extend(pack_rows)
    rows_path = tmp_path / "serialized.jsonl"
    rows_path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
    result = assign_strict_long_context_pack_splits(
        rows_path=rows_path, output_dir=tmp_path / "serialized_out", eval_ratio=0.2, strict_ratio=0.2
    )
    card = json.loads(Path(result["card_path"]).read_text(encoding="utf-8"))
    assert all(pack["source_signature"] for pack in card["pack_stats"])

    rows[0]["context_rows"] = json.dumps([{"source_type": "repo"}], sort_keys=True)
    rows_path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
    import pytest
    with pytest.raises(ValueError, match="missing_source_identity"):
        assign_strict_long_context_pack_splits(
            rows_path=rows_path, output_dir=tmp_path / "bad_out", eval_ratio=0.2, strict_ratio=0.2
        )


def test_assign_strict_long_context_pack_splits_preserves_row_count(tmp_path: Path) -> None:
    rows = []
    for idx, retrieval_count in enumerate([6, 6, 6, 6, 6]):
        rows.extend(_rows_for_pack(f'pack_{idx}', retrieval_count, token_count=1000 - idx, source_id=f'repo_{idx}'))
    rows_path = tmp_path / 'rows.jsonl'
    rows_path.write_text('\n'.join(json.dumps(row, sort_keys=True) for row in rows) + '\n', encoding='utf-8')

    result = assign_strict_long_context_pack_splits(
        rows_path=rows_path,
        output_dir=tmp_path / 'out',
        eval_ratio=0.2,
        strict_ratio=0.2,
    )
    split_rows = [json.loads(line) for line in Path(result['rows_path']).read_text(encoding='utf-8').splitlines() if line.strip()]
    assert len(split_rows) == len(rows)
    assert sum(card['rows'] for card in result['split_cards'].values()) == len(rows)


def test_assign_keeps_shared_source_identity_together_across_different_families(tmp_path: Path) -> None:
    rows = []
    for pack_id, source_id in (("alpha", "shared"), ("beta", "shared"), ("gamma", "g"), ("delta", "d"), ("epsilon", "e")):
        rows.extend(_rows_for_pack(pack_id, 3, 1000, source_id=source_id))
    rows_path = tmp_path / "shared_source.jsonl"
    rows_path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
    result = assign_strict_long_context_pack_splits(
        rows_path=rows_path, output_dir=tmp_path / "out", eval_ratio=0.2, strict_ratio=0.2
    )
    split_rows = [json.loads(line) for line in Path(result["rows_path"]).read_text(encoding="utf-8").splitlines() if line.strip()]
    split_by_pack = {row["pack_id"]: row["effective_split"] for row in split_rows}
    group_by_pack = {row["pack_id"]: row["pack_group_key"] for row in split_rows}
    assert split_by_pack["alpha"] == split_by_pack["beta"]
    assert group_by_pack["alpha"] == group_by_pack["beta"]


def test_assign_strict_long_context_pack_splits_keeps_same_family_together(tmp_path: Path) -> None:
    rows = []
    rows.extend(_rows_for_pack('lcp_pack_1_5000000_session_family_alpha_deadbeef01', 5, 5000, source_id='repo_shared'))
    rows.extend(_rows_for_pack('lcp_pack_1_5500000_session_family_alpha_deadbeef02', 4, 4900, source_id='repo_shared'))
    rows.extend(_rows_for_pack('lcp_pack_1_5000000_session_family_beta_deadbeef03', 4, 4800, source_id='repo_beta'))
    rows.extend(_rows_for_pack('lcp_pack_1_5000000_session_family_gamma_deadbeef04', 4, 4700, source_id='repo_gamma'))
    rows_path = tmp_path / 'rows.jsonl'
    rows_path.write_text('\n'.join(json.dumps(row, sort_keys=True) for row in rows) + '\n', encoding='utf-8')

    result = assign_strict_long_context_pack_splits(
        rows_path=rows_path,
        output_dir=tmp_path / 'out',
        eval_ratio=0.25,
        strict_ratio=0.25,
    )
    split_rows = [json.loads(line) for line in Path(result['rows_path']).read_text(encoding='utf-8').splitlines() if line.strip()]
    split_by_pack = {}
    group_by_pack = {}
    for row in split_rows:
        split_by_pack.setdefault(row['pack_id'], row['effective_split'])
        group_by_pack.setdefault(row['pack_id'], row['pack_group_key'])
    assert split_by_pack['lcp_pack_1_5000000_session_family_alpha_deadbeef01'] == split_by_pack['lcp_pack_1_5500000_session_family_alpha_deadbeef02']
    assert group_by_pack['lcp_pack_1_5000000_session_family_alpha_deadbeef01'] == group_by_pack['lcp_pack_1_5500000_session_family_alpha_deadbeef02']
