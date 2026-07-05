from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from contamination_leakage_detector import detect_card, detect_row


def clean_row() -> dict:
    return {
        "row_id": "row_001",
        "split": "train",
        "semantic_key": "sem_clean_001",
        "source_id": "src_clean_001",
        "input_state": {
            "user_intent": "repair a parser edge case",
            "evidence_state": "direct_present",
            "visible_feature": "parser_has_escape_sequence_branch",
        },
        "target": {"action": "PATCH_OPERATOR"},
    }


def test_clean_row_passes_with_authority_closed() -> None:
    decision = detect_row(clean_row())
    assert decision["route"] == "PASS_NO_CONTAMINATION"
    assert decision["target_leak_flag"] is False
    assert decision["authority"]["decoder_ce_training_authorized_next"] is False


def test_visible_target_like_key_blocks_target_leak() -> None:
    row = clean_row()
    row["input_state"]["expected_answer"] = "PATCH_OPERATOR"
    decision = detect_row(row)
    assert decision["route"] == "BLOCK_TARGET_LEAK"
    assert decision["target_leak_flag"] is True
    assert any(reason.startswith("visible_target_like_key") for reason in decision["reasons"])


def test_target_text_copied_in_visible_input_blocks_target_leak() -> None:
    row = clean_row()
    row["target_text"] = "The repair is to update parse_escape_literal safely."
    row["encoder_text"] = "Known target: The repair is to update parse_escape_literal safely."
    decision = detect_row(row)
    assert decision["route"] == "BLOCK_TARGET_LEAK"
    assert "target_text_copied_in_visible_input" in decision["reasons"]


def test_label_coded_ids_are_blocked() -> None:
    row = clean_row()
    row["row_id"] = "row_REPAIR_SHORT_OUTPUT_001"
    decision = detect_row(row)
    assert decision["route"] == "BLOCK_LABEL_CODED_ID"
    assert decision["label_coded_id"] is True


def test_body_or_source_leak_is_blocked_before_other_routes() -> None:
    row = clean_row()
    row["input_state"]["raw_source"] = "def hidden_target(): pass"
    decision = detect_row(row)
    assert decision["route"] == "BLOCK_BODY_OR_SOURCE_LEAK"
    assert decision["body_leak_flag"] is True


def test_locked_eval_overlap_is_blocked() -> None:
    row = clean_row()
    row["source_id"] = "locked_src_001"
    decision = detect_row(row, locked_eval_ids={"locked_src_001"})
    assert decision["route"] == "BLOCK_HELDOUT_OVERLAP"
    assert decision["heldout_overlap"] is True


def test_suspicious_proxy_routes_review_not_training() -> None:
    row = clean_row()
    row["suspicious_proxy_feature"] = True
    decision = detect_row(row)
    assert decision["route"] == "REVIEW_SUSPICIOUS_PROXY"
    assert decision["authority"]["training_authorized_next"] is False


def test_detect_card_reports_split_overlap() -> None:
    train = clean_row()
    strict = clean_row()
    strict["row_id"] = "row_002"
    strict["split"] = "strict_eval"
    card = detect_card([train, strict])
    assert card["rows"] == 2
    assert card["split_overlap_rows"] == 1
    assert card["route_counts"]["REVIEW_SPLIT_OVERLAP"] == 1


def test_detect_card_counts_block_and_review_routes() -> None:
    target_leak = clean_row()
    target_leak["row_id"] = "row_002"
    target_leak["input_state"]["target"] = "COPY_ME"
    proxy = clean_row()
    proxy["row_id"] = "row_003"
    proxy["semantic_key"] = "sem_proxy_003"
    proxy["shortcut_dominated_feature"] = True
    card = detect_card([clean_row(), target_leak, proxy])
    assert card["pass_rows"] == 1
    assert card["blocked_rows"] == 1
    assert card["review_rows"] == 1
    assert card["target_leak_rows"] == 1
