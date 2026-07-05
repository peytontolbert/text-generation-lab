from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.learning_signal_contract_builder import (
    COUNTERFACTUAL_OBLIGATIONS,
    REQUIRED_TELEMETRY,
    STRUCTURED_TARGET_FIELDS,
    build_card,
    build_learning_signal_rows,
)


def test_learning_signal_contract_covers_structured_fields_and_telemetry() -> None:
    rows = build_learning_signal_rows()
    assert {row["target_field"] for row in rows} == set(STRUCTURED_TARGET_FIELDS)
    for row in rows:
        contract = row["contract"]
        assert set(COUNTERFACTUAL_OBLIGATIONS).issubset(contract["counterfactual_obligations"])
        assert set(REQUIRED_TELEMETRY).issubset(contract["required_telemetry"])
        assert not any(row["authority"].values())
        assert not any(row["loss_mask"].values())


def test_learning_signal_card_is_closed_and_complete() -> None:
    card = build_card(build_learning_signal_rows())
    assert card["passed"] is True
    assert card["authority_open_rows"] == 0
    assert card["loss_open_rows"] == 0
    assert card["opening_rows"] == 0
