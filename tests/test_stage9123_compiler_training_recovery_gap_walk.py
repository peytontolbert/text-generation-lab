from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9123_compiler_training_recovery_gap_walk import (  # noqa: E402
    AUTHORITY_CLOSED,
    NEXT_SAFE_BRANCHES,
    OPEN_GAPS,
    build_card,
    validate_card,
)


def registry(latest: int = 9122) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9123_records_compiler_training_gaps() -> None:
    card = build_card(registry())

    assert card["checks"]["source_stage9122_passed"] is True
    assert card["checks"]["source_stage9122_inventory_closed"] is True
    assert "route_cards_not_materialized" in OPEN_GAPS
    assert "route_to_loss_translation_not_materialized" in OPEN_GAPS
    assert "loss_mask_cards_not_materialized_from_real_routes" in OPEN_GAPS
    assert "curriculum_compiler_single_entrypoint_design" in NEXT_SAFE_BRANCHES
    assert len(card["open_gaps"]) >= 10


def test_stage9123_keeps_compiler_training_execution_closed() -> None:
    card = build_card(registry())
    metrics = card["metrics"]

    assert metrics["route_cards_materialized_now"] is False
    assert metrics["route_to_loss_translation_ready_now"] is False
    assert metrics["loss_mask_cards_materialized_now"] is False
    assert metrics["compiler_handoff_ready_now"] is False
    assert metrics["trainer_contract_only_artifacts_materialized_now"] is False
    assert metrics["trainer_executed_now"] is False
    assert metrics["contract_only_invoked_now"] is False
    assert metrics["model_forward_attempted"] is False
    assert metrics["training_authorized"] is False
    assert metrics["decoder_ce_authorized"] is False
    assert metrics["denoise_ce_authorized"] is False
    assert metrics["runtime_authorized_flag"] is False
    assert metrics["inventory_execution_authorized_next"] is False
    assert metrics["arxiv_access_performed"] is False
    assert metrics["dataset_rows_loaded"] is False
    assert metrics["repository_source_bodies_loaded"] is False
    assert metrics["network_upload_performed"] is False
    assert metrics["cleanup_authorized_now"] is False
    assert not any(card["authority"].values())


def test_stage9123_validation_rejects_missing_gaps_or_open_execution() -> None:
    card = build_card(registry())
    assert validate_card(card, registry()) == []

    missing_gap = build_card(registry())
    missing_gap["open_gaps"].remove("route_cards_not_materialized")
    assert "missing_open_gap:route_cards_not_materialized" in validate_card(missing_gap, registry())

    routes = build_card(registry())
    routes["metrics"]["route_cards_materialized_now"] = True
    assert "route_cards_materialized_now" in validate_card(routes, registry())

    trainer = build_card(registry())
    trainer["metrics"]["trainer_executed_now"] = True
    assert "trainer_executed_now" in validate_card(trainer, registry())

    training = build_card(registry())
    training["metrics"]["training_authorized"] = True
    assert "training_authorized" in validate_card(training, registry())

    authority = build_card(registry())
    authority["authority"]["model_execution_authorized_next"] = True
    assert "authority_open" in validate_card(authority, registry())

    assert "unexpected_registry_frontier:9999" in validate_card(card, registry(latest=9999))
