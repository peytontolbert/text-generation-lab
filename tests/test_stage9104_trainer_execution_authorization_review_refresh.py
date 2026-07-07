from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9104_trainer_execution_authorization_review_refresh import (  # noqa: E402
    AUTHORITY_CLOSED,
    REQUIRED_BEFORE_ANY_FUTURE_EXECUTION,
    build_card,
    validate_card,
)


def registry(latest: int = 9103) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9104_review_card_passes_but_authorizes_nothing() -> None:
    card = build_card(registry())
    assert card["passed"] is True
    assert card["checks"]["registry_frontier_stage9103"] is True
    assert card["metrics"]["review_failures"] == 0
    assert card["metrics"]["current_blockers"] >= 5
    assert card["metrics"]["same_stage_execution_authorized"] is False
    assert card["metrics"]["next_stage_execution_authorized"] is False
    assert not any(card["authority"].values())


def test_stage9104_records_future_requirements_and_current_blockers() -> None:
    card = build_card(registry())
    assert set(REQUIRED_BEFORE_ANY_FUTURE_EXECUTION).issubset(set(card["required_before_any_future_execution"]))
    assert "no_explicit_user_execution_request_for_trainer" in card["current_blockers"]
    assert "contract_only_artifacts_not_materialized" in card["current_blockers"]
    assert "no_one_run_training_ticket" in card["current_blockers"]


def test_stage9104_validation_rejects_execution_training_cleanup_or_bad_frontier() -> None:
    card = build_card(registry())
    assert validate_card(card, registry()) == []
    same_stage = build_card(registry())
    same_stage["metrics"]["same_stage_execution_authorized"] = True
    assert "same_stage_execution_authorized" in validate_card(same_stage, registry())
    next_stage = build_card(registry())
    next_stage["metrics"]["next_stage_execution_authorized"] = True
    assert "next_stage_execution_authorized" in validate_card(next_stage, registry())
    trainer = build_card(registry())
    trainer["metrics"]["trainer_executed_now"] = True
    assert "trainer_executed_now" in validate_card(trainer, registry())
    rows = build_card(registry())
    rows["metrics"]["model_input_rows_now"] = 1
    assert "model_input_rows_now" in validate_card(rows, registry())
    cleanup = build_card(registry())
    cleanup["metrics"]["cleanup_authorized_now"] = True
    assert "cleanup_authorized_now" in validate_card(cleanup, registry())
    authority = build_card(registry())
    authority["authority"]["model_execution_authorized_next"] = True
    assert "authority_open" in validate_card(authority, registry())
    assert "unexpected_registry_frontier:9999" in validate_card(card, registry(latest=9999))
