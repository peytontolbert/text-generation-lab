from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.model_output_packet_telemetry_contract_builder import build_contract_rows
from scripts.model_output_packet_validator_dry_run import build_placeholder_packets, validate_packets


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


def test_placeholder_packet_validates_without_model_output() -> None:
    contract_rows = build_contract_rows([design_row()])
    packets = build_placeholder_packets(contract_rows)
    audit = validate_packets(packets)
    assert audit["passed"] is True
    assert audit["valid_packet_rows"] == 1
    assert audit["model_output_rows"] == 0
    assert packets[0]["generated_text_ref"] == "synthetic://placeholder/no_model_output"


def test_validator_catches_forbidden_target_text_field() -> None:
    contract_rows = build_contract_rows([design_row()])
    packets = build_placeholder_packets(contract_rows)
    packets[0]["decoder_target_text"] = "forbidden"
    audit = validate_packets(packets)
    assert audit["passed"] is False
    assert audit["forbidden_field_rows"] == 1
