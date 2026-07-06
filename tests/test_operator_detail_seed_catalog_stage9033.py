from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage9033_operator_detail_seed_catalog import (  # noqa: E402
    AUTHORITY_CLOSED,
    LAYER_TO_CATEGORY,
    LAYER_TO_ROLE,
    build_catalog,
    validate_catalog,
)


def registry() -> dict[str, object]:
    return {"metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9033_recovers_contiguous_op001_to_op108_seed_catalog() -> None:
    card = build_catalog(registry())
    rows = card["operator_detail_seed_rows"]
    assert card["metrics"]["operator_seed_rows"] == 108
    assert rows[0]["id"] == "OP001"
    assert rows[-1]["id"] == "OP108"
    assert {row["id"] for row in rows} == {f"OP{index:03d}" for index in range(1, 109)}
    assert card["metrics"]["missing_operator_ids"] == 0
    assert card["metrics"]["extra_operator_ids"] == 0


def test_stage9033_records_layer_roles_and_categories() -> None:
    card = build_catalog(registry())
    assert set(card["layer_to_role"]) == set("ABCDEFGHIJKL")
    assert set(card["layer_to_category"]) == set("ABCDEFGHIJKL")
    assert LAYER_TO_ROLE["I"] == "probabilistic_compression_and_calibration"
    assert LAYER_TO_CATEGORY["J"] == "memory_learning"
    assert card["metrics"]["layer_count"] == 12
    assert card["metrics"]["category_count"] == 12


def test_stage9033_marks_all_rows_metadata_only_not_training_ready() -> None:
    card = build_catalog(registry())
    rows = card["operator_detail_seed_rows"]
    assert card["metrics"]["metadata_only_rows"] == 108
    assert card["metrics"]["detail_training_ready_rows"] == 0
    assert all(row["detail_status"] == "name_layer_recovered_metadata_only" for row in rows)
    assert all(row["detail_required_before_mining"] is True for row in rows)
    assert all(row["detail_required_before_operator_specific_training"] is True for row in rows)
    assert all("inputs" in row["missing_detail_fields_before_training"] for row in rows)
    assert validate_catalog(card) == []


def test_stage9033_does_not_materialize_payloads_or_open_authority() -> None:
    card = build_catalog(registry())
    assert card["metrics"]["operator_details_materialized_now"] is False
    assert card["metrics"]["raw_session_text_materialized_now"] is False
    assert card["metrics"]["training_authorized"] is False
    assert card["metrics"]["data_mining_authorized"] is False
    assert card["metrics"]["decoder_ce_authorized"] is False
    assert card["metrics"]["denoise_ce_authorized"] is False
    assert all(value is False for value in card["authority"].values())


def test_stage9033_validation_rejects_open_authority_or_training_ready_rows() -> None:
    opened = build_catalog(registry())
    opened["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_catalog(opened)
    unsafe = build_catalog(registry())
    unsafe["metrics"]["detail_training_ready_rows"] = 1
    assert "detail_training_ready_rows" in validate_catalog(unsafe)
