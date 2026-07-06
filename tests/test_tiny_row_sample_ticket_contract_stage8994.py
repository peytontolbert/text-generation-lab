from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8994_tiny_row_sample_ticket_contract import (  # noqa: E402
    AUTHORITY_CLOSED,
    FORBIDDEN_OPERATIONS,
    REQUIRED_ASSERTIONS,
    REQUIRED_OUTPUTS,
    TICKET_FIELDS,
    build_contract,
    validate_contract,
)


def registry() -> dict[str, object]:
    return {"metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage8994_defines_bounded_ticket_fields_and_outputs() -> None:
    card = build_contract(registry())
    assert len(TICKET_FIELDS) >= 15
    assert "compatible_candidate_ids" in TICKET_FIELDS
    assert "lineage_fields_required" in TICKET_FIELDS
    assert "row_sample_manifest_metadata.jsonl" in REQUIRED_OUTPUTS
    assert "post_sample_dataset_judge_required_before_manifest_compile" in REQUIRED_ASSERTIONS
    assert card["limits"]["max_candidates"] == 3
    assert card["limits"]["max_rows_per_candidate"] == 3
    assert card["limits"]["max_total_rows"] == 9


def test_stage8994_preserves_no_sampling_no_training_boundary() -> None:
    card = build_contract(registry())
    assert "ROW_SAMPLE_EXECUTION_NOW" in FORBIDDEN_OPERATIONS
    assert "LOCKED_EVAL_ROW_READ" in FORBIDDEN_OPERATIONS
    assert "TRAINING" in FORBIDDEN_OPERATIONS
    assert card["metrics"]["row_sample_authorized_now"] is False
    assert card["metrics"]["dataset_rows_loaded"] is False
    assert card["metrics"]["training_authorized"] is False
    assert all(value is False for value in card["authority"].values())


def test_stage8994_validation_catches_open_authority_or_scope_expansion() -> None:
    assert validate_contract(build_contract(registry())) == []
    opened = build_contract(registry())
    opened["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_contract(opened)
    expanded = build_contract(registry())
    expanded["limits"]["max_total_rows"] = 10
    assert "max_total_rows_too_high" in validate_contract(expanded)
    unsafe = build_contract(registry())
    unsafe["metrics"]["locked_eval_rows_loaded"] = True
    assert "locked_eval_rows_loaded" in validate_contract(unsafe)
