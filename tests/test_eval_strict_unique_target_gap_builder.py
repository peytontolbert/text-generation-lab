from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.eval_strict_unique_target_gap_builder import build_card, build_gap_rows


def row(split: str, route: str = "CE_BLOCK_SPLIT_DUPLICATE_TARGET_HASH") -> dict:
    return {
        "row_id": f"r_{split}",
        "split": split,
        "route": route,
        "corrupted_state": {"language": "python", "file_extension": "py", "argument_signal": "literal_argument_visible"},
        "clean_state": {"bounded_argument_type": "ARG_LITERAL"},
        "selection_status": {"target_hash": "same_hash", "selected_by_split_dedup": False},
    }


def test_gap_rows_only_eval_and_strict_duplicate_hash_blocks() -> None:
    rows = build_gap_rows([row("train"), row("eval"), row("strict"), row("eval", "CE_BLOCK_NOT_MATERIALIZED_OR_NONDECODE_ROUTE")])
    assert [r["split"] for r in rows] == ["eval", "strict"]
    assert all(r["clean_state"]["decoder_ce_eligible_now"] is False for r in rows)
    assert all(not any(r["loss_mask"].values()) for r in rows)


def test_card_closed_authority_and_no_target_visibility() -> None:
    rows = build_gap_rows([row("eval"), row("strict")])
    card = build_card(rows)
    assert card["rows"] == 2
    assert card["authority_rows"] == 0
    assert card["loss_rows"] == 0
    assert card["decoder_ce_eligible_now_rows"] == 0
    assert card["raw_or_target_visible_rows"] == 0
    assert card["complete_gate_status_rows"] == 2
