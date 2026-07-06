from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage9032_operator_detail_reference_contract import (  # noqa: E402
    AUTHORITY_CLOSED,
    DETAIL_STATUSES,
    FORBIDDEN_DETAIL_PAYLOAD_FIELDS,
    OPERATOR_DETAIL_REF_FIELDS,
    build_contract,
    validate_contract,
)


def registry() -> dict[str, object]:
    return {"metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9032_records_opaque_operator_detail_ref_fields() -> None:
    card = build_contract(registry())
    assert len(OPERATOR_DETAIL_REF_FIELDS) >= 9
    assert "operator_detail_ref" in card["operator_detail_ref_fields"]
    assert "operator_schema_version" in card["operator_detail_ref_fields"]
    assert "detail_status" in card["operator_detail_ref_fields"]
    assert "detail_hash" in card["operator_detail_ref_fields"]
    assert "detail_required_before_operator_specific_training" in card["operator_detail_ref_fields"]


def test_stage9032_tracks_detail_status_lifecycle() -> None:
    card = build_contract(registry())
    assert "detail_missing_blocked" in DETAIL_STATUSES
    assert "detail_recovered_pending_audit" in DETAIL_STATUSES
    assert "detail_audited_metadata_only" in DETAIL_STATUSES
    assert "detail_training_ready_after_future_gate" in DETAIL_STATUSES
    assert card["metrics"]["detail_statuses"] == 4
    assert validate_contract(card) == []


def test_stage9032_forbids_detail_payloads() -> None:
    card = build_contract(registry())
    assert "raw_operator_body" in FORBIDDEN_DETAIL_PAYLOAD_FIELDS
    assert "raw_session_text" in FORBIDDEN_DETAIL_PAYLOAD_FIELDS
    assert "raw_training_target" in FORBIDDEN_DETAIL_PAYLOAD_FIELDS
    assert "generated_patch" in FORBIDDEN_DETAIL_PAYLOAD_FIELDS
    assert card["metrics"]["operator_details_materialized_now"] is False
    assert card["metrics"]["raw_session_text_read_now"] is False


def test_stage9032_keeps_execution_mining_and_training_closed() -> None:
    card = build_contract(registry())
    assert card["metrics"]["operator_detail_reference_contract_only"] is True
    assert card["metrics"]["judge_executed_now"] is False
    assert card["metrics"]["manifest_compile_authorized_now"] is False
    assert card["metrics"]["data_mining_authorized"] is False
    assert card["metrics"]["training_authorized"] is False
    assert card["metrics"]["decoder_ce_authorized"] is False
    assert card["metrics"]["denoise_ce_authorized"] is False
    assert all(value is False for value in card["authority"].values())


def test_stage9032_validation_rejects_open_authority_or_materialization() -> None:
    opened = build_contract(registry())
    opened["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_contract(opened)
    unsafe = build_contract(registry())
    unsafe["metrics"]["operator_details_materialized_now"] = True
    assert "operator_details_materialized_now" in validate_contract(unsafe)
