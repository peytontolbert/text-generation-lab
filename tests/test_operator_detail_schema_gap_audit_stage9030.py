from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage9030_operator_detail_schema_gap_audit import (  # noqa: E402
    AUTHORITY_CLOSED,
    DETAIL_FIELDS_REQUIRED_FOR_TRAINING_ROADMAP,
    RECOVERED_STAGE1239_SAMPLE_OPERATORS,
    build_audit,
    validate_audit,
)


def registry() -> dict[str, object]:
    return {"metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9030_records_stage8718_as_incomplete_detail_recovery() -> None:
    card = build_audit(registry())
    assert card["stage"] == 9030
    assert card["metrics"]["stage8718_operator_count"] >= 83
    assert card["metrics"]["stage8718_missing_detail_rows"] > 0
    assert card["metrics"]["operator_detail_schema_complete"] is False
    assert "full per-operator" in card["gap"]["stage1239_still_missing"]


def test_stage9030_recovers_stage1239_sample_names_from_sessions() -> None:
    card = build_audit(registry())
    assert len(RECOVERED_STAGE1239_SAMPLE_OPERATORS) >= 20
    assert card["metrics"]["recovered_stage1239_sample_hits"] >= 20
    assert "repo_fact_store_writer" in card["recovered_stage1239_sample_hits"]
    assert "target_codelength_scorer" in card["recovered_stage1239_sample_hits"]


def test_stage9030_required_training_roadmap_fields_are_explicit() -> None:
    card = build_audit(registry())
    for field in [
        "id",
        "name",
        "layer",
        "inputs",
        "outputs",
        "confidence_score",
        "failure_modes",
        "training_label_source",
        "metric",
    ]:
        assert field in DETAIL_FIELDS_REQUIRED_FOR_TRAINING_ROADMAP
        assert field in card["detail_fields_required_for_training_roadmap"]


def test_stage9030_keeps_mining_training_and_execution_closed() -> None:
    card = build_audit(registry())
    assert card["metrics"]["model_execution_attempted"] is False
    assert card["metrics"]["training_authorized"] is False
    assert card["metrics"]["data_mining_authorized"] is False
    assert card["metrics"]["decoder_ce_authorized"] is False
    assert card["metrics"]["denoise_ce_authorized"] is False
    assert all(value is False for value in card["authority"].values())
    assert validate_audit(card) == []


def test_stage9030_validation_rejects_open_authority_or_false_completion() -> None:
    opened = build_audit(registry())
    opened["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_audit(opened)
    false_complete = build_audit(registry())
    false_complete["metrics"]["operator_detail_schema_complete"] = True
    assert "operator_detail_schema_complete" in validate_audit(false_complete)
