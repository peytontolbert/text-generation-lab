from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9126_route_to_loss_translation_contract_design import (  # noqa: E402
    AUTHORITY_CLOSED,
    FORBIDDEN_TRANSLATIONS,
    ROUTE_TO_LOSSES,
    build_contract,
    validate_contract,
)


def registry(latest: int = 9125) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9126_records_route_to_loss_contract() -> None:
    contract = build_contract(registry())

    assert contract["checks"]["source_stage9125_passed"] is True
    assert contract["checks"]["route_to_losses_recorded"] is True
    assert contract["checks"]["quarantine_routes_have_no_losses"] is True
    assert "decoder_ce" in contract["route_to_losses"]["KEEP_BOUNDED_DECODER"]
    assert "decoder_ce" not in contract["route_to_losses"]["KEEP_STRUCTURED"]
    assert contract["route_to_losses"]["QUARANTINE_LABEL_CONFLICT"] == []
    assert contract["route_to_losses"]["DROP_DUPLICATE"] == []
    assert contract["route_to_losses"]["NEEDS_HUMAN_REVIEW"] == []
    assert set(FORBIDDEN_TRANSLATIONS).issubset(contract["forbidden_translations"])


def test_stage9126_does_not_translate_or_execute() -> None:
    contract = build_contract(registry())
    metrics = contract["metrics"]

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
    assert not any(contract["authority"].values())


def test_stage9126_validation_rejects_missing_mapping_or_open_paths() -> None:
    contract = build_contract(registry())
    assert validate_contract(contract, registry()) == []

    missing_route = build_contract(registry())
    del missing_route["route_to_losses"]["KEEP_BOUNDED_DECODER"]
    assert "missing_route_translation:KEEP_BOUNDED_DECODER" in validate_contract(missing_route, registry())

    missing_forbidden = build_contract(registry())
    missing_forbidden["forbidden_translations"].remove("HOLD_LONG_OUTPUT_to_decoder_ce")
    assert "missing_forbidden_translation:HOLD_LONG_OUTPUT_to_decoder_ce" in validate_contract(missing_forbidden, registry())

    ready = build_contract(registry())
    ready["metrics"]["route_to_loss_translation_ready_now"] = True
    assert "route_to_loss_translation_ready_now" in validate_contract(ready, registry())

    training = build_contract(registry())
    training["metrics"]["training_authorized"] = True
    assert "training_authorized" in validate_contract(training, registry())

    authority = build_contract(registry())
    authority["authority"]["model_execution_authorized_next"] = True
    assert "authority_open" in validate_contract(authority, registry())

    assert "unexpected_registry_frontier:9999" in validate_contract(contract, registry(latest=9999))


def test_stage9126_constants_preserve_decoder_ce_safety() -> None:
    assert "decoder_ce" in ROUTE_TO_LOSSES["KEEP_BOUNDED_DECODER"]
    for route in ["HOLD_LONG_OUTPUT", "USE_AS_NEGATIVE", "NEEDS_RETRIEVAL", "KEEP_STRUCTURED"]:
        assert "decoder_ce" not in ROUTE_TO_LOSSES[route]
