from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9092_trainer_command_surface_static_refresh import (  # noqa: E402
    AUTHORITY_CLOSED,
    REQUIRED_FLAGS,
    REQUIRED_GUARD_TERMS,
    REQUIRED_MODES,
    build_card,
    validate_card,
)


def registry(latest: int = 9091) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9092_trainer_static_surface_contains_required_terms() -> None:
    card = build_card(registry())
    assert card["checks"]["trainer_exists"] is True
    assert card["checks"]["required_flags_present"] is True
    assert card["checks"]["required_modes_present"] is True
    assert card["checks"]["required_guard_terms_present"] is True
    assert card["missing_flags"] == []
    assert card["missing_modes"] == []
    assert card["missing_guard_terms"] == []
    assert len(REQUIRED_FLAGS) >= 20
    assert len(REQUIRED_MODES) >= 8
    assert len(REQUIRED_GUARD_TERMS) >= 16


def test_stage9092_keeps_trainer_static_only() -> None:
    card = build_card(registry())
    metrics = card["metrics"]
    assert metrics["trainer_static_inspection_only"] is True
    assert metrics["trainer_executed_now"] is False
    assert metrics["contract_only_invoked_now"] is False
    assert metrics["route_to_loss_translation_ready_now"] is False
    assert metrics["model_input_rows_now"] == 0
    assert metrics["candidate_rows_materialized"] == 0
    assert metrics["model_forward_attempted"] is False
    assert metrics["training_authorized"] is False
    assert not any(card["authority"].values())


def test_stage9092_validation_rejects_open_execution_or_bad_frontier() -> None:
    card = build_card(registry())
    assert validate_card(card, registry()) == []
    bad = build_card(registry())
    bad["metrics"]["trainer_executed_now"] = True
    assert "trainer_executed_now" in validate_card(bad, registry())
    bad_rows = build_card(registry())
    bad_rows["metrics"]["model_input_rows_now"] = 1
    assert "model_input_rows_now" in validate_card(bad_rows, registry())
    bad_authority = build_card(registry())
    bad_authority["authority"]["model_execution_authorized_next"] = True
    assert "authority_open" in validate_card(bad_authority, registry())
    assert "unexpected_registry_frontier:9999" in validate_card(card, registry(latest=9999))
