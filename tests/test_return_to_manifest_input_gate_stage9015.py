from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage9015_return_to_manifest_input_gate import (  # noqa: E402
    AUTHORITY_CLOSED,
    REQUIRED_MANIFEST_INPUTS,
    build_gate,
    validate_gate,
)


def registry() -> dict[str, object]:
    return {"metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}, "rows": []}


def test_stage9015_routes_to_manifest_inputs() -> None:
    card = build_gate(registry())
    assert card["active_next_surface"] == "stage9007_manifest_input_prerequisites"
    for item in ["row_sample_dataset_judge_report.json", "accepted_row_ids_pending_manifest_compile.jsonl", "judge_to_compiler_gate_status.json"]:
        assert item in REQUIRED_MANIFEST_INPUTS


def test_stage9015_keeps_everything_closed() -> None:
    card = build_gate(registry())
    assert card["metrics"]["duplicate_resolution_applied_now"] is False
    assert card["metrics"]["manifest_materialized_now"] is False
    assert card["metrics"]["trainer_dry_run_execution_authorized_now"] is False
    assert card["metrics"]["training_authorized"] is False
    assert validate_gate(card) == []


def test_stage9015_validation_rejects_open_authority_or_manifest_execution() -> None:
    unsafe = build_gate(registry())
    unsafe["metrics"]["manifest_materialized_now"] = True
    assert "manifest_materialized_now" in validate_gate(unsafe)
    opened = build_gate(registry())
    opened["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_gate(opened)
