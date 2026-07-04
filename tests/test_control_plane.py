from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from authority_gate import AuthorityGateError, assert_authority_closed, authority_counts
from loss_mask_card import validate_loss_mask_row, summarize_rows
from stage_summary_schema import make_summary, require_valid_stage_summary


def test_make_summary_defaults_authority_closed() -> None:
    payload = make_summary(stage=1, stage_name='stage1_test', passed=True, next_best_step='next')
    require_valid_stage_summary(payload, require_closed=True)
    assert all(value is False for value in payload['authority'].values())


def test_authority_gate_rejects_forbidden_open_key() -> None:
    payload = make_summary(stage=2, stage_name='stage2_test', passed=False, next_best_step='none', authority={'runtime_authorized': True})
    with pytest.raises(AuthorityGateError):
        assert_authority_closed(payload)


def test_authority_counts() -> None:
    rows = [make_summary(stage=1, stage_name='a', passed=True, next_best_step=''), make_summary(stage=2, stage_name='b', passed=True, next_best_step='', authority={'model_execution_authorized_next': True})]
    counts = authority_counts(rows)
    assert counts['model_execution_authorized_next'] == 1
    assert counts['runtime_authorized'] == 0


def test_loss_mask_blocks_decoder_by_default() -> None:
    row = {'row_id': 'r1', 'loss_mask': {'decoder_ce': True}}
    errors = validate_loss_mask_row(row)
    assert 'decoder_ce enabled without authorization' in errors


def test_loss_mask_allows_structured_loss() -> None:
    row = {'row_id': 'r1', 'loss_mask': {'build_mode_ce': True}}
    assert validate_loss_mask_row(row) == []


def test_loss_mask_card_counts_failures() -> None:
    rows = [
        {'row_id': 'ok', 'loss_mask': {'build_mode_ce': True}},
        {'row_id': 'bad', 'loss_mask': {'runtime_reward': True}},
    ]
    card = summarize_rows(rows)
    assert card['rows'] == 2
    assert card['loss_counts']['build_mode_ce'] == 1
    assert card['failure_count'] == 1
