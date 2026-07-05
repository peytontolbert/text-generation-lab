from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from curriculum_compiler import REQUIRED_RECOVERED_GATE_REFERENCES
from bounded_decoder_argument_controls_builder import build_bounded_decoder_argument_controls, build_card


def sample_row() -> dict:
    return {
        "row_id": "old_ARG_IMPORT_row",
        "split": "train",
        "corrupted_state": {
            "language": "python",
            "file_extension": "py",
            "argument_signal": "approved_import_argument_visible",
            "bounded_argument_features": {
                "approved_import_policy_visible": True,
                "argument_evidence_visible": True,
                "over_budget_signal": False,
                "path_context_visible": True,
                "small_argument_required": True,
                "symbol_context_visible": True,
            },
            "budget": {"decoder_budget_ok": False, "max_arg_tokens": 16, "target_length_bucket": "tiny"},
        },
        "clean_state": {
            "bounded_argument_type": "ARG_IMPORT",
            "action_sequence": ["PACKAGE_IMPORT_ARG"],
            "file_plan": "package arg_import",
        },
    }


def test_wraps_bounded_decoder_argument_with_complete_gates_and_closed_losses() -> None:
    rows = build_bounded_decoder_argument_controls([sample_row()])
    assert len(rows) == 1
    row = rows[0]
    assert set(row["gate_status"]) == set(REQUIRED_RECOVERED_GATE_REFERENCES)
    assert all(row["gate_status"].values())
    assert not any(row["loss_mask"].values())
    assert row["authority"]["decoder_ce_training_authorized_next"] is False
    assert row["anti_cheat"]["raw_decoder_text_included"] is False


def test_row_id_and_semantic_key_do_not_expose_target_label() -> None:
    row = build_bounded_decoder_argument_controls([sample_row()])[0]
    assert "ARG_IMPORT" not in row["row_id"]
    assert "ARG_IMPORT" not in row["semantic_key"]
    assert row["clean_state"]["bounded_argument_type"] == "ARG_IMPORT"
    assert "bounded_argument_type" not in row["corrupted_state"]


def test_card_counts_no_authority_or_training_rows() -> None:
    rows = build_bounded_decoder_argument_controls([sample_row(), {**sample_row(), "row_id": "second", "split": "eval"}])
    card = build_card(rows)
    assert card["rows"] == 2
    assert card["labels"]["ARG_IMPORT"] == 2
    assert card["authority_rows"] == 0
    assert card["training_loss_rows"] == 0
    assert card["raw_source_rows"] == 0
    assert card["raw_decoder_text_rows"] == 0
