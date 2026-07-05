from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.learning_signal_contract_builder import build_learning_signal_rows
from scripts.learning_signal_implementation_plan_builder import build_card, build_plan_rows


def test_plan_rows_have_file_changes_and_acceptance_checks() -> None:
    rows = build_plan_rows(build_learning_signal_rows())
    assert rows
    assert {row["route"] for row in rows} == {"IMPLEMENTATION_PLAN_ONLY"}
    for row in rows:
        assert row["planned_changes"]
        assert row["acceptance_checks"]
        assert not any(row["authority"].values())
        assert not any(row["loss_mask"].values())


def test_plan_card_is_closed_and_complete() -> None:
    card = build_card(build_plan_rows(build_learning_signal_rows()))
    assert card["passed"] is True
    assert card["implementation_plan_ready_rows"] == card["rows"]
    assert card["training_authorized"] is False
    assert card["decoder_ce_authorized"] is False
