from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.model_output_packet_telemetry_contract_builder import (
    FORBIDDEN_PACKET_FIELDS,
    REQUIRED_CHECKS,
    REQUIRED_PACKET_FIELDS,
    REQUIRED_TELEMETRY,
    build_card,
    build_contract_rows,
)


def design_row(split: str = "eval") -> dict:
    return {
        "row_id": f"design_{split}",
        "source_stage": "test_stage",
        "split": split,
        "corrupted_state": {
            "language": "python",
            "file_extension": "py",
            "argument_signal": "literal",
            "bounded_argument_type": "ARG_LITERAL",
        },
        "clean_state": {
            "requires_future_model_output_packet": True,
        },
    }


def test_contract_rows_require_packet_checks_and_telemetry() -> None:
    rows = build_contract_rows([design_row("eval"), design_row("strict")])
    assert len(rows) == 2
    for row in rows:
        clean = row["clean_state"]
        assert set(REQUIRED_PACKET_FIELDS).issubset(clean["required_packet_fields"])
        assert set(REQUIRED_CHECKS).issubset(clean["required_checks"])
        assert set(REQUIRED_TELEMETRY).issubset(clean["required_telemetry"])
        assert set(FORBIDDEN_PACKET_FIELDS).issubset(clean["forbidden_packet_fields"])
        assert clean["probe_ready"] is False
        assert clean["decoder_ce_eligible_now"] is False


def test_contract_card_remains_closed_and_complete() -> None:
    rows = build_contract_rows([design_row("eval"), design_row("strict")])
    card = build_card(rows)
    assert card["rows"] == 2
    assert card["authority_rows"] == 0
    assert card["loss_rows"] == 0
    assert card["probe_ready_rows"] == 0
    assert card["decoder_ce_eligible_now_rows"] == 0
    assert card["missing_required_field_rows"] == 0
    assert card["missing_required_check_rows"] == 0
    assert card["missing_required_telemetry_rows"] == 0
    assert card["forbidden_visible_rows"] == 0
