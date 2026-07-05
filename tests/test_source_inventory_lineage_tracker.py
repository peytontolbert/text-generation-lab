from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from source_inventory_lineage_tracker import audit_lineage_cards, build_lineage_card, lineage_manifest


def test_train_source_gets_stable_ids_and_train_eligibility() -> None:
    card = build_lineage_card({
        "source_uri": "/arxiv/repositories/example/file.py",
        "content": "def f(): pass",
        "split": "train",
        "license_status": "license_file_present",
        "security_policy_present": True,
    })
    assert card["source_id"].startswith("src_")
    assert len(card["lineage_hash"]) == 64
    assert card["split_eligibility"]["train"] is True
    assert card["authority"]["training_authorized_next"] is False


def test_locked_eval_never_train_eligible() -> None:
    card = build_lineage_card({
        "source_uri": "/arxiv/datasets/locked/example.parquet",
        "content": "locked row",
        "split": "locked_eval",
        "locked_eval": True,
    })
    assert card["split_eligibility"]["locked_eval"] is True
    assert card["split_eligibility"]["train"] is False
    assert "locked_eval_source" in card["blocked_reasons"]


def test_unknown_license_blocks_train_until_reviewed() -> None:
    card = build_lineage_card({
        "source_uri": "/arxiv/repositories/unknown/file.py",
        "content": "x = 1",
        "split": "train",
        "license_status": "unknown",
        "security_policy_present": True,
    })
    assert card["split_eligibility"]["train"] is False
    assert "unknown_license_without_review" in card["blocked_reasons"]


def test_missing_security_policy_blocks_train_external_code() -> None:
    card = build_lineage_card({
        "source_uri": "/arxiv/repositories/no-security/file.py",
        "content": "x = 1",
        "split": "train",
        "license_status": "license_file_present",
        "security_policy_present": False,
    })
    assert card["split_eligibility"]["train"] is False
    assert "security_policy_missing_for_external_code" in card["blocked_reasons"]


def test_audit_rejects_duplicate_lineage_hashes() -> None:
    row = {"source_uri": "/arxiv/repositories/example/file.py", "content": "x = 1", "split": "train", "license_status": "license_file_present", "security_policy_present": True}
    cards = [build_lineage_card(row), build_lineage_card(row)]
    audit = audit_lineage_cards(cards)
    assert audit["passed"] is False
    assert audit["duplicate_lineage_hashes"]


def test_manifest_counts_locked_and_train_sources() -> None:
    manifest = lineage_manifest([
        {"source_uri": "/arxiv/repositories/example/file.py", "content": "def f(): pass", "split": "train", "license_status": "license_file_present", "security_policy_present": True},
        {"source_uri": "/arxiv/datasets/locked/example.parquet", "content": "locked", "split": "locked_eval", "locked_eval": True},
    ])
    audit = manifest["audit"]
    assert audit["train_eligible_rows"] == 1
    assert audit["locked_eval_rows"] == 1
    assert audit["passed"] is True
