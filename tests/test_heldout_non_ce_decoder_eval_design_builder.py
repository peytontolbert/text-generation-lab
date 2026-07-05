from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.heldout_non_ce_decoder_eval_design_builder import build_card, build_design_rows


def gap(split: str) -> dict:
    return {
        "row_id": f"g_{split}",
        "split": split,
        "source_row_ref": {"source_stage": "test"},
        "corrupted_state": {"language": "python", "file_extension": "py", "argument_signal": "literal", "bounded_argument_type": "ARG_LITERAL"},
    }


def test_design_rows_are_eval_strict_only_and_ce_closed() -> None:
    rows = build_design_rows([gap("train"), gap("eval"), gap("strict")])
    assert [r["split"] for r in rows] == ["eval", "strict"]
    assert all(r["clean_state"]["decoder_ce_eligible_now"] is False for r in rows)
    assert all(not any(r["loss_mask"].values()) for r in rows)
    assert all("decoder_target_text_ce" in r["clean_state"]["forbidden_eval_signals"] for r in rows)


def test_card_has_no_authority_or_forbidden_visibility() -> None:
    rows = build_design_rows([gap("eval"), gap("strict")])
    card = build_card(rows)
    assert card["rows"] == 2
    assert card["authority_rows"] == 0
    assert card["loss_rows"] == 0
    assert card["decoder_ce_eligible_now_rows"] == 0
    assert card["probe_ready_rows"] == 0
    assert card["raw_or_forbidden_visible_rows"] == 0
