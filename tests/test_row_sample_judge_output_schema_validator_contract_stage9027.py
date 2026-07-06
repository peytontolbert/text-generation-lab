from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage9027_row_sample_judge_output_schema_validator_contract import (  # noqa: E402
    AUTHORITY_CLOSED,
    build_contract,
    validate_contract,
)


def registry() -> dict[str, object]:
    return {"metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9027_records_required_future_inputs_and_validator_checks() -> None:
    card = build_contract(registry())
    assert card["metrics"]["required_future_inputs"] == 5
    assert card["metrics"]["validator_checks"] >= 14
    assert "row_sample_dataset_judge_report.json" in card["required_future_inputs"]
    assert "judge_to_compiler_gate_status.json" in card["required_future_inputs"]
    assert "accepted_and_rejected_ids_disjoint" in card["validator_checks"]
    assert "counts_match_report" in card["validator_checks"]


def test_stage9027_links_taxonomy_and_gate_status_requirements() -> None:
    card = build_contract(registry())
    assert card["metrics"]["known_reject_reason_codes"] >= 10
    assert "target_leakage" in card["known_reject_reason_codes"]
    assert "rejected_rows_have_known_taxonomy_reason" in card["validator_checks"]
    assert "gate_status_has_all_recovered_keys" in card["validator_checks"]
    assert card["metrics"]["required_recovered_gate_references"] >= 1
    assert validate_contract(card) == []


def test_stage9027_forbids_raw_fields_and_execution() -> None:
    card = build_contract(registry())
    assert "raw_row_body" in card["forbidden_fields"]
    assert "raw_repository_source_body" in card["forbidden_fields"]
    assert "model_logits" in card["forbidden_fields"]
    assert "generated_patch" in card["forbidden_fields"]
    assert card["metrics"]["real_judge_outputs_validated_now"] is False
    assert card["metrics"]["judge_executed_now"] is False
    assert card["metrics"]["manifest_compile_authorized_now"] is False
    assert card["metrics"]["training_authorized"] is False
    assert all(value is False for value in card["authority"].values())


def test_stage9027_validation_rejects_missing_checks_or_open_authority() -> None:
    opened = build_contract(registry())
    opened["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_contract(opened)
    unsafe = build_contract(registry())
    unsafe["validator_checks"] = [check for check in unsafe["validator_checks"] if check != "forbidden_raw_fields_absent"]
    assert "missing_validator_check:forbidden_raw_fields_absent" in validate_contract(unsafe)
    unsafe = build_contract(registry())
    unsafe["metrics"]["real_judge_outputs_validated_now"] = True
    assert "real_judge_outputs_validated_now" in validate_contract(unsafe)
