from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from source_provenance_license_security_filter import filter_card, filter_source


def base_row() -> dict:
    return {
        "source_id": "src_ok",
        "lineage_hash": "abc",
        "license_status": "license_file_present",
        "security_policy_present": True,
        "allowed_import_source": True,
        "split": "train",
    }


def test_clean_train_source_is_allowed_for_structured_only() -> None:
    decision = filter_source(base_row())
    assert decision["route"] == "ALLOW_SOURCE_FOR_STRUCTURED"
    assert decision["train_allowed"] is True
    assert decision["decoder_ce_authorized"] is False
    assert decision["runtime_authorized"] is False


def test_missing_lineage_blocks_source() -> None:
    row = base_row()
    row["lineage_hash"] = ""
    decision = filter_source(row)
    assert decision["route"] == "BLOCK_MISSING_LINEAGE"
    assert "missing_lineage" in decision["reasons"]


def test_secret_or_pii_blocks_source() -> None:
    row = base_row()
    row["content_preview"] = "password = 'abc'"
    decision = filter_source(row)
    assert decision["route"] == "BLOCK_SECRET_OR_PII"
    assert decision["secret_or_pii"] is True


def test_locked_eval_train_request_blocks_source() -> None:
    row = base_row()
    row["split_eligibility"] = {"locked_eval": True}
    row["requested_split"] = "train"
    decision = filter_source(row)
    assert decision["route"] == "BLOCK_LOCKED_EVAL_TRAIN"


def test_unknown_license_routes_review() -> None:
    row = base_row()
    row["license_status"] = "unknown"
    decision = filter_source(row)
    assert decision["route"] == "HOLD_LICENSE_REVIEW"


def test_missing_security_policy_routes_review() -> None:
    row = base_row()
    row["security_policy_present"] = False
    decision = filter_source(row)
    assert decision["route"] == "HOLD_SECURITY_REVIEW"


def test_disallowed_import_source_blocks_when_import_required() -> None:
    row = base_row()
    row["allowed_import_source"] = False
    row["requires_import"] = True
    decision = filter_source(row)
    assert decision["route"] == "BLOCK_DISALLOWED_IMPORT_SOURCE"


def test_filter_card_counts_routes_and_keeps_authority_closed() -> None:
    rows = [base_row(), {**base_row(), "source_id": "src_secret", "content_preview": "token=abc"}]
    card = filter_card(rows)
    assert card["rows"] == 2
    assert card["train_allowed_rows"] == 1
    assert card["blocked_rows"] == 1
    assert card["unsafe_decisions"] == 0
    assert card["authority"]["training_authorized_next"] is False
