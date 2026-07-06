from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage9004_post_training_diagnostics_gate_contract import (  # noqa: E402
    AUTHORITY_CLOSED,
    FORBIDDEN_OPERATIONS,
    REQUIRED_DIAGNOSTIC_CHECKS,
    REQUIRED_INPUTS,
    build_contract,
    validate_contract,
)


def registry() -> dict[str, object]:
    return {"metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9004_requires_training_telemetry_and_diagnostics() -> None:
    card = build_contract(registry())
    assert "high_confidence_wrong_rows.jsonl" in REQUIRED_INPUTS
    assert "gradient_norm_summary.json" in REQUIRED_INPUTS
    assert "checkpoint_cleanup_proof.json" in REQUIRED_INPUTS
    assert "high_confidence_wrong_rows_below_gate_or_blocked" in REQUIRED_DIAGNOSTIC_CHECKS
    assert "promotion_blocker_report_present" in REQUIRED_DIAGNOSTIC_CHECKS
    assert card["metrics"]["required_diagnostic_checks"] >= 13


def test_stage9004_keeps_promotion_and_execution_closed() -> None:
    card = build_contract(registry())
    assert "RUN_POST_TRAINING_DIAGNOSTICS_NOW" in FORBIDDEN_OPERATIONS
    assert "PROMOTE_MODEL" in FORBIDDEN_OPERATIONS
    assert "START_ADDITIONAL_TRAINING" in FORBIDDEN_OPERATIONS
    assert card["metrics"]["post_training_diagnostics_authorized_now"] is False
    assert card["metrics"]["promotion_authorized"] is False
    assert card["metrics"]["training_authorized"] is False
    assert all(value is False for value in card["authority"].values())


def test_stage9004_validation_rejects_open_authority_or_side_effects() -> None:
    assert validate_contract(build_contract(registry())) == []
    opened = build_contract(registry())
    opened["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_contract(opened)
    unsafe = build_contract(registry())
    unsafe["metrics"]["promotion_authorized"] = True
    assert "promotion_authorized" in validate_contract(unsafe)
