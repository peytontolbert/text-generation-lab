from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage9021_locked_manifest_compile_blocker_audit import (  # noqa: E402
    AUTHORITY_CLOSED,
    BLOCKING_REASONS,
    FORBIDDEN_OPERATIONS,
    REQUIRED_MANIFEST_INPUTS,
    build_audit,
    validate_audit,
)


def registry() -> dict[str, object]:
    return {"metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9021_blocks_schema_only_gate_status() -> None:
    card = build_audit(registry())
    assert card["readiness"]["stage9020_schema_contract_passed"] is True
    assert card["readiness"]["schema_only_not_treated_as_materialized_gate"] is True
    assert "schema_only_stage9020_is_not_gate_materialization" in card["blocking_reasons"]
    assert BLOCKING_REASONS["schema_only_stage9020_is_not_gate_materialization"]


def test_stage9021_requires_real_manifest_inputs_before_compile() -> None:
    card = build_audit(registry())
    assert len(REQUIRED_MANIFEST_INPUTS) == 4
    for name in REQUIRED_MANIFEST_INPUTS:
        assert name in card["required_manifest_inputs"]
    assert card["metrics"]["present_manifest_inputs"] == 0
    assert card["metrics"]["missing_manifest_inputs"] == 4
    assert card["metrics"]["manifest_compile_ready"] is False


def test_stage9021_keeps_manifest_training_and_execution_closed() -> None:
    card = build_audit(registry())
    assert "MATERIALIZE_LOCKED_TRAINING_MANIFEST" in FORBIDDEN_OPERATIONS
    assert "READ_ROW_BODY_TEXT" in FORBIDDEN_OPERATIONS
    assert "WRITE_TO_ARXIV" in FORBIDDEN_OPERATIONS
    assert card["metrics"]["manifest_compile_authorized_now"] is False
    assert card["metrics"]["manifest_materialized_now"] is False
    assert card["metrics"]["training_authorized"] is False
    assert card["metrics"]["model_execution_attempted"] is False
    assert all(value is False for value in card["authority"].values())


def test_stage9021_validation_rejects_open_authority_or_side_effects() -> None:
    assert validate_audit(build_audit(registry())) == []
    opened = build_audit(registry())
    opened["authority"] = dict(opened["authority"])
    opened["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_audit(opened)
    unsafe = build_audit(registry())
    unsafe["metrics"]["manifest_materialized_now"] = True
    assert "manifest_materialized_now" in validate_audit(unsafe)
