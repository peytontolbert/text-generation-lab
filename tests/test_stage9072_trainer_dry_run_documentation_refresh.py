from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9072_trainer_dry_run_documentation_refresh import (  # noqa: E402
    AUTHORITY_CLOSED,
    DOCUMENTED_HARD_STOPS,
    REQUIRED_LONG_CONTEXT_INPUTS,
    build_card,
    validate_card,
)


def registry(latest: int = 9071) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9072_preserves_long_context_dry_run_inputs() -> None:
    card = build_card(registry())
    assert card["metrics"]["source_summaries_passed"] == card["metrics"]["source_summaries"]
    for required in REQUIRED_LONG_CONTEXT_INPUTS:
        assert required in card["recovered_inputs"]
    assert card["checks"]["long_context_inputs_preserved"] is True
    assert card["checks"]["stage9071_training_closed"] is True


def test_stage9072_documents_hard_stops_and_closed_authority() -> None:
    card = build_card(registry())
    for hard_stop in DOCUMENTED_HARD_STOPS:
        assert hard_stop in card["recovered_assertions"]
    assert card["metrics"]["trainer_invoked"] is False
    assert card["metrics"]["model_forward_attempted"] is False
    assert card["metrics"]["candidate_rows_materialized"] == 0
    assert not any(card["authority"].values())


def test_stage9072_validation_rejects_execution_or_bad_frontier() -> None:
    card = build_card(registry())
    assert validate_card(card, registry()) == []
    bad = build_card(registry())
    bad["metrics"]["trainer_invoked"] = True
    assert "trainer_invoked" in validate_card(bad, registry())
    bad_authority = build_card(registry())
    bad_authority["authority"]["decoder_ce_training_authorized_next"] = True
    assert "authority_open" in validate_card(bad_authority, registry())
    assert "unexpected_registry_frontier:9999" in validate_card(card, registry(latest=9999))
