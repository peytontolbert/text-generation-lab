from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from shortcut_baseline_audit import audit_shortcuts
from structured_dataset_junk_ranker import rank_row, rank_rows


def test_shortcut_audit_blocks_perfect_marker() -> None:
    rows = [
        {'row_id': 'a', 'marker': 'x', 'target': 'A'},
        {'row_id': 'b', 'marker': 'x', 'target': 'A'},
        {'row_id': 'c', 'marker': 'y', 'target': 'B'},
        {'row_id': 'd', 'marker': 'y', 'target': 'B'},
    ]
    card = audit_shortcuts(rows, target_field='target', feature_fields=['marker'], ceiling=0.8)
    assert card['strongest_single_feature_exact'] == 1.0
    assert card['training_blocked_by_shortcut_dominance'] is True


def test_shortcut_audit_allows_nonperfect_marker() -> None:
    rows = [
        {'row_id': 'a', 'marker': 'x', 'target': 'A'},
        {'row_id': 'b', 'marker': 'x', 'target': 'B'},
        {'row_id': 'c', 'marker': 'y', 'target': 'A'},
        {'row_id': 'd', 'marker': 'y', 'target': 'B'},
    ]
    card = audit_shortcuts(rows, target_field='target', feature_fields=['marker'], ceiling=0.8)
    assert card['strongest_single_feature_exact'] == 0.5
    assert card['training_blocked_by_shortcut_dominance'] is False


def test_junk_ranker_holds_long_html() -> None:
    row = {'row_id': 'r', 'decoder_text': '<html>' + ('x' * 12000), 'decoder_budget_ok': False, 'decode_allowed': False}
    ranked = rank_row(row, max_decoder_tokens=768)
    assert ranked['risk_bucket'] == 'HOLD_LONG_OUTPUT'
    assert 'target_over_decoder_budget' in ranked['reasons']
    assert 'html_doc_fragment' in ranked['reasons']


def test_junk_ranker_routes_internal_tokens_to_denoise() -> None:
    row = {'row_id': 'r', 'decoder_text': '<MTC> POLICY_CONTINUE answer', 'decoder_budget_ok': True, 'decode_allowed': True}
    ranked = rank_row(row)
    assert ranked['risk_bucket'] == 'USE_FOR_DENOISE_REPAIR'
    assert 'raw_internal_token_in_decoder' in ranked['reasons']


def test_junk_ranker_catches_missing_evidence_decode() -> None:
    row = {'row_id': 'r', 'evidence_state': 'missing', 'decode_allowed': True, 'decoder_budget_ok': True, 'decoder_text': 'safe bounded answer'}
    ranked = rank_row(row)
    assert 'missing_evidence_but_decode_allowed' in ranked['reasons']


def test_rank_rows_counts_routes() -> None:
    card = rank_rows([
        {'row_id': 'a', 'decoder_budget_ok': True, 'decode_allowed': True, 'decoder_text': 'bounded answer'},
        {'row_id': 'b', 'decoder_text': '<MTC> leak'},
    ])
    assert card['rows'] == 2
    assert card['route_counts']['KEEP_BOUNDED_DECODER'] == 1
    assert card['route_counts']['USE_FOR_DENOISE_REPAIR'] == 1
