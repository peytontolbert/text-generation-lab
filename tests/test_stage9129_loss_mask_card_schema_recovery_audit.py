from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9129_loss_mask_card_schema_recovery_audit import (  # noqa: E402
    build_audit,
    run_negative_cases,
)


def test_stage9129_base_audit_passes() -> None:
    audit = build_audit()

    assert audit["passed"] is True
    assert audit["base_failures"] == []
    assert audit["checks"]["base_schema_passes"] is True
    assert audit["checks"]["negative_cases_rejected"] is True
    assert audit["checks"]["required_loss_mask_fields_recorded"] is True
    assert audit["checks"]["required_disabled_by_default_recorded"] is True
    assert audit["checks"]["required_telemetry_recorded"] is True
    assert audit["checks"]["no_loss_mask_materialization"] is True
    assert audit["checks"]["authority_closed"] is True


def test_stage9129_rejects_negative_cases() -> None:
    negatives = run_negative_cases()

    assert negatives
    assert all(item["rejected"] for item in negatives.values())
    for name in [
        "loss_mask_cards_materialized_now",
        "route_cards_materialized_now",
        "route_to_loss_translation_ready_now",
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
    assert "missing_loss_mask_field:loss_authority_evidence" in negatives["missing_loss_authority_evidence"]["failures"]
    assert "missing_disabled_default_loss:runtime_reward" in negatives["missing_runtime_reward_disabled_default"]["failures"]
    assert "missing_required_telemetry:loss_mask_enforcement_audit" in negatives["missing_loss_mask_enforcement_telemetry"]["failures"]
    assert "authority_open" in negatives["authority_open"]["failures"]
    assert "unexpected_registry_frontier:9999" in negatives["unexpected_registry_frontier"]["failures"]


def test_stage9129_does_not_materialize_or_execute() -> None:
    audit = build_audit()
    metrics = audit["metrics"]

    assert metrics["loss_mask_cards_materialized_now"] is False
    assert metrics["route_cards_materialized_now"] is False
    assert metrics["route_to_loss_translation_ready_now"] is False
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
