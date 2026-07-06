from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8999_trainer_contract_dry_run_contract import (  # noqa: E402
    AUTHORITY_CLOSED,
    FORBIDDEN_OPERATIONS,
    REQUIRED_DRY_RUN_CHECKS,
    REQUIRED_TELEMETRY_OUTPUTS,
    build_contract,
    validate_contract,
)


def registry() -> dict[str, object]:
    return {"metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage8999_records_trainer_dry_run_safety_checks() -> None:
    card = build_contract(registry())
    assert "no_model_weights_loaded" in REQUIRED_DRY_RUN_CHECKS
    assert "no_optimizer_created" in REQUIRED_DRY_RUN_CHECKS
    assert "no_backward_called" in REQUIRED_DRY_RUN_CHECKS
    assert "authority_ticket_required_for_real_training" in REQUIRED_DRY_RUN_CHECKS
    assert "dry_run_contract_report.json" in REQUIRED_TELEMETRY_OUTPUTS
    assert card["metrics"]["required_dry_run_checks"] >= 13


def test_stage8999_keeps_trainer_and_training_closed() -> None:
    card = build_contract(registry())
    assert "TRAINER_DRY_RUN_EXECUTION_NOW" in FORBIDDEN_OPERATIONS
    assert "MODEL_WEIGHT_LOAD" in FORBIDDEN_OPERATIONS
    assert "START_TRAINING" in FORBIDDEN_OPERATIONS
    assert card["metrics"]["trainer_dry_run_authorized_now"] is False
    assert card["metrics"]["model_weights_loaded"] is False
    assert card["metrics"]["training_authorized"] is False
    assert all(value is False for value in card["authority"].values())


def test_stage8999_validation_rejects_training_side_effects() -> None:
    assert validate_contract(build_contract(registry())) == []
    opened = build_contract(registry())
    opened["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_contract(opened)
    loaded = build_contract(registry())
    loaded["metrics"]["model_weights_loaded"] = True
    assert "model_weights_loaded" in validate_contract(loaded)
    backward = build_contract(registry())
    backward["metrics"]["backward_called"] = True
    assert "backward_called" in validate_contract(backward)
