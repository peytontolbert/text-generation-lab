from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage9034_operator_detail_seed_gap_matrix import (  # noqa: E402
    AUTHORITY_CLOSED,
    TRAINING_READY_DETAIL_FIELDS,
    build_matrix,
    validate_matrix,
)


def registry() -> dict[str, object]:
    return {"metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9034_records_training_ready_detail_field_gaps() -> None:
    card = build_matrix(registry())
    assert card["metrics"]["operator_seed_rows"] == 108
    assert card["metrics"]["training_ready_detail_fields"] == len(TRAINING_READY_DETAIL_FIELDS)
    assert set(TRAINING_READY_DETAIL_FIELDS) == {"inputs", "outputs", "confidence_score", "failure_modes", "training_label_source", "metric"}
    assert card["metrics"]["rows_missing_training_ready_fields"] == 108
    assert card["metrics"]["field_missing_total"] == 108 * len(TRAINING_READY_DETAIL_FIELDS)


def test_stage9034_gap_rows_block_operator_specific_training() -> None:
    card = build_matrix(registry())
    assert card["gap_rows_sample"]
    for row in card["gap_rows_sample"]:
        assert row["missing_training_ready_fields"] == TRAINING_READY_DETAIL_FIELDS
        assert row["mining_blocked"] is True
        assert row["operator_specific_training_blocked"] is True
    assert validate_matrix(card) == []


def test_stage9034_records_future_recovery_actions() -> None:
    card = build_matrix(registry())
    assert "recover_inputs_outputs_metadata" in card["future_recovery_actions"]
    assert "recover_confidence_score_semantics" in card["future_recovery_actions"]
    assert "recover_failure_modes" in card["future_recovery_actions"]
    assert "recover_training_label_source" in card["future_recovery_actions"]
    assert "recover_metric_definition" in card["future_recovery_actions"]


def test_stage9034_keeps_detail_recovery_execution_and_training_closed() -> None:
    card = build_matrix(registry())
    assert card["metrics"]["gap_matrix_only"] is True
    assert card["metrics"]["operator_details_recovered_now"] is False
    assert card["metrics"]["raw_session_text_read_now"] is False
    assert card["metrics"]["training_rows_materialized_now"] is False
    assert card["metrics"]["training_authorized"] is False
    assert card["metrics"]["decoder_ce_authorized"] is False
    assert card["metrics"]["denoise_ce_authorized"] is False
    assert all(value is False for value in card["authority"].values())


def test_stage9034_validation_rejects_unblocked_rows_or_open_authority() -> None:
    opened = build_matrix(registry())
    opened["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_matrix(opened)
    unsafe = build_matrix(registry())
    unsafe["metrics"]["rows_missing_training_ready_fields"] = 107
    assert "not_all_seed_rows_blocked" in validate_matrix(unsafe)
