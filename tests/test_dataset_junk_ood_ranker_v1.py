from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from dataset_junk_ood_ranker_v1 import rank_row_v1, rank_rows_v1


def test_ranker_holds_long_decoder_output() -> None:
    row = {"row_id": "r1", "decoder_text": "<html>" + ("x " * 900), "decode_allowed": False, "decoder_budget_ok": False}
    ranked = rank_row_v1(row, max_decoder_tokens=100)
    assert ranked["route"] == "HOLD_LONG_OUTPUT"
    assert ranked["loss_mask"]["decoder_ce"] is False
    assert ranked["eligibility"]["holdout_only"] is True


def test_ranker_routes_internal_decoder_tokens_to_denoise() -> None:
    row = {"row_id": "r2", "decoder_text": "<MNSB1> POLICY_CONTINUE", "decode_allowed": True, "decoder_budget_ok": True}
    ranked = rank_row_v1(row)
    assert ranked["route"] == "USE_FOR_DENOISE_REPAIR"
    assert ranked["loss_mask"]["denoise_ce"] is True
    assert ranked["loss_mask"]["decoder_ce"] is False


def test_ranker_quarantines_locked_eval_source() -> None:
    row = {
        "row_id": "r3",
        "clean_state": {"x": "y"},
        "source_lineage": {"graph_nodes_source_id": "locked_a"},
    }
    ranked = rank_row_v1(row, locked_source_ids={"locked_a"})
    assert ranked["route"] == "QUARANTINE_AUTHORITY_OR_LOCKED"
    assert ranked["eligibility"]["train_eligible"] is False
    assert ranked["eligibility"]["locked_eval_source"] is True


def test_ranker_quarantines_target_copy_leakage() -> None:
    row = {
        "row_id": "r4",
        "encoder_text": "prefix EXACT_TARGET_PAYLOAD suffix",
        "target_text": "EXACT_TARGET_PAYLOAD",
    }
    ranked = rank_row_v1(row)
    assert ranked["route"] == "QUARANTINE_LABEL_CONFLICT"
    assert "target_text_copied_in_encoder" in ranked["reasons"]


def test_ranker_keeps_structured_default_closed_authority() -> None:
    ranked = rank_row_v1({"row_id": "r5", "objective_family": "symbol_binding", "clean_state": {"action": "RETRIEVE_MORE"}})
    assert ranked["route"] == "KEEP_STRUCTURED"
    assert ranked["loss_mask"]["symbol_binding_ce"] is True
    assert ranked["authority"]["model_execution_authorized_next"] is False


def test_rank_rows_counts_routes_and_losses() -> None:
    card = rank_rows_v1(
        [
            {"row_id": "a", "clean_state": {"action": "RETRIEVE_MORE"}},
            {"row_id": "b", "decoder_text": "<PYPLAN> leak", "decode_allowed": True, "decoder_budget_ok": True},
        ]
    )
    assert card["rows"] == 2
    assert card["route_counts"]["KEEP_STRUCTURED"] == 1
    assert card["route_counts"]["USE_FOR_DENOISE_REPAIR"] == 1
    assert card["loss_counts"]["denoise_ce"] == 1
