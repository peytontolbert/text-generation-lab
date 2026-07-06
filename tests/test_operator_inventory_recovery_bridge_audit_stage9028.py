from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage9028_operator_inventory_recovery_bridge_audit import (  # noqa: E402
    AUTHORITY_CLOSED,
    REQUIRED_GAP_OPERATORS,
    REQUIRED_RECOVERED_CATEGORIES,
    build_audit,
    validate_audit,
)


def registry() -> dict[str, object]:
    return {"metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9028_records_stage8718_as_stage1239_replacement() -> None:
    card = build_audit(registry())
    assert card["metrics"]["stage1239_present"] is False
    assert card["metrics"]["replacement_operator_count"] >= 83
    assert card["metrics"]["replacement_category_count"] >= 15
    assert card["replacement_sources"]["stage8718_inventory"].endswith("operator_inventory.json")


def test_stage9028_covers_gap_categories_and_operators() -> None:
    card = build_audit(registry())
    assert len(REQUIRED_RECOVERED_CATEGORIES) == 15
    assert len(REQUIRED_GAP_OPERATORS) == 10
    assert card["missing_categories"] == []
    assert card["missing_operators"] == []
    assert card["metrics"]["missing_gap_operators"] == 0


def test_stage9028_keeps_execution_training_and_scoring_closed() -> None:
    card = build_audit(registry())
    assert card["metrics"]["model_execution_attempted"] is False
    assert card["metrics"]["training_authorized"] is False
    assert card["metrics"]["data_mining_authorized"] is False
    assert card["metrics"]["scoring_authorized_next"] is False
    assert all(value is False for value in card["authority"].values())


def test_stage9028_validation_rejects_open_authority_or_training() -> None:
    assert validate_audit(build_audit(registry())) == []
    opened = build_audit(registry())
    opened["authority"] = dict(opened["authority"])
    opened["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_audit(opened)
    unsafe = build_audit(registry())
    unsafe["metrics"]["training_authorized"] = True
    assert "training_authorized" in validate_audit(unsafe)
