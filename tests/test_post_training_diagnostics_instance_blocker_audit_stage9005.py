from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage9005_post_training_diagnostics_instance_blocker_audit import (  # noqa: E402
    AUTHORITY_CLOSED,
    FORBIDDEN_OPERATIONS,
    FUTURE_REQUIRED_ARTIFACTS,
    REQUIRED_READINESS_CONDITIONS,
    build_audit,
    validate_audit,
)


def registry() -> dict[str, object]:
    return {"metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9005_records_required_future_training_artifacts() -> None:
    card = build_audit(registry())
    assert len(FUTURE_REQUIRED_ARTIFACTS) == 9
    assert "training_run_card_present" in REQUIRED_READINESS_CONDITIONS
    assert "high_confidence_wrong_rows_present" in REQUIRED_READINESS_CONDITIONS
    assert "promotion_blocker_report_present" in REQUIRED_READINESS_CONDITIONS
    assert card["metrics"]["future_required_artifacts"] == 9


def test_stage9005_blocks_diagnostics_without_training_outputs() -> None:
    card = build_audit(registry())
    assert "RUN_POST_TRAINING_DIAGNOSTICS_NOW" in FORBIDDEN_OPERATIONS
    assert "PROMOTE_MODEL" in FORBIDDEN_OPERATIONS
    assert "START_ADDITIONAL_TRAINING" in FORBIDDEN_OPERATIONS
    assert card["metrics"]["diagnostics_instance_ready"] is False
    assert card["metrics"]["post_training_diagnostics_authorized_now"] is False
    assert card["blocking_reasons"]
    assert all(value is False for value in card["authority"].values())


def test_stage9005_validation_rejects_open_authority_or_execution_side_effects() -> None:
    assert validate_audit(build_audit(registry())) == []
    opened = build_audit(registry())
    opened["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_audit(opened)
    unsafe = build_audit(registry())
    unsafe["metrics"]["post_training_diagnostics_executed_now"] = True
    assert "post_training_diagnostics_executed_now" in validate_audit(unsafe)
