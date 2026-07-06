from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8955_bounded_decoder_no_execution_telemetry_gate import (  # noqa: E402
    AUTHORITY_CLOSED,
    GATED_BEFORE_EXECUTION,
    MANDATORY_FAILURE_MODES,
    build_gate,
    validate_gate,
)


def registry(latest: int = 8954) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage8955_records_required_bounded_decoder_telemetry_artifacts() -> None:
    gate = build_gate(registry())
    required = set(gate["required_bounded_jsonl_artifacts"]) | set(gate["required_bounded_json_artifacts"])
    for artifact in GATED_BEFORE_EXECUTION:
        assert artifact in required
    assert gate["metrics"]["required_bounded_jsonl_artifacts"] >= 6
    assert gate["metrics"]["required_bounded_json_artifacts"] >= 9


def test_stage8955_requires_nonempty_schema_and_real_token_loss_checks() -> None:
    gate = build_gate(registry())
    assert "empty_jsonl_artifact" in MANDATORY_FAILURE_MODES
    assert "row_token_loss_without_per_position_loss" in MANDATORY_FAILURE_MODES
    assert gate["checks"]["row_token_loss_requires_positions"] is True
    assert gate["checks"]["jsonl_empty_failure_present"] is True
    assert gate["checks"]["native_test_covers_bounded_token_positions"] is True


def test_stage8955_keeps_execution_mining_and_training_closed() -> None:
    gate = build_gate(registry())
    assert gate["metrics"]["actual_execution_authorized_next"] is False
    assert gate["metrics"]["model_execution_attempted"] is False
    assert gate["metrics"]["training_authorized"] is False
    assert gate["metrics"]["data_mining_authorized"] is False
    assert gate["metrics"]["decoder_ce_authorized"] is False
    assert all(value is False for value in gate["authority"].values())


def test_stage8955_validation_rejects_open_authority_or_bad_frontier() -> None:
    gate = build_gate(registry())
    assert validate_gate(gate, registry()) == []
    bad = build_gate(registry())
    bad["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_gate(bad, registry())
    bad_exec = build_gate(registry())
    bad_exec["metrics"]["actual_execution_authorized_next"] = True
    assert "actual_execution_authorized_next" in validate_gate(bad_exec, registry())
    assert "unexpected_registry_frontier:9999" in validate_gate(gate, registry(latest=9999))
