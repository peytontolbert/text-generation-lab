from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.authority_ticket_schema_builder import build_authority_ticket_schema_rows
from scripts.authority_ticket_schema_gate_audit import audit_ticket_rows


def runner_row() -> dict:
    return {
        "row_id": "runner_a",
        "split": "eval",
        "runner_contract": {
            "loads_checkpoint_now": False,
            "runs_model_forward_now": False,
            "decodes_tokens_now": False,
            "writes_model_output_artifact_now": False,
            "computes_decoder_ce_now": False,
            "runs_runtime_now": False,
            "calls_gemma_now": False,
            "opens_scoring_now": False,
        },
    }


def test_ticket_gate_passes_closed_schema() -> None:
    rows = build_authority_ticket_schema_rows([runner_row()])
    audit = audit_ticket_rows(rows)
    assert audit["passed"] is True
    assert audit["ticket_gate_pass_rows"] == 1
    assert audit["allowed_operation_rows"] == 0


def test_ticket_gate_catches_missing_denial() -> None:
    rows = build_authority_ticket_schema_rows([runner_row()])
    rows[0]["example_closed_ticket"]["denied_operations"] = []
    audit = audit_ticket_rows(rows)
    assert audit["passed"] is False
    assert audit["missing_denial_rows"] == 1
