from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.capture_preflight_gate_audit import audit_preflight_rows
from scripts.model_output_capture_preflight_design_builder import build_preflight_rows


def packet() -> dict:
    return {
        "packet_id": "synthetic_packet::a",
        "split": "eval",
        "bounded_argument_type": "ARG_LITERAL",
        "anti_cheat": {"contains_model_output": False},
    }


def test_gate_passes_closed_preflight_rows() -> None:
    rows = build_preflight_rows([packet()])
    card = audit_preflight_rows(rows)
    assert card["passed"] is True
    assert card["static_gate_pass_rows"] == 1
    assert card["authority_open_rows"] == 0
    assert card["model_execution_ready_rows"] == 0


def test_gate_catches_probe_ready_opening() -> None:
    rows = build_preflight_rows([packet()])
    rows[0]["clean_state"]["probe_ready"] = True
    card = audit_preflight_rows(rows)
    assert card["passed"] is False
    assert card["probe_ready_rows"] == 1
