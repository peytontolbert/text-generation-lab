from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9131_synthetic_route_to_loss_mask_translator_smoke_design_audit import (  # noqa: E402
    build_audit,
    run_negative_cases,
)


def test_stage9131_base_audit_passes() -> None:
    audit = build_audit()

    assert audit["passed"] is True
    assert audit["base_failures"] == []
    assert audit["checks"]["base_design_passes"] is True
    assert audit["checks"]["negative_cases_rejected"] is True
    assert audit["checks"]["required_smoke_checks_recorded"] is True
    assert audit["checks"]["synthetic_only"] is True
    assert audit["checks"]["no_materialization"] is True
    assert audit["checks"]["authority_closed"] is True


def test_stage9131_rejects_negative_cases() -> None:
    negatives = run_negative_cases()

    assert negatives
    assert all(item["rejected"] for item in negatives.values())
    for name in [
        "synthetic_loss_masks_materialized_now",
        "route_cards_materialized_now",
        "route_to_loss_translation_ready_now",
        "loss_mask_cards_materialized_now",
        "compiler_handoff_ready_now",
        "dataset_rows_loaded",
        "repository_source_bodies_loaded",
        "trainer_executed_now",
        "model_forward_attempted",
        "training_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
        "network_upload_performed",
        "cleanup_authorized_now",
    ]:
        assert name in negatives[name]["failures"]
    assert "decoder_ce_route_violation" in negatives["structured_fixture_maps_to_decoder_ce"]["failures"]
    assert "quarantine_fixture_has_enabled_loss" in negatives["quarantine_fixture_maps_to_loss"]["failures"]
    assert "missing_smoke_check:synthetic_only_inputs" in negatives["missing_synthetic_only_check"]["failures"]
    assert "real_route_cards_used" in negatives["real_route_cards_used"]["failures"]
    assert "authority_open" in negatives["authority_open"]["failures"]
    assert "unexpected_registry_frontier:9999" in negatives["unexpected_registry_frontier"]["failures"]


def test_stage9131_does_not_materialize_or_execute() -> None:
    audit = build_audit()
    metrics = audit["metrics"]

    assert metrics["real_route_cards_used"] == 0
    assert metrics["real_loss_masks_materialized"] == 0
    assert metrics["synthetic_loss_masks_materialized_now"] is False
    assert metrics["route_cards_materialized_now"] is False
    assert metrics["route_to_loss_translation_ready_now"] is False
    assert metrics["loss_mask_cards_materialized_now"] is False
    assert metrics["compiler_handoff_ready_now"] is False
    assert metrics["dataset_rows_loaded"] is False
    assert metrics["repository_source_bodies_loaded"] is False
    assert metrics["trainer_executed_now"] is False
    assert metrics["model_forward_attempted"] is False
    assert metrics["training_authorized"] is False
    assert metrics["decoder_ce_authorized"] is False
    assert metrics["denoise_ce_authorized"] is False
    assert metrics["runtime_authorized_flag"] is False
    assert metrics["network_upload_performed"] is False
    assert metrics["cleanup_authorized_now"] is False
    assert not any(audit["authority"].values())
