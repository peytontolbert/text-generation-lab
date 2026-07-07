from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9122_current_frontier_reconciliation_after_metadata_inventory_gates import (  # noqa: E402
    ACTIVE_BLOCKERS,
    AUTHORITY_CLOSED,
    NEXT_SAFE_BRANCHES,
    build_card,
    validate_card,
)


def registry(latest: int = 9121) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9122_reconciles_metadata_inventory_gate_chain() -> None:
    card = build_card(registry())

    assert card["checks"]["source_stage9117_passed"] is True
    assert card["checks"]["source_stage9120_passed"] is True
    assert card["checks"]["source_stage9121_passed"] is True
    assert card["checks"]["stage9117_runner_not_executed"] is True
    assert card["checks"]["stage9120_negative_cases_rejected"] is True
    assert card["checks"]["stage9121_execution_not_authorized"] is True
    assert "explicit_user_inventory_execution_request_missing" in ACTIVE_BLOCKERS
    assert "return_to_compiler_training_recovery_gap_walk" in NEXT_SAFE_BRANCHES


def test_stage9122_keeps_inventory_and_training_closed() -> None:
    card = build_card(registry())
    metrics = card["metrics"]

    assert metrics["inventory_execution_authorized_now"] is False
    assert metrics["inventory_execution_authorized_next"] is False
    assert metrics["runner_executed_now"] is False
    assert metrics["arxiv_access_performed"] is False
    assert metrics["dataset_file_names_read_now"] is False
    assert metrics["repository_root_names_read_now"] is False
    assert metrics["dataset_rows_loaded"] is False
    assert metrics["repository_source_bodies_loaded"] is False
    assert metrics["arxiv_write_authorized"] is False
    assert metrics["data_mining_authorized"] is False
    assert metrics["route_cards_materialized_now"] is False
    assert metrics["route_to_loss_translation_ready_now"] is False
    assert metrics["trainer_executed_now"] is False
    assert metrics["model_forward_attempted"] is False
    assert metrics["training_authorized"] is False
    assert metrics["decoder_ce_authorized"] is False
    assert metrics["denoise_ce_authorized"] is False
    assert metrics["runtime_authorized_flag"] is False
    assert metrics["network_upload_performed"] is False
    assert metrics["cleanup_authorized_now"] is False
    assert not any(card["authority"].values())


def test_stage9122_validation_rejects_open_inventory_training_or_bad_frontier() -> None:
    card = build_card(registry())
    assert validate_card(card, registry()) == []

    inventory = build_card(registry())
    inventory["metrics"]["inventory_execution_authorized_next"] = True
    assert "inventory_execution_authorized_next" in validate_card(inventory, registry())

    rows = build_card(registry())
    rows["metrics"]["dataset_rows_loaded"] = True
    assert "dataset_rows_loaded" in validate_card(rows, registry())

    route = build_card(registry())
    route["metrics"]["route_cards_materialized_now"] = True
    assert "route_cards_materialized_now" in validate_card(route, registry())

    training = build_card(registry())
    training["metrics"]["training_authorized"] = True
    assert "training_authorized" in validate_card(training, registry())

    authority = build_card(registry())
    authority["authority"]["model_execution_authorized_next"] = True
    assert "authority_open" in validate_card(authority, registry())

    assert "unexpected_registry_frontier:9999" in validate_card(card, registry(latest=9999))
