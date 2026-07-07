from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9130_synthetic_route_to_loss_mask_translator_smoke_design import (  # noqa: E402
    AUTHORITY_CLOSED,
    REQUIRED_SMOKE_CHECKS,
    build_design,
    validate_design,
)


def registry(latest: int = 9129) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9130_records_synthetic_fixtures_and_checks() -> None:
    design = build_design(registry())

    assert design["checks"]["source_stage9127_passed"] is True
    assert design["checks"]["source_stage9129_passed"] is True
    assert design["checks"]["synthetic_fixtures_recorded"] is True
    assert design["checks"]["decoder_ce_only_for_keep_bounded_decoder"] is True
    assert set(REQUIRED_SMOKE_CHECKS).issubset(design["required_smoke_checks"])
    routes = {fixture["route"] for fixture in design["synthetic_fixtures"]}
    assert "KEEP_STRUCTURED" in routes
    assert "KEEP_BOUNDED_DECODER" in routes
    assert "HOLD_LONG_OUTPUT" in routes
    assert "USE_FOR_DENOISE_REPAIR" in routes
    assert "NEEDS_RETRIEVAL" in routes
    assert "QUARANTINE_LABEL_CONFLICT" in routes


def test_stage9130_decoder_ce_only_on_bounded_fixture() -> None:
    design = build_design(registry())
    decoder_routes = {
        fixture["route"]
        for fixture in design["synthetic_fixtures"]
        if "decoder_ce" in fixture["expected_enabled_losses"]
    }
    assert decoder_routes == {"KEEP_BOUNDED_DECODER"}
    for fixture in design["synthetic_fixtures"]:
        if fixture["route"] == "QUARANTINE_LABEL_CONFLICT":
            assert fixture["expected_enabled_losses"] == []


def test_stage9130_does_not_materialize_or_execute() -> None:
    design = build_design(registry())
    metrics = design["metrics"]

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
    assert not any(design["authority"].values())


def test_stage9130_validation_rejects_bad_smoke_design_or_open_paths() -> None:
    design = build_design(registry())
    assert validate_design(design, registry()) == []

    bad_decoder = build_design(registry())
    bad_decoder["synthetic_fixtures"][0]["expected_enabled_losses"].append("decoder_ce")
    assert "decoder_ce_route_violation" in validate_design(bad_decoder, registry())

    bad_quarantine = build_design(registry())
    for fixture in bad_quarantine["synthetic_fixtures"]:
        if fixture["route"] == "QUARANTINE_LABEL_CONFLICT":
            fixture["expected_enabled_losses"].append("action_ce")
    assert "quarantine_fixture_has_enabled_loss" in validate_design(bad_quarantine, registry())

    missing_check = build_design(registry())
    missing_check["required_smoke_checks"].remove("synthetic_only_inputs")
    assert "missing_smoke_check:synthetic_only_inputs" in validate_design(missing_check, registry())

    materialized = build_design(registry())
    materialized["metrics"]["loss_mask_cards_materialized_now"] = True
    assert "loss_mask_cards_materialized_now" in validate_design(materialized, registry())

    real_data = build_design(registry())
    real_data["metrics"]["real_route_cards_used"] = 1
    assert "real_route_cards_used" in validate_design(real_data, registry())

    authority = build_design(registry())
    authority["authority"]["model_execution_authorized_next"] = True
    assert "authority_open" in validate_design(authority, registry())

    assert "unexpected_registry_frontier:9999" in validate_design(design, registry(latest=9999))
