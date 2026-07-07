from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9128_loss_mask_card_schema_recovery_design import (  # noqa: E402
    AUTHORITY_CLOSED,
    REQUIRED_DISABLED_BY_DEFAULT,
    REQUIRED_LOSS_MASK_FIELDS,
    REQUIRED_TELEMETRY,
    build_schema,
    validate_schema,
)


def registry(latest: int = 9127) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9128_records_loss_mask_schema() -> None:
    schema = build_schema(registry())

    assert schema["checks"]["source_stage9127_passed"] is True
    assert set(REQUIRED_LOSS_MASK_FIELDS).issubset(schema["required_loss_mask_fields"])
    assert set(REQUIRED_DISABLED_BY_DEFAULT).issubset(schema["required_disabled_by_default"])
    assert set(REQUIRED_TELEMETRY).issubset(schema["required_telemetry"])
    assert "decoder_ce" in schema["required_disabled_by_default"]
    assert "runtime_reward" in schema["required_disabled_by_default"]
    assert "row_token_loss_if_decoder_ce" in schema["required_telemetry"]


def test_stage9128_does_not_materialize_or_execute() -> None:
    schema = build_schema(registry())
    metrics = schema["metrics"]

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
    assert not any(schema["authority"].values())


def test_stage9128_validation_rejects_missing_fields_or_open_paths() -> None:
    schema = build_schema(registry())
    assert validate_schema(schema, registry()) == []

    missing_field = build_schema(registry())
    missing_field["required_loss_mask_fields"].remove("decoder_ce_allowed")
    assert "missing_loss_mask_field:decoder_ce_allowed" in validate_schema(missing_field, registry())

    missing_disabled = build_schema(registry())
    missing_disabled["required_disabled_by_default"].remove("decoder_ce")
    assert "missing_disabled_default_loss:decoder_ce" in validate_schema(missing_disabled, registry())

    missing_telemetry = build_schema(registry())
    missing_telemetry["required_telemetry"].remove("row_token_loss_if_decoder_ce")
    assert "missing_required_telemetry:row_token_loss_if_decoder_ce" in validate_schema(missing_telemetry, registry())

    materialized = build_schema(registry())
    materialized["metrics"]["loss_mask_cards_materialized_now"] = True
    assert "loss_mask_cards_materialized_now" in validate_schema(materialized, registry())

    training = build_schema(registry())
    training["metrics"]["training_authorized"] = True
    assert "training_authorized" in validate_schema(training, registry())

    authority = build_schema(registry())
    authority["authority"]["model_execution_authorized_next"] = True
    assert "authority_open" in validate_schema(authority, registry())

    assert "unexpected_registry_frontier:9999" in validate_schema(schema, registry(latest=9999))
