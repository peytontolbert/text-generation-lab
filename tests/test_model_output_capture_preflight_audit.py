from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.model_output_capture_preflight_audit import audit_rows
from scripts.model_output_capture_preflight_builder import build_preflight_rows
from scripts.model_output_packet_telemetry_contract_builder import build_contract_rows
from scripts.model_output_packet_validator_dry_run import build_placeholder_packets


def design_row() -> dict:
    return {
        "row_id": "design_eval",
        "source_stage": "test_stage",
        "split": "eval",
        "corrupted_state": {"language": "python", "file_extension": "py", "argument_signal": "literal", "bounded_argument_type": "ARG_LITERAL"},
        "clean_state": {"requires_future_model_output_packet": True},
    }


def rows() -> list[dict]:
    return build_preflight_rows(build_placeholder_packets(build_contract_rows([design_row()])))


def test_capture_preflight_audit_passes_closed_design() -> None:
    card = audit_rows(rows())
    assert card["passed"] is True
    assert card["audit_ready_rows"] == 1
    assert card["authority_open_rows"] == 0
    assert card["execution_allowed_rows"] == 0


def test_capture_preflight_audit_catches_execution_authority() -> None:
    sample = rows()
    sample[0]["capture_contract"]["model_execution_allowed"] = True
    card = audit_rows(sample)
    assert card["passed"] is False
    assert card["execution_allowed_rows"] == 1
