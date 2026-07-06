from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage9016_row_sample_judge_output_readiness_audit import (  # noqa: E402
    AUTHORITY_CLOSED,
    REQUIRED_INPUT_ARTIFACTS,
    build_audit,
    validate_audit,
)


def registry() -> dict[str, object]:
    return {"metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}, "rows": []}


def test_stage9016_records_four_required_inputs() -> None:
    card = build_audit(registry())
    assert len(REQUIRED_INPUT_ARTIFACTS) == 4
    assert "row_sample_dataset_judge_report.json" in card["required_input_artifacts"]
    assert "accepted_row_ids_pending_manifest_compile.jsonl" in card["required_input_artifacts"]
    assert "judge_to_compiler_gate_status.json" in card["required_input_artifacts"]


def test_stage9016_blocks_until_inputs_exist_without_execution() -> None:
    card = build_audit(registry())
    assert card["metrics"]["row_sample_judge_outputs_ready"] is False
    assert card["metrics"]["manifest_materialized_now"] is False
    assert card["metrics"]["row_body_read_authorized_now"] is False
    assert card["blocking_reasons"]
    assert validate_audit(card) == []


def test_stage9016_validation_rejects_execution_or_open_authority() -> None:
    unsafe = build_audit(registry())
    unsafe["metrics"]["manifest_materialization_authorized_now"] = True
    assert "manifest_materialization_authorized_now" in validate_audit(unsafe)
    opened = build_audit(registry())
    opened["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_audit(opened)
