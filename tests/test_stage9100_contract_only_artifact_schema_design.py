from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9100_contract_only_artifact_schema_design import (  # noqa: E402
    AUTHORITY_CLOSED,
    CONTRACT_ONLY_SCHEMA,
    FORBIDDEN_OPERATIONS,
    REQUIRED_TELEMETRY_ARTIFACTS,
    build_schema,
    validate_schema,
)


def registry(latest: int = 9099) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9100_records_contract_only_artifact_schema() -> None:
    card = build_schema(registry())
    assert card["checks"]["source_stage9099_passed"] is True
    assert card["checks"]["schema_artifacts_recorded"] is True
    assert card["checks"]["telemetry_artifacts_included"] is True
    assert card["checks"]["jsonl_artifact_requirements_included"] is True
    assert set(CONTRACT_ONLY_SCHEMA).issubset(set(card["contract_only_schema"]))


def test_stage9100_keeps_contract_only_invocation_and_training_closed() -> None:
    card = build_schema(registry())
    metrics = card["metrics"]
    assert metrics["trainer_executed_now"] is False
    assert metrics["contract_only_invoked_now"] is False
    assert metrics["runtime_assertions_executed_now"] is False
    assert metrics["model_input_rows_now"] == 0
    assert metrics["candidate_rows_materialized"] == 0
    assert metrics["model_forward_attempted"] is False
    assert metrics["training_authorized"] is False
    assert metrics["decoder_ce_authorized"] is False
    assert metrics["denoise_ce_authorized"] is False
    assert metrics["arxiv_write_authorized"] is False
    assert metrics["cleanup_authorized_now"] is False
    assert not any(card["authority"].values())


def test_stage9100_validation_rejects_missing_schema_or_open_authority() -> None:
    card = build_schema(registry())
    assert validate_schema(card, registry()) == []
    missing_schema = build_schema(registry())
    missing_schema["contract_only_schema"].pop("no_model_forward_proof.json")
    assert "missing_schema_artifact:no_model_forward_proof.json" in validate_schema(missing_schema, registry())
    missing_telemetry = build_schema(registry())
    missing_telemetry["contract_only_schema"]["telemetry_artifact_plan.json"]["contains_all"]["required_artifacts"].remove("row_gradient_norms.jsonl")
    assert "missing_required_telemetry_artifact:row_gradient_norms.jsonl" in validate_schema(missing_telemetry, registry())
    opened = build_schema(registry())
    opened["authority"]["model_execution_authorized_next"] = True
    assert "authority_open" in validate_schema(opened, registry())
    invoked = build_schema(registry())
    invoked["metrics"]["contract_only_invoked_now"] = True
    assert "contract_only_invoked_now" in validate_schema(invoked, registry())
    rows = build_schema(registry())
    rows["metrics"]["model_input_rows_now"] = 1
    assert "model_input_rows_now" in validate_schema(rows, registry())
    assert "unexpected_registry_frontier:9999" in validate_schema(card, registry(latest=9999))


def test_stage9100_forbidden_operation_inventory_is_complete() -> None:
    card = build_schema(registry())
    assert set(FORBIDDEN_OPERATIONS).issubset(set(card["forbidden_operations"]))
    assert set(REQUIRED_TELEMETRY_ARTIFACTS).issubset(
        set(card["contract_only_schema"]["telemetry_artifact_plan.json"]["contains_all"]["required_artifacts"])
    )
