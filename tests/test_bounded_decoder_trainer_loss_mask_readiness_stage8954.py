from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8954_bounded_decoder_trainer_loss_mask_readiness_refresh import (  # noqa: E402
    AUTHORITY_CLOSED,
    EXPECTED_RECOVERED_CAPS,
    REQUIRED_TRAINER_FLAGS,
    build_card,
    validate_card,
)


def registry(latest: int = 8953) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage8954_recovers_trainer_flag_and_guard_contract() -> None:
    card = build_card(registry())
    assert card["trainer_static_contract"]["trainer_exists"] is True
    assert len(REQUIRED_TRAINER_FLAGS) >= 20
    assert card["metrics"]["trainer_missing_required_flags"] == 0
    assert card["metrics"]["trainer_missing_runtime_guard_strings"] == 0
    assert card["checks"]["trainer_required_flags_present"] is True


def test_stage8954_preserves_bounded_loss_mask_caps_and_closed_execution() -> None:
    card = build_card(registry())
    assert card["metrics"]["loss_mask_rows"] == EXPECTED_RECOVERED_CAPS["loss_mask_rows"]
    assert card["metrics"]["unsafe_loss_rows"] == 0
    assert card["metrics"]["over_cap_rows"] == 0
    assert card["metrics"]["actual_execution_authorized_next"] is False
    assert card["metrics"]["model_execution_attempted"] is False
    assert card["metrics"]["training_authorized"] is False


def test_stage8954_validation_rejects_authority_or_execution_reopen() -> None:
    card = build_card(registry())
    assert validate_card(card, registry()) == []
    bad = build_card(registry())
    bad["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_card(bad, registry())
    bad_exec = build_card(registry())
    bad_exec["metrics"]["actual_execution_authorized_next"] = True
    assert "actual_execution_authorized_next" in validate_card(bad_exec, registry())
    assert "unexpected_registry_frontier:9999" in validate_card(card, registry(latest=9999))
