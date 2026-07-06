from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage9035_operator_detail_recovery_ticket_contract import (  # noqa: E402
    AUTHORITY_CLOSED,
    RECOVERY_FIELDS,
    build_contract,
    validate_contract,
)


def registry() -> dict[str, object]:
    return {"metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9035_recovery_ticket_covers_all_missing_fields() -> None:
    card = build_contract(registry())
    assert card["metrics"]["recovery_fields"] == 6
    assert set(RECOVERY_FIELDS) == {"inputs", "outputs", "confidence_score", "failure_modes", "training_label_source", "metric"}
    assert card["metrics"]["operator_rows_to_recover"] == 108
    assert card["ticket_template"]["recovery_fields"] == RECOVERY_FIELDS


def test_stage9035_records_safe_metadata_sources_and_forbidden_sources() -> None:
    card = build_contract(registry())
    assert "stage8703_low_level_training_concept_session_grep_artifacts" in card["allowed_metadata_sources"]
    assert "stage9033_operator_detail_seed_catalog" in card["allowed_metadata_sources"]
    assert "raw_codex_session_text" in card["forbidden_sources"]
    assert "raw_repository_source_body" in card["forbidden_sources"]
    assert "raw_row_body_text" in card["forbidden_sources"]
    assert validate_contract(card) == []


def test_stage9035_future_outputs_and_validation_requirements_are_recorded() -> None:
    card = build_contract(registry())
    assert "operator_detail_metadata_patch.jsonl" in card["future_output_artifacts"]
    assert "operator_detail_no_raw_payload_proof.json" in card["future_output_artifacts"]
    assert "all_108_operator_ids_preserved" in card["validation_requirements"]
    assert "no_raw_session_or_source_payload_fields" in card["validation_requirements"]
    assert "metric_is_named_and_bounded" in card["validation_requirements"]


def test_stage9035_keeps_recovery_execution_and_training_closed() -> None:
    card = build_contract(registry())
    assert card["metrics"]["ticket_contract_only"] is True
    assert card["metrics"]["operator_details_recovered_now"] is False
    assert card["metrics"]["operator_detail_patch_materialized_now"] is False
    assert card["metrics"]["raw_session_text_read_now"] is False
    assert card["metrics"]["training_authorized"] is False
    assert card["metrics"]["decoder_ce_authorized"] is False
    assert card["metrics"]["denoise_ce_authorized"] is False
    assert all(value is False for value in card["authority"].values())
    assert all(value is False for value in card["ticket_template"]["authority"].values())


def test_stage9035_validation_rejects_open_ticket_authority_or_materialization() -> None:
    opened = build_contract(registry())
    opened["ticket_template"]["authority"]["runtime_authorized"] = True
    assert "ticket_authority_open" in validate_contract(opened)
    unsafe = build_contract(registry())
    unsafe["metrics"]["operator_detail_patch_materialized_now"] = True
    assert "operator_detail_patch_materialized_now" in validate_contract(unsafe)
