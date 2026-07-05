from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.model_output_capture_preflight_design_builder import BLOCKED_OPERATIONS, build_card, build_preflight_rows


def packet() -> dict:
    return {
        "packet_id": "synthetic_packet::a",
        "split": "eval",
        "bounded_argument_type": "ARG_LITERAL",
        "anti_cheat": {"contains_model_output": False},
    }


def test_preflight_rows_keep_execution_closed() -> None:
    rows = build_preflight_rows([packet()])
    assert len(rows) == 1
    clean = rows[0]["clean_state"]
    assert clean["ready_for_model_execution"] is False
    assert clean["ready_for_decoder_ce"] is False
    assert clean["probe_ready"] is False
    assert set(BLOCKED_OPERATIONS).issubset(clean["blocked_operations"])
    assert not any(rows[0]["authority"].values())


def test_preflight_card_catches_model_output_absence_and_completeness() -> None:
    rows = build_preflight_rows([packet()])
    card = build_card(rows)
    assert card["rows"] == 1
    assert card["authority_rows"] == 0
    assert card["loss_rows"] == 0
    assert card["model_output_rows"] == 0
    assert card["ready_for_model_execution_rows"] == 0
    assert card["missing_preflight_field_rows"] == 0
    assert card["missing_blocked_operation_rows"] == 0
