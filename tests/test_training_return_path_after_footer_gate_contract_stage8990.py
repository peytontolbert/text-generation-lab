from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8990_training_return_path_after_footer_gate_contract import (  # noqa: E402
    AUTHORITY_CLOSED,
    NON_NEGOTIABLE_CONTROLS,
    RETURN_PATH_GATES,
    build_contract,
    validate_contract,
)


def registry() -> dict[str, object]:
    return {"metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage8990_records_ordered_return_path_to_training() -> None:
    card = build_contract(registry())
    gate_ids = [gate["gate_id"] for gate in RETURN_PATH_GATES]
    assert "active_parquet_footer_ticket_instance" in gate_ids
    assert "row_sample_dataset_judge" in gate_ids
    assert gate_ids[-1] == "one_run_bounded_training_ticket"
    assert card["metrics"]["return_path_gates"] >= 8


def test_stage8990_only_final_gate_can_authorize_training() -> None:
    training_gates = [gate for gate in RETURN_PATH_GATES if gate["authorizes_training"]]
    assert len(training_gates) == 1
    assert training_gates[0]["gate_id"] == "one_run_bounded_training_ticket"
    assert "locked_eval_never_train" in NON_NEGOTIABLE_CONTROLS
    assert "contamination_leakage_detector_pass" in NON_NEGOTIABLE_CONTROLS


def test_stage8990_keeps_all_execution_and_training_closed() -> None:
    card = build_contract(registry())
    assert validate_contract(card) == []
    assert card["metrics"]["footer_access_authorized_now"] is False
    assert card["metrics"]["dataset_rows_loaded"] is False
    assert card["metrics"]["training_authorized"] is False
    assert card["metrics"]["model_execution_attempted"] is False
    assert all(value is False for value in card["authority"].values())


def test_stage8990_validation_rejects_open_authority_or_training_flag() -> None:
    card = build_contract(registry())
    bad = build_contract(registry())
    bad["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_contract(bad)
    train = build_contract(registry())
    train["metrics"]["training_authorized"] = True
    assert "training_authorized" in validate_contract(train)
