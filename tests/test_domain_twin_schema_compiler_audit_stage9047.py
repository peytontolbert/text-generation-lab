from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_stage9047_domain_twin_schema_compiler_audit import (  # noqa: E402
    ADAPTER_REQUIRED_RULES,
    COMPILER_ROW_REQUIRED_FIELDS,
    build_card,
    validate_card,
)


def test_stage9047_audit_requires_adapter_boundary_before_compiler_rows() -> None:
    card = build_card({"metrics": {"authority_counts": {}}})
    assert validate_card(card) == []
    assert "route" in COMPILER_ROW_REQUIRED_FIELDS
    assert "gate_status" in COMPILER_ROW_REQUIRED_FIELDS
    assert "loss_mask" in COMPILER_ROW_REQUIRED_FIELDS
    assert "source_metadata_records_must_not_be_compiler_rows_directly" in ADAPTER_REQUIRED_RULES
    assert card["metrics"]["domain_twin_records_compiled_now"] is False
    assert card["metrics"]["training_authorized"] is False


def test_stage9047_validation_rejects_adapter_execution_or_open_authority() -> None:
    card = build_card({"metrics": {"authority_counts": {}}})
    card["metrics"]["adapter_outputs_materialized_now"] = True
    card["authority"]["model_execution_authorized_next"] = True
    failures = validate_card(card)
    assert "adapter_outputs_materialized_now" in failures
    assert "authority_open" in failures
