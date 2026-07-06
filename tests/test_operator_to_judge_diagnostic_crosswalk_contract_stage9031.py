from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage9031_operator_to_judge_diagnostic_crosswalk_contract import (  # noqa: E402
    AUTHORITY_CLOSED,
    CATEGORY_TO_DIAGNOSTIC_FIELDS,
    build_contract,
    validate_contract,
)


def registry() -> dict[str, object]:
    return {"metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9031_crosswalk_covers_all_recovered_operator_categories() -> None:
    card = build_contract(registry())
    assert card["metrics"]["inventory_categories"] == 15
    assert card["metrics"]["crosswalk_categories"] == 15
    assert card["missing_inventory_categories"] == []
    assert card["unknown_crosswalk_categories"] == []
    assert set(CATEGORY_TO_DIAGNOSTIC_FIELDS) == set(card["category_to_diagnostic_fields"])


def test_stage9031_crosswalk_references_known_judge_diagnostic_fields() -> None:
    card = build_contract(registry())
    assert card["metrics"]["unknown_diagnostic_fields"] == 0
    assert "quality_score" in {field for fields in card["category_to_diagnostic_fields"].values() for field in fields}
    assert "confidence" in {field for fields in card["category_to_diagnostic_fields"].values() for field in fields}
    assert "gate_status" in {field for fields in card["category_to_diagnostic_fields"].values() for field in fields}
    assert validate_contract(card) == []


def test_stage9031_requires_operator_fields_for_future_rows() -> None:
    card = build_contract(registry())
    assert "operator_id" in card["required_row_fields"]
    assert "operator_category" in card["required_row_fields"]
    assert "diagnostic_fields_required" in card["required_row_fields"]
    assert "loss_mask_candidates" in card["required_row_fields"]


def test_stage9031_keeps_execution_and_training_closed() -> None:
    card = build_contract(registry())
    assert card["metrics"]["crosswalk_contract_only"] is True
    assert card["metrics"]["crosswalked_rows_materialized_now"] is False
    assert card["metrics"]["judge_executed_now"] is False
    assert card["metrics"]["manifest_compile_authorized_now"] is False
    assert card["metrics"]["training_authorized"] is False
    assert card["metrics"]["decoder_ce_authorized"] is False
    assert card["metrics"]["denoise_ce_authorized"] is False
    assert all(value is False for value in card["authority"].values())


def test_stage9031_validation_rejects_open_authority_or_materialization() -> None:
    opened = build_contract(registry())
    opened["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_contract(opened)
    unsafe = build_contract(registry())
    unsafe["metrics"]["crosswalked_rows_materialized_now"] = True
    assert "crosswalked_rows_materialized_now" in validate_contract(unsafe)
