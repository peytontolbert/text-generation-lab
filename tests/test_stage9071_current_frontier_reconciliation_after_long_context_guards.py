from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9071_current_frontier_reconciliation_after_long_context_guards import (  # noqa: E402
    AUTHORITY_CLOSED,
    CURRENT_BLOCKED_AUTHORITY,
    CURRENT_RECOVERED_CONTROLS,
    build_card,
    validate_card,
)


def registry(latest: int = 9070) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9071_reconciles_recent_chain() -> None:
    card = build_card(registry())
    assert card["metrics"]["source_summaries_passed"] == card["metrics"]["source_summaries"]
    assert len(CURRENT_RECOVERED_CONTROLS) >= 7
    assert card["checks"]["stage9066_negative_cases_rejected"] is True
    assert card["checks"]["stage9070_no_candidate_mining"] is True


def test_stage9071_records_closed_authority() -> None:
    card = build_card(registry())
    for authority in ["model_execution", "trainer_execution", "candidate_mining", "decoder_ce_training", "arxiv_read_write_for_compiler"]:
        assert authority in CURRENT_BLOCKED_AUTHORITY
    assert card["metrics"]["training_ready"] is False
    assert card["metrics"]["candidate_rows_materialized"] == 0
    assert card["metrics"]["real_index_rows_written"] == 0
    assert not any(card["authority"].values())


def test_stage9071_validation_rejects_authority_or_bad_frontier() -> None:
    card = build_card(registry())
    assert validate_card(card, registry()) == []
    bad = build_card(registry())
    bad["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_card(bad, registry())
    bad_train = build_card(registry())
    bad_train["metrics"]["training_ready"] = True
    assert "training_ready" in validate_card(bad_train, registry())
    assert "unexpected_registry_frontier:9999" in validate_card(card, registry(latest=9999))
