from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage9002_one_run_training_ticket_blocker_audit import (  # noqa: E402
    AUTHORITY_CLOSED,
    FORBIDDEN_OPERATIONS,
    FUTURE_REQUIRED_ARTIFACTS,
    REQUIRED_READINESS_CONDITIONS,
    build_audit,
    validate_audit,
)


def registry() -> dict[str, object]:
    return {"metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9002_records_future_dry_run_artifact_requirements() -> None:
    card = build_audit(registry())
    assert len(FUTURE_REQUIRED_ARTIFACTS) == 6
    assert "trainer_dry_run_execution_report_present" in REQUIRED_READINESS_CONDITIONS
    assert "loss_mask_enforcement_audit_present" in REQUIRED_READINESS_CONDITIONS
    assert "next_one_run_training_ticket_input_present" in REQUIRED_READINESS_CONDITIONS
    assert card["metrics"]["future_required_artifacts"] == 6


def test_stage9002_blocks_ticket_instantiation_without_real_dry_run() -> None:
    card = build_audit(registry())
    assert "INSTANTIATE_TRAINING_TICKET_NOW" in FORBIDDEN_OPERATIONS
    assert "RUN_TRAINING_NOW" in FORBIDDEN_OPERATIONS
    assert card["metrics"]["ticket_instantiation_ready"] is False
    assert card["metrics"]["training_ticket_authorized_now"] is False
    assert card["metrics"]["training_executed_now"] is False
    assert card["blocking_reasons"]
    assert all(value is False for value in card["authority"].values())


def test_stage9002_validation_rejects_authority_or_training_side_effects() -> None:
    assert validate_audit(build_audit(registry())) == []
    opened = build_audit(registry())
    opened["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_audit(opened)
    unsafe = build_audit(registry())
    unsafe["metrics"]["training_executed_now"] = True
    assert "training_executed_now" in validate_audit(unsafe)
