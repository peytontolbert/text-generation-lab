from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage9017_row_sample_judge_output_materialization_contract import (  # noqa: E402
    AUTHORITY_CLOSED,
    FUTURE_OUTPUTS,
    MATERIALIZATION_RULES,
    OUTPUT_SCHEMA,
    build_contract,
    validate_contract,
)


def registry() -> dict[str, object]:
    return {"metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}, "rows": []}


def test_stage9017_records_judge_outputs_and_schema() -> None:
    card = build_contract(registry())
    for output in ["row_sample_dataset_judge_report.json", "candidate_row_quality_scores.jsonl", "accepted_row_ids_pending_manifest_compile.jsonl", "judge_to_compiler_gate_status.json"]:
        assert output in FUTURE_OUTPUTS
        assert output in OUTPUT_SCHEMA
    assert card["metrics"]["future_outputs"] == 5


def test_stage9017_forbids_body_reads_and_training() -> None:
    card = build_contract(registry())
    assert "do_not_read_row_bodies" in MATERIALIZATION_RULES
    assert "emit_row_ids_and_scores_only" in MATERIALIZATION_RULES
    assert card["metrics"]["judge_outputs_materialized_now"] is False
    assert card["metrics"]["row_bodies_read_now"] is False
    assert card["metrics"]["training_authorized"] is False
    assert validate_contract(card) == []


def test_stage9017_validation_rejects_execution_or_open_authority() -> None:
    unsafe = build_contract(registry())
    unsafe["metrics"]["row_sample_judge_executed_now"] = True
    assert "row_sample_judge_executed_now" in validate_contract(unsafe)
    opened = build_contract(registry())
    opened["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_contract(opened)
