from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8998_trainer_contract_only_dry_run_contract import (  # noqa: E402
    AUTHORITY_CLOSED,
    REQUIRED_ASSERTIONS,
    REQUIRED_FLAGS,
    build_contract,
    validate_contract,
)


def registry() -> dict[str, object]:
    return {"metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage8998_records_required_flags_and_assertions() -> None:
    card = build_contract(registry())
    assert "--manifest" in REQUIRED_FLAGS
    assert "--require-loss-mask-enforcement-audit" in REQUIRED_FLAGS
    assert "--no-final-checkpoint-export" in REQUIRED_FLAGS
    assert "dry_run_stops_before_model_forward" in REQUIRED_ASSERTIONS
    assert card["metrics"]["required_flags"] >= 13


def test_stage8998_keeps_trainer_and_model_execution_closed() -> None:
    card = build_contract(registry())
    assert validate_contract(card) == []
    assert card["metrics"]["trainer_dry_run_authorized_now"] is False
    assert card["metrics"]["model_forward_attempted"] is False
    assert card["metrics"]["checkpoint_written"] is False
    assert card["metrics"]["training_authorized"] is False
    assert all(value is False for value in card["authority"].values())


def test_stage8998_validation_rejects_any_execution_or_open_authority() -> None:
    run = build_contract(registry())
    run["metrics"]["trainer_dry_run_executed_now"] = True
    assert "trainer_dry_run_executed_now" in validate_contract(run)
    ckpt = build_contract(registry())
    ckpt["metrics"]["checkpoint_written"] = True
    assert "checkpoint_written" in validate_contract(ckpt)
    opened = build_contract(registry())
    opened["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_contract(opened)
