from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage9040_operator_detail_metadata_patch_validator_contract import (  # noqa: E402
    AUTHORITY_CLOSED,
    PATCH_ROW_REQUIRED_FIELDS,
    VALIDATION_RULES,
    build_contract,
    validate_contract,
)


def registry() -> dict[str, object]:
    return {"metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9040_patch_validator_requires_training_ready_fields() -> None:
    card = build_contract(registry())
    for field in ["operator_id", "inputs", "outputs", "confidence_score", "failure_modes", "training_label_source", "metric", "detail_hash"]:
        assert field in PATCH_ROW_REQUIRED_FIELDS
        assert field in card["patch_row_required_fields"]
    assert card["metrics"]["patch_row_required_fields"] >= 11


def test_stage9040_validation_rules_block_raw_or_partial_metadata() -> None:
    card = build_contract(registry())
    assert "all_108_rows_present_before_training_ready" in VALIDATION_RULES
    assert "forbidden_raw_payload_fields_absent" in VALIDATION_RULES
    assert "detail_hash_present" in VALIDATION_RULES
    assert "metric_is_named_and_bounded" in VALIDATION_RULES
    assert "failure_modes_are_reason_codes_not_trace_text" in VALIDATION_RULES
    assert validate_contract(card) == []


def test_stage9040_forbids_raw_payload_fields() -> None:
    card = build_contract(registry())
    assert "raw_codex_session_text" in card["forbidden_patch_fields"]
    assert "raw_repository_source_body" in card["forbidden_patch_fields"]
    assert "raw_row_body_text" in card["forbidden_patch_fields"]
    assert "model_logits" in card["forbidden_patch_fields"]


def test_stage9040_future_validator_outputs_are_recorded() -> None:
    card = build_contract(registry())
    assert "operator_detail_metadata_patch_validation_card.json" in card["future_validator_outputs"]
    assert "operator_detail_field_coverage_card.json" in card["future_validator_outputs"]
    assert "operator_detail_hash_audit.json" in card["future_validator_outputs"]
    assert "operator_detail_no_raw_payload_proof_audit.json" in card["future_validator_outputs"]


def test_stage9040_keeps_validation_recovery_and_training_closed() -> None:
    card = build_contract(registry())
    assert card["metrics"]["validator_contract_only"] is True
    assert card["metrics"]["real_operator_detail_patch_validated_now"] is False
    assert card["metrics"]["operator_detail_patch_materialized_now"] is False
    assert card["metrics"]["operator_details_recovered_now"] is False
    assert card["metrics"]["raw_session_text_read_now"] is False
    assert card["metrics"]["training_authorized"] is False
    assert card["metrics"]["decoder_ce_authorized"] is False
    assert card["metrics"]["denoise_ce_authorized"] is False
    assert all(value is False for value in card["authority"].values())


def test_stage9040_validation_rejects_open_authority_or_materialization() -> None:
    opened = build_contract(registry())
    opened["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_contract(opened)
    unsafe = build_contract(registry())
    unsafe["metrics"]["real_operator_detail_patch_validated_now"] = True
    assert "real_operator_detail_patch_validated_now" in validate_contract(unsafe)
