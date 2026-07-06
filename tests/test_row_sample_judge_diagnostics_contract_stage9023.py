from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage9023_row_sample_judge_diagnostics_contract import (  # noqa: E402
    AUTHORITY_CLOSED,
    FORBIDDEN_FIELDS,
    REJECT_REASON_CODES,
    REQUIRED_CRITERIA,
    REQUIRED_REPORT_FIELDS,
    REQUIRED_ROW_SCORE_FIELDS,
    build_contract,
    validate_contract,
)


def registry() -> dict[str, object]:
    return {"metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9023_records_diagnostic_fields_for_future_judge_outputs() -> None:
    card = build_contract(registry())
    assert len(REQUIRED_REPORT_FIELDS) >= 11
    assert len(REQUIRED_ROW_SCORE_FIELDS) >= 14
    assert "quality_score" in REQUIRED_ROW_SCORE_FIELDS
    assert "criteria_scores" in REQUIRED_ROW_SCORE_FIELDS
    assert "feature_presence" in REQUIRED_ROW_SCORE_FIELDS
    assert "loss_mask_candidates" in REQUIRED_ROW_SCORE_FIELDS
    assert card["metrics"]["diagnostics_contract_only"] is True


def test_stage9023_requires_dataset_quality_and_leakage_criteria() -> None:
    card = build_contract(registry())
    assert "target_leakage_absent" in REQUIRED_CRITERIA
    assert "shortcut_proxy_absent" in REQUIRED_CRITERIA
    assert "near_duplicate_risk_below_threshold" in REQUIRED_CRITERIA
    assert "junk_ood_rank_acceptable" in REQUIRED_CRITERIA
    assert "unsafe_loss_mask" in REJECT_REASON_CODES
    assert "requires_source_body_text" in REJECT_REASON_CODES
    assert validate_contract(card) == []


def test_stage9023_forbids_body_text_and_execution_paths() -> None:
    card = build_contract(registry())
    assert "raw_row_body" in FORBIDDEN_FIELDS
    assert "raw_repository_source_body" in FORBIDDEN_FIELDS
    assert "model_logits" in FORBIDDEN_FIELDS
    assert card["metrics"]["judge_executed_now"] is False
    assert card["metrics"]["judge_outputs_materialized_now"] is False
    assert card["metrics"]["row_bodies_read_now"] is False
    assert card["metrics"]["manifest_compile_authorized_now"] is False
    assert card["metrics"]["training_authorized"] is False
    assert all(value is False for value in card["authority"].values())


def test_stage9023_validation_rejects_open_authority_or_side_effects() -> None:
    opened = build_contract(registry())
    opened["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_contract(opened)
    unsafe = build_contract(registry())
    unsafe["metrics"]["decoder_ce_authorized"] = True
    assert "decoder_ce_authorized" in validate_contract(unsafe)
    unsafe = build_contract(registry())
    unsafe["metrics"]["judge_outputs_materialized_now"] = True
    assert "judge_outputs_materialized_now" in validate_contract(unsafe)
