from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9142_real_route_card_input_ticket_instance_schema_design import (  # noqa: E402
    INSTANCE_INVARIANTS,
    INSTANCE_REQUIRED_FIELDS,
    build_schema,
    validate_schema,
)
from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # noqa: E402


def registry(latest: int = 9141) -> dict:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9142_schema_passes_without_instance() -> None:
    schema = build_schema(registry())

    assert validate_schema(schema, registry()) == []
    assert all(schema["checks"].values())
    assert not any(schema["authority"].values())
    assert schema["metrics"]["ticket_instance_schema_designed"] is True
    assert schema["metrics"]["ticket_instance_materialized"] is False


def test_stage9142_records_instance_fields_and_invariants() -> None:
    schema = build_schema(registry())

    assert set(INSTANCE_REQUIRED_FIELDS).issubset(set(schema["instance_required_fields"]))
    assert set(INSTANCE_INVARIANTS).issubset(set(schema["instance_invariants"]))
    assert "approved_for_preflight_only" in schema["instance_required_fields"]
    assert "approved_for_route_card_materialization" in schema["instance_required_fields"]
    assert "manual_approval_record" in schema["instance_required_fields"]
    assert "approved_for_route_card_materialization_false" in schema["instance_invariants"]
    assert "arxiv_paths_forbidden_without_separate_authorization" in schema["instance_invariants"]
    assert "source_body_and_decoder_target_fields_forbidden" in schema["instance_invariants"]


def test_stage9142_keeps_authorization_closed() -> None:
    schema = build_schema(registry())
    metrics = schema["metrics"]

    assert metrics["approved_for_preflight_only"] is False
    assert metrics["approved_for_route_card_materialization"] is False
    assert metrics["real_input_authorized_now"] is False
    assert metrics["real_judge_rows_used"] == 0
    assert metrics["real_ranker_rows_used"] == 0
    assert metrics["real_route_cards_materialized"] == 0
    assert metrics["route_cards_materialized_now"] is False
    assert metrics["loss_mask_cards_materialized_now"] is False
    assert metrics["compiler_handoff_ready_now"] is False
    assert metrics["dataset_rows_loaded"] is False
    assert metrics["repository_source_bodies_loaded"] is False
    assert metrics["trainer_executed_now"] is False
    assert metrics["model_forward_attempted"] is False
    assert metrics["training_authorized"] is False
    assert metrics["decoder_ce_authorized"] is False
    assert metrics["runtime_authorized_flag"] is False
    assert metrics["cleanup_authorized_now"] is False


def test_stage9142_rejects_missing_fields_open_authority_and_bad_frontier() -> None:
    schema = build_schema(registry())
    schema["instance_required_fields"].remove("manual_approval_record")
    assert "missing_instance_field:manual_approval_record" in validate_schema(schema, registry())

    schema = build_schema(registry())
    schema["instance_invariants"].remove("approved_for_route_card_materialization_false")
    assert "missing_instance_invariant:approved_for_route_card_materialization_false" in validate_schema(schema, registry())

    schema = build_schema(registry())
    schema["metrics"]["approved_for_preflight_only"] = True
    assert "approved_for_preflight_only" in validate_schema(schema, registry())

    schema = build_schema(registry())
    schema["authority"]["model_execution_authorized_next"] = True
    assert "authority_open" in validate_schema(schema, registry())

    schema = build_schema(registry())
    assert "unexpected_registry_frontier:9999" in validate_schema(schema, registry(latest=9999))
