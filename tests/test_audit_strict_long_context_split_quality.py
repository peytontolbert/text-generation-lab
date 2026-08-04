from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from audit_strict_long_context_split_quality import audit_strict_long_context_split_quality  # noqa: E402


def test_audit_strict_long_context_split_quality_passes_for_dispersed_nonblank_pack(tmp_path: Path) -> None:
    context_rows = [
        {'chunk_id': 'c0', 'source_id': 'repo_a', 'source_type': 'repo', 'text': 'repo chunk'},
        {'chunk_id': 'c1', 'source_id': 'paper_a', 'source_type': 'paper', 'text': 'paper chunk'},
        {'chunk_id': 'c2', 'source_id': 'dataset_a', 'source_type': 'dataset', 'text': 'dataset chunk'},
        {'chunk_id': 'c3', 'source_id': 'repo_a', 'source_type': 'repo', 'text': 'repo later chunk'},
    ]
    rows = [
        {
            'mixture_surface': 'full_context_rows',
            'pack_id': 'pack_a',
            'split': 'eval',
            'context_rows': json.dumps(context_rows, sort_keys=True),
            'pack_source_signature': 'sig_pack_a',
            'target_text': json.dumps({'state_variable': 'alpha_state', 'final_state': {'alpha_state': True}}, sort_keys=True),
        },
        {
            'mixture_surface': 'memory_rows',
            'pack_id': 'pack_a',
            'split': 'eval',
            'target_text': json.dumps({'state_variables': ['alpha_state'], 'canonical_names': ['alpha_state']}, sort_keys=True),
        },
        {
            'mixture_surface': 'retrieval_rows',
            'pack_id': 'pack_a',
            'split': 'eval',
            'query_text': '[1] What is the final value of `alpha_state` after reconciling all evidence?',
            'positive_chunk_ids': json.dumps(['c0', 'c2'], sort_keys=True),
            'target_text': json.dumps({'state_variable': 'alpha_state', 'final_state': {'alpha_state': True}}, sort_keys=True),
        },
    ]
    manifest = tmp_path / 'manifest.jsonl'
    manifest.write_text('\n'.join(json.dumps(row, sort_keys=True) for row in rows) + '\n', encoding='utf-8')
    result = audit_strict_long_context_split_quality(manifest_path=manifest, output_path=tmp_path / 'audit.json')
    assert result['passed'] is True
    assert result['failures'] == []


def test_audit_rejects_cross_split_source_content_target_and_lineage_overlap(tmp_path: Path) -> None:
    rows = []
    for pack_id, split in (("pack_train", "train"), ("pack_eval", "eval")):
        context_rows = [
            {"chunk_id": f"{pack_id}_c0", "source_id": "shared_repo", "source_type": "repo", "text": "shared first"},
            {"chunk_id": f"{pack_id}_c1", "source_id": "shared_repo", "source_type": "paper", "text": "shared middle"},
            {"chunk_id": f"{pack_id}_c2", "source_id": "shared_repo", "source_type": "dataset", "text": "shared last"},
            {"chunk_id": f"{pack_id}_c3", "source_id": "shared_repo", "source_type": "repo", "text": "shared tail"},
        ]
        target = json.dumps({"state_variable": "alpha", "final_state": {"alpha": True}}, sort_keys=True)
        rows.extend([
            {"mixture_surface": "full_context_rows", "pack_id": pack_id, "split": split, "pack_source_signature": "shared_sig", "pack_group_key": "shared_group", "context_rows": json.dumps(context_rows, sort_keys=True), "target_text": target},
            {"mixture_surface": "memory_rows", "pack_id": pack_id, "split": split, "target_text": json.dumps({"state_variables": ["alpha"]}, sort_keys=True)},
            {"mixture_surface": "retrieval_rows", "pack_id": pack_id, "split": split, "query_text": "What is alpha?", "positive_chunk_ids": json.dumps([f"{pack_id}_c0", f"{pack_id}_c2"]), "target_text": target},
        ])
    manifest = tmp_path / "overlap.jsonl"
    manifest.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
    result = audit_strict_long_context_split_quality(manifest_path=manifest, output_path=tmp_path / "audit.json")
    assert result["passed"] is False
    assert {
        "cross_split_source_identity_overlap",
        "cross_split_exact_context_overlap",
        "cross_split_exact_target_overlap",
        "cross_split_group_lineage_overlap",
    }.issubset(result["failures"])


def test_audit_strict_long_context_split_quality_fails_for_blank_fallback_pack(tmp_path: Path) -> None:
    context_rows = [
        {'chunk_id': 'c0', 'source_type': 'repo', 'text': 'repo chunk'},
        {'chunk_id': 'c1', 'source_type': 'repo', 'text': 'repo chunk 2'},
        {'chunk_id': 'c2', 'source_type': 'repo', 'text': 'repo chunk 3'},
    ]
    rows = [
        {
            'mixture_surface': 'full_context_rows',
            'pack_id': 'pack_b',
            'split': 'strict_eval',
            'context_rows': json.dumps(context_rows, sort_keys=True),
            'pack_source_signature': 'sig_pack_b',
            'target_text': json.dumps({'state_variable': '', 'final_state': {}}, sort_keys=True),
        },
        {
            'mixture_surface': 'memory_rows',
            'pack_id': 'pack_b',
            'split': 'strict_eval',
            'target_text': json.dumps({'state_variables': [''], 'canonical_names': ['']}, sort_keys=True),
        },
        {
            'mixture_surface': 'retrieval_rows',
            'pack_id': 'pack_b',
            'split': 'strict_eval',
            'query_text': '[1] What is the final value of `` after reconciling all evidence?',
            'positive_chunk_ids': json.dumps(['c0', 'c1', 'c2'], sort_keys=True),
            'target_text': json.dumps({'state_variable': '', 'final_state': {}}, sort_keys=True),
        },
    ]
    manifest = tmp_path / 'manifest.jsonl'
    manifest.write_text('\n'.join(json.dumps(row, sort_keys=True) for row in rows) + '\n', encoding='utf-8')
    result = audit_strict_long_context_split_quality(manifest_path=manifest, output_path=tmp_path / 'audit.json')
    assert result['passed'] is False
    assert 'blank_full_target_packs_present' in result['failures']
    assert 'blank_memory_target_packs_present' in result['failures']
    assert 'blank_query_rate_too_high' in result['failures']
