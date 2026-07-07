from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9124_route_card_schema_recovery_design import (  # noqa: E402
    AUTHORITY_CLOSED,
    REQUIRED_ROUTE_FIELDS,
    ROUTE_ENUM,
    build_schema,
    validate_schema,
)


def registry(latest: int = 9123) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9124_records_route_card_schema() -> None:
    schema = build_schema(registry())

    assert schema["checks"]["source_stage9123_passed"] is True
    assert set(REQUIRED_ROUTE_FIELDS).issubset(schema["required_route_fields"])
    assert set(ROUTE_ENUM).issubset(schema["route_enum"])
    assert "KEEP_STRUCTURED" in schema["route_enum"]
    assert "KEEP_BOUNDED_DECODER" in schema["route_enum"]
    assert "HOLD_LONG_OUTPUT" in schema["route_enum"]
    assert "USE_FOR_DENOISE_REPAIR" in schema["route_enum"]
    assert "QUARANTINE_LABEL_CONFLICT" in schema["route_enum"]


def test_stage9124_does_not_materialize_routes_or_execute() -> None:
    schema = build_schema(registry())
    metrics = schema["metrics"]

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
    assert not any(schema["authority"].values())


def test_stage9124_validation_rejects_missing_schema_or_open_paths() -> None:
    schema = build_schema(registry())
    assert validate_schema(schema, registry()) == []

    missing_field = build_schema(registry())
    missing_field["required_route_fields"].remove("loss_mask_ref")
    assert "missing_route_field:loss_mask_ref" in validate_schema(missing_field, registry())

    missing_route = build_schema(registry())
    missing_route["route_enum"].remove("KEEP_BOUNDED_DECODER")
    assert "missing_route_enum:KEEP_BOUNDED_DECODER" in validate_schema(missing_route, registry())

    materialized = build_schema(registry())
    materialized["metrics"]["route_cards_materialized_now"] = True
    assert "route_cards_materialized_now" in validate_schema(materialized, registry())

    training = build_schema(registry())
    training["metrics"]["training_authorized"] = True
    assert "training_authorized" in validate_schema(training, registry())

    authority = build_schema(registry())
    authority["authority"]["model_execution_authorized_next"] = True
    assert "authority_open" in validate_schema(authority, registry())

    assert "unexpected_registry_frontier:9999" in validate_schema(schema, registry(latest=9999))
