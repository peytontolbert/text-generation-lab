from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.authority_ticket_schema_builder import GATED_OPERATIONS, build_authority_ticket_schema_rows, build_card


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


def test_authority_ticket_schema_denies_all_gated_operations() -> None:
    rows = build_authority_ticket_schema_rows([runner_row()])
    assert len(rows) == 1
    ticket = rows[0]["example_closed_ticket"]
    assert ticket["allowed_operations"] == []
    assert set(GATED_OPERATIONS).issubset(ticket["denied_operations"])
    assert not any(rows[0]["authority"].values())


def test_authority_ticket_card_rejects_allowed_operation() -> None:
    rows = build_authority_ticket_schema_rows([runner_row()])
    rows[0]["example_closed_ticket"]["allowed_operations"] = ["run_forward"]
    card = build_card(rows)
    assert card["passed"] is False
    assert card["allowed_operation_rows"] == 1
