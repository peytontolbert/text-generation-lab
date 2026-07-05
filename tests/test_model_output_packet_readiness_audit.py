from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.model_output_packet_readiness_audit import audit_rows
from scripts.model_output_packet_telemetry_contract_builder import build_contract_rows


def design_row() -> dict:
    return {
        "row_id": "design_eval",
        "source_stage": "test_stage",
        "split": "eval",
        "corrupted_state": {
            "language": "python",
            "file_extension": "py",
            "argument_signal": "literal",
            "bounded_argument_type": "ARG_LITERAL",
        },
        "clean_state": {"requires_future_model_output_packet": True},
    }


def test_readiness_audit_passes_complete_closed_contract() -> None:
    rows = build_contract_rows([design_row()])
    card = audit_rows(rows)
    assert card["passed"] is True
    assert card["contract_ready_rows"] == 1
    assert card["authority_open_rows"] == 0
    assert card["loss_open_rows"] == 0


def test_readiness_audit_catches_open_authority() -> None:
    rows = build_contract_rows([design_row()])
    rows[0]["authority"]["model_execution_authorized_next"] = True
    card = audit_rows(rows)
    assert card["passed"] is False
    assert card["contract_ready_rows"] == 0
    assert card["authority_open_rows"] == 1
