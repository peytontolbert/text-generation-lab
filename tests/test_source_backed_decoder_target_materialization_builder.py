from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from curriculum_compiler import REQUIRED_RECOVERED_GATE_REFERENCES
from source_backed_decoder_target_materialization_builder import build_card, build_materialization_controls


def ce_candidate(arg_type: str = "ARG_NAME") -> dict:
    return {
        "row_id": "stage8802_ce_gate_sample",
        "split": "train",
        "source_stage": "stage8802_from_bounded_decoder_argument_controls",
        "corrupted_state": {
            "language": "python",
            "file_extension": "py",
            "context_group": "add_import_plan",
            "argument_signal": "identifier_argument_visible",
            "bounded_argument_features": {"argument_evidence_visible": True},
            "budget": {"decoder_budget_ok": False, "max_arg_tokens": 16, "target_length_bucket": "tiny"},
        },
        "clean_state": {
            "bounded_argument_type": arg_type,
            "ce_gate_decision": "CE_CANDIDATE_NEEDS_SOURCE_BACKED_TARGET_TEXT",
            "decoder_ce_eligible_now": False,
        },
        "gate_status": {key: True for key in REQUIRED_RECOVERED_GATE_REFERENCES},
    }


def blocked_retrieve() -> dict:
    row = ce_candidate("RETRIEVE_MORE")
    row["clean_state"]["ce_gate_decision"] = "CE_BLOCK_RETRIEVE_MORE_BEFORE_DECODING"
    return row


def test_materializes_target_store_without_putting_text_in_manifest() -> None:
    manifest, target_store = build_materialization_controls([ce_candidate()])
    assert len(manifest) == 1
    assert len(target_store) == 1
    row = manifest[0]
    assert row["clean_state"]["decoder_target_text_materialized"] is True
    assert row["clean_state"]["decoder_ce_eligible_now"] is False
    assert not any(row["loss_mask"].values())
    assert not any(row["authority"].values())
    assert row["anti_cheat"]["target_text_in_manifest"] is False
    target_text = target_store[0]["decoder_text"]
    assert target_text
    assert target_text not in str(row)
    assert row["clean_state"]["decoder_target_text_sha256"] == target_store[0]["decoder_text_sha256"]


def test_blocked_rows_do_not_get_target_store_entries() -> None:
    manifest, target_store = build_materialization_controls([ce_candidate(), blocked_retrieve()])
    assert len(manifest) == 2
    assert len(target_store) == 1
    blocked = [row for row in manifest if row["route"] == "TARGET_MATERIALIZATION_BLOCKED"]
    assert len(blocked) == 1
    assert blocked[0]["clean_state"]["decoder_target_ref"] is None
    assert blocked[0]["clean_state"]["decoder_target_text_materialized"] is False


def test_card_counts_materialized_rows_and_closed_authority() -> None:
    manifest, target_store = build_materialization_controls([ce_candidate("ARG_CALL"), blocked_retrieve()])
    card = build_card(manifest, target_store)
    assert card["rows"] == 2
    assert card["target_store_rows"] == 1
    assert card["materialized_rows"] == 1
    assert card["blocked_rows"] == 1
    assert card["authority_rows"] == 0
    assert card["target_store_authority_rows"] == 0
    assert card["training_loss_rows"] == 0
    assert card["decoder_ce_eligible_now_rows"] == 0
    assert card["target_text_copied_to_manifest_rows"] == 0
    assert card["over_cap_target_store_rows"] == 0
    assert card["internal_token_target_store_rows"] == 0
