from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from split_deduped_closed_ce_candidate_selector import build_card, select_rows


def materialized(split: str, ref: str, h: str) -> dict:
    return {
        "row_id": f"stage8806_target_materialization_{split}_{ref}",
        "semantic_key": f"{split}:source_backed_target_materialization:{ref}",
        "split": split,
        "corrupted_state": {"language": "python"},
        "clean_state": {
            "bounded_argument_type": "ARG_NAME",
            "decoder_target_ref": ref,
            "decoder_target_text_sha256": h,
            "decoder_target_token_len": 32,
        },
        "materialization_status": {"source_backed_target_text_materialized": True, "hard_blockers": []},
        "gate_status": {"source_inventory_lineage": True},
    }


def test_selects_one_train_row_per_duplicate_hash() -> None:
    manifest = [materialized("eval", "eval_ref", "same_hash"), materialized("train", "train_ref", "same_hash")]
    store = [{"target_ref": "eval_ref", "decoder_text": "same text"}, {"target_ref": "train_ref", "decoder_text": "same text"}]
    rows = select_rows(manifest, store)
    selected = [row for row in rows if row["selection_status"]["selected_by_split_dedup"]]
    assert len(selected) == 1
    assert selected[0]["split"] == "train"
    assert selected[0]["clean_state"]["decoder_ce_eligible_now"] is False
    assert not any(selected[0]["loss_mask"].values())


def test_card_records_closed_candidate_counts_without_target_text_copy() -> None:
    manifest = [materialized("eval", "eval_ref", "same_hash"), materialized("train", "train_ref", "same_hash")]
    store = [{"target_ref": "eval_ref", "decoder_text": "same text"}, {"target_ref": "train_ref", "decoder_text": "same text"}]
    rows = select_rows(manifest, store)
    card = build_card(rows, store)
    assert card["rows"] == 2
    assert card["selected_candidate_rows"] == 1
    assert card["blocked_rows"] == 1
    assert card["training_loss_rows"] == 0
    assert card["authority_rows"] == 0
    assert card["decoder_ce_eligible_now_rows"] == 0
    assert card["selected_target_hash_unique_rows"] == 1
    assert card["target_text_copied_to_manifest_rows"] == 0
