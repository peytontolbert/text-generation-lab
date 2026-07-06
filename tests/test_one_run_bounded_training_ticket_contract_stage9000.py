from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage9000_one_run_bounded_training_ticket_contract import (  # noqa: E402
    AUTHORITY_CLOSED,
    BOUNDED_LIMITS,
    FORBIDDEN_OPERATIONS,
    REQUIRED_POST_RUN_TELEMETRY,
    build_contract,
    validate_contract,
)


def registry() -> dict[str, object]:
    return {"metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9000_records_bounded_limits_and_post_run_telemetry() -> None:
    card = build_contract(registry())
    assert BOUNDED_LIMITS["max_train_rows"] == 128
    assert BOUNDED_LIMITS["max_steps"] == 20
    assert BOUNDED_LIMITS["max_checkpoints_retained"] == 0
    assert "high_confidence_wrong_rows.jsonl" in REQUIRED_POST_RUN_TELEMETRY
    assert "gradient_norm_summary.json" in REQUIRED_POST_RUN_TELEMETRY
    assert card["metrics"]["required_post_run_telemetry"] >= 9


def test_stage9000_keeps_training_ticket_closed_now() -> None:
    card = build_contract(registry())
    assert "TRAINING_EXECUTION_NOW" in FORBIDDEN_OPERATIONS
    assert "FINAL_CHECKPOINT_EXPORT" in FORBIDDEN_OPERATIONS
    assert "PROMOTION" in FORBIDDEN_OPERATIONS
    assert card["metrics"]["training_ticket_authorized_now"] is False
    assert card["metrics"]["training_authorized"] is False
    assert card["metrics"]["model_execution_attempted"] is False
    assert all(value is False for value in card["authority"].values())


def test_stage9000_validation_rejects_scope_expansion_or_training_side_effects() -> None:
    assert validate_contract(build_contract(registry())) == []
    opened = build_contract(registry())
    opened["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_contract(opened)
    expanded = build_contract(registry())
    expanded["bounded_limits"]["max_steps"] = 21
    assert "max_steps_too_high" in validate_contract(expanded)
    unsafe = build_contract(registry())
    unsafe["metrics"]["training_executed_now"] = True
    assert "training_executed_now" in validate_contract(unsafe)
