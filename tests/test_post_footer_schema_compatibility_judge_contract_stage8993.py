from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8993_post_footer_schema_compatibility_judge_contract import (  # noqa: E402
    AUTHORITY_CLOSED,
    COMPATIBILITY_CRITERIA,
    FORBIDDEN_JUDGE_ACTIONS,
    RECOMMENDED_ROUTES,
    SCHEMA_JUDGE_OUTPUT_FIELDS,
    build_contract,
    validate_contract,
)


def registry() -> dict[str, object]:
    return {"metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage8993_defines_schema_judge_outputs_and_routes() -> None:
    card = build_contract(registry())
    assert len(SCHEMA_JUDGE_OUTPUT_FIELDS) >= 10
    assert "compatible_with_curriculum_compiler" in SCHEMA_JUDGE_OUTPUT_FIELDS
    assert "SCHEMA_COMPATIBLE_CANDIDATE_PENDING_ROW_SAMPLE_TICKET" in RECOMMENDED_ROUTES
    assert card["metrics"]["schema_judge_output_fields"] >= 10


def test_stage8993_preserves_no_row_and_no_training_boundary() -> None:
    card = build_contract(registry())
    assert "read_dataset_rows" in FORBIDDEN_JUDGE_ACTIONS
    assert "claim_dataset_quality_from_schema_only" in FORBIDDEN_JUDGE_ACTIONS
    assert "no_row_body_needed_for_initial_schema_decision" in COMPATIBILITY_CRITERIA
    assert card["metrics"]["schema_judge_executed_now"] is False
    assert card["metrics"]["dataset_rows_loaded"] is False
    assert card["metrics"]["training_authorized"] is False
    assert all(value is False for value in card["authority"].values())


def test_stage8993_validation_rejects_execution_or_open_authority() -> None:
    card = build_contract(registry())
    assert validate_contract(card) == []
    bad = build_contract(registry())
    bad["metrics"]["schema_judge_executed_now"] = True
    assert "schema_judge_executed_now" in validate_contract(bad)
    auth = build_contract(registry())
    auth["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_contract(auth)
