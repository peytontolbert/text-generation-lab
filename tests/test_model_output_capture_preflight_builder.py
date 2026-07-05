from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.model_output_capture_preflight_builder import build_card, build_preflight_rows
from scripts.model_output_packet_telemetry_contract_builder import build_contract_rows
from scripts.model_output_packet_validator_dry_run import build_placeholder_packets


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


def test_preflight_design_keeps_capture_authority_closed() -> None:
    packets = build_placeholder_packets(build_contract_rows([design_row()]))
    rows = build_preflight_rows(packets)
    card = build_card(rows)
    assert card["passed"] is True
    assert card["preflight_design_ready_rows"] == 1
    assert card["authority_open_rows"] == 0
    assert card["loss_open_rows"] == 0
    assert card["model_output_rows"] == 0
    assert card["artifact_write_rows"] == 0
    assert rows[0]["capture_contract"]["model_execution_allowed"] is False


def test_preflight_design_catches_model_output_artifact_write() -> None:
    packets = build_placeholder_packets(build_contract_rows([design_row()]))
    rows = build_preflight_rows(packets)
    rows[0]["capture_contract"]["writes_model_output_artifact_now"] = True
    card = build_card(rows)
    assert card["passed"] is False
    assert card["artifact_write_rows"] == 1
