from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage9018_row_sample_judge_output_materialization_blocker_audit import (  # noqa: E402
    AUTHORITY_CLOSED,
    FORBIDDEN_OPERATIONS,
    REQUIRED_AUTHORIZATION_CONDITIONS,
    REQUIRED_UPSTREAM_ARTIFACTS,
    build_audit,
    validate_audit,
)


def registry() -> dict[str, object]:
    return {"metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9018_records_materialization_prerequisites() -> None:
    card = build_audit(registry())
    assert len(REQUIRED_UPSTREAM_ARTIFACTS) == 4
    assert "stage9017_contract_present" in REQUIRED_AUTHORIZATION_CONDITIONS
    assert "row_sample_ticket_authorization_present" in REQUIRED_AUTHORIZATION_CONDITIONS
    assert "separate_materialization_execution_ticket_present" in REQUIRED_AUTHORIZATION_CONDITIONS
    assert card["metrics"]["authorization_conditions"] >= 9


def test_stage9018_blocks_materialization_without_upstream_artifacts() -> None:
    card = build_audit(registry())
    assert "MATERIALIZE_JUDGE_OUTPUTS_NOW" in FORBIDDEN_OPERATIONS
    assert "READ_ROW_BODIES_NOW" in FORBIDDEN_OPERATIONS
    assert "MATERIALIZE_MANIFEST_NOW" in FORBIDDEN_OPERATIONS
    assert card["metrics"]["materialization_ready"] is False
    assert card["metrics"]["materialization_authorized_now"] is False
    assert card["blocking_reasons"]
    assert all(value is False for value in card["authority"].values())


def test_stage9018_validation_rejects_open_authority_or_materialization() -> None:
    assert validate_audit(build_audit(registry())) == []
    opened = build_audit(registry())
    opened["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_audit(opened)
    unsafe = build_audit(registry())
    unsafe["metrics"]["judge_outputs_materialized_now"] = True
    assert "judge_outputs_materialized_now" in validate_audit(unsafe)
