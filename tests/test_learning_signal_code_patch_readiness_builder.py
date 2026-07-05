from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.learning_signal_contract_builder import build_learning_signal_rows
from scripts.learning_signal_implementation_plan_builder import build_plan_rows
from scripts.learning_signal_code_patch_readiness_builder import build_card, build_readiness_rows


def test_readiness_rows_are_closed_and_cover_plan() -> None:
    rows = build_readiness_rows(build_plan_rows(build_learning_signal_rows()))
    assert rows
    for row in rows:
        assert row["required_checks"]
        assert not row["plan_coverage"]["missing_plan_ids"]
        assert not row["plan_coverage"]["missing_files"]
        assert not any(row["authority"].values())
        assert not any(row["loss_mask"].values())


def test_readiness_card_does_not_authorize_code_or_training() -> None:
    card = build_card(build_readiness_rows(build_plan_rows(build_learning_signal_rows())))
    assert card["passed"] is True
    assert card["code_patch_authorized"] is False
    assert card["training_authorized"] is False
    assert card["decoder_ce_authorized"] is False
