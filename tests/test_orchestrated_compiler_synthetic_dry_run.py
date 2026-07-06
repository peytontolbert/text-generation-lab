from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8931_orchestrated_compiler_synthetic_dry_run import (  # noqa: E402
    AUTHORITY_CLOSED,
    build_dry_run,
    validate_dry_run,
)


def registry() -> dict[str, object]:
    return {"metrics": {"latest_stage": 8930, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_synthetic_dry_run_emits_all_compiler_cards() -> None:
    card = build_dry_run(registry())
    assert card["checks"]["judge_rows_emitted"] is True
    assert card["checks"]["ranker_rows_emitted"] is True
    assert card["checks"]["shortcut_card_emitted"] is True
    assert card["checks"]["counterfactual_card_emitted"] is True
    assert card["checks"]["compile_card_emitted"] is True
    assert card["metrics"]["synthetic_rows"] == 4
    assert card["metrics"]["compiled_rows"] == 4


def test_synthetic_dry_run_keeps_loss_authority_closed() -> None:
    card = build_dry_run(registry())
    assert card["checks"]["decoder_loss_closed"] is True
    assert card["checks"]["denoise_loss_closed"] is True
    assert card["checks"]["runtime_loss_closed"] is True
    assert card["metrics"]["decoder_ce_loss_rows"] == 0
    assert card["metrics"]["denoise_ce_loss_rows"] == 0
    assert card["metrics"]["runtime_reward_rows"] == 0
    assert all(value is False for value in card["authority"].values())


def test_synthetic_dry_run_has_counterfactual_and_route_signal() -> None:
    card = build_dry_run(registry())
    assert card["counterfactual_card"]["rows"] == 4
    assert card["ranked_card"]["rows"] == 4
    assert "HOLD_LONG_OUTPUT" in card["ranked_card"]["route_counts"]
    assert "USE_FOR_DENOISE_REPAIR" in card["ranked_card"]["route_counts"]


def test_validation_rejects_bad_frontier_or_open_authority() -> None:
    assert validate_dry_run(build_dry_run(registry()), registry()) == []
    bad_registry = registry()
    bad_registry["metrics"]["latest_stage"] = 9999  # type: ignore[index]
    assert "unexpected_registry_frontier:9999" in validate_dry_run(build_dry_run(registry()), bad_registry)
    bad_card = build_dry_run(registry())
    bad_card["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_dry_run(bad_card, registry())
