from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from structured_data_operation_curriculum import build_seed_rows, curriculum_card, operation_row, validate_operation_row


def test_seed_rows_cover_core_structures() -> None:
    rows = build_seed_rows()
    card = curriculum_card(rows)
    assert card["passed"] is True
    assert set(card["structure_counts"]) == {"table", "json", "graph", "ast", "log_trace", "workflow", "memory"}
    assert card["authority"]["training_authorized_next"] is False


def test_operator_must_match_structure_type() -> None:
    row = operation_row(
        row_id="bad",
        structure_type="json",
        state={"a": 1},
        schema={"a": "int"},
        addressing="json_pointer",
        task="bad op",
        operator="group_by",
        arguments={},
        validator="should_fail",
    )
    audit = validate_operation_row(row)
    assert audit["passed"] is False
    assert "operator_not_allowed:json:group_by" in audit["failures"]


def test_forbidden_losses_are_rejected() -> None:
    row = build_seed_rows()[0]
    row["loss_mask"]["decoder_ce"] = True
    row["loss_mask"]["denoise_ce"] = True
    row["loss_mask"]["runtime_reward"] = True
    audit = validate_operation_row(row)
    assert audit["passed"] is False
    assert "forbidden_loss_enabled:decoder_ce" in audit["failures"]
    assert "forbidden_loss_enabled:denoise_ce" in audit["failures"]
    assert "forbidden_loss_enabled:runtime_reward" in audit["failures"]


def test_authority_true_is_rejected() -> None:
    row = build_seed_rows()[0]
    row["authority"]["model_execution_authorized_next"] = True
    audit = validate_operation_row(row)
    assert audit["passed"] is False
    assert "authority_open" in audit["failures"]


def test_missing_schema_and_validator_are_rejected() -> None:
    row = build_seed_rows()[0]
    row["schema"] = None
    row["validator"] = ""
    audit = validate_operation_row(row)
    assert audit["passed"] is False
    assert "schema_not_object" in audit["failures"]
    assert "missing_validator" in audit["failures"]
