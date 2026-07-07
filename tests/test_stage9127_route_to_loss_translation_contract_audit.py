from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9127_route_to_loss_translation_contract_audit import (  # noqa: E402
    build_audit,
    run_negative_cases,
    semantic_failures,
)
from scripts.build_stage9126_route_to_loss_translation_contract_design import build_contract  # noqa: E402


def registry(latest: int = 9125) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {}}}


def test_stage9127_base_audit_passes() -> None:
    audit = build_audit()

    assert audit["passed"] is True
    assert audit["base_failures"] == []
    assert audit["checks"]["base_contract_passes"] is True
    assert audit["checks"]["negative_cases_rejected"] is True
    assert audit["checks"]["decoder_ce_only_on_bounded_decoder_route"] is True
    assert audit["checks"]["quarantine_routes_have_no_losses"] is True
    assert audit["checks"]["authority_closed"] is True


def test_stage9127_rejects_negative_cases() -> None:
    negatives = run_negative_cases()

    assert negatives
    assert all(item["rejected"] for item in negatives.values())
    for name in [
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
    assert "missing_route_translation:KEEP_BOUNDED_DECODER" in negatives["missing_keep_bounded_decoder_translation"]["failures"]
    assert "missing_forbidden_translation:HOLD_LONG_OUTPUT_to_decoder_ce" in negatives["missing_hold_long_output_forbidden_translation"]["failures"]
    assert "forbidden_decoder_ce_route:HOLD_LONG_OUTPUT" in negatives["hold_long_output_maps_to_decoder_ce"]["failures"]
    assert "quarantine_route_has_loss:QUARANTINE_LABEL_CONFLICT" in negatives["quarantine_maps_to_loss"]["failures"]
    assert "authority_open" in negatives["authority_open"]["failures"]
    assert "unexpected_registry_frontier:9999" in negatives["unexpected_registry_frontier"]["failures"]


def test_stage9127_semantic_failures_catch_bad_decoder_ce_routes() -> None:
    contract = build_contract(registry())
    assert semantic_failures(contract) == []

    contract["route_to_losses"]["NEEDS_RETRIEVAL"].append("decoder_ce")
    assert "forbidden_decoder_ce_route:NEEDS_RETRIEVAL" in semantic_failures(contract)


def test_stage9127_does_not_translate_or_execute() -> None:
    audit = build_audit()
    metrics = audit["metrics"]

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
