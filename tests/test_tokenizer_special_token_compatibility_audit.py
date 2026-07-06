from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_stage8908_tokenizer_special_token_compatibility_audit import (
    AUTHORITY_CLOSED,
    EXPECTED_AK_SPECIALS,
    REQUIRED_V2_SPECIAL_GAPS,
    build_audit,
    validate_audit,
)


def test_core_special_ids_and_agentkernel_tokens_are_recovered() -> None:
    audit = build_audit()
    assert audit["checks"]["tokenizer_files_present"] is True
    assert audit["checks"]["core_special_ids_match"] is True
    assert audit["checks"]["ak_special_tokens_present"] is True
    assert audit["checks"]["ak_special_ids_contiguous"] is True
    tokens = {row["content"]: row["id"] for row in audit["special_tokens"]}
    for offset, token in enumerate(EXPECTED_AK_SPECIALS):
        assert tokens[token] == 8192 + offset


def test_vocab_mismatch_blocks_direct_tokenizer_swap() -> None:
    audit = build_audit()
    assert audit["checks"]["export_vocab_size"] == 8207
    assert audit["checks"]["recovered_target_vocab_size"] == 1506
    assert audit["checks"]["vocab_matches_recovered_target"] is False
    assert audit["checks"]["safe_to_swap_tokenizer_without_resize"] is False
    assert "export_vocab_8207_does_not_match_recovered_target_1506" in audit["blockers"]


def test_v2_maintenance_special_tokens_are_recorded_as_future_migration() -> None:
    audit = build_audit()
    assert set(REQUIRED_V2_SPECIAL_GAPS).issubset(set(audit["v2_special_token_gaps"]))
    assert audit["decision"]["recommended_v2_policy"].startswith("Do not add missing V2 maintenance tokens ad hoc")


def test_validation_keeps_authority_closed() -> None:
    registry = {"metrics": {"latest_stage": 8907, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}
    assert validate_audit(build_audit(), registry) == []
    registry["metrics"]["authority_counts"]["decoder_ce_training_authorized_next"] = 1
    assert "registry_authority_counts_nonzero" in validate_audit(build_audit(), registry)
