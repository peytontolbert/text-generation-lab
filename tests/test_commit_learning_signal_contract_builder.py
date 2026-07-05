import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.commit_learning_signal_contract_builder import (
    COMMIT_SIZE_BUCKETS,
    REQUIRED_FILTER_SIGNALS,
    TARGET_SURFACES,
    build_card,
    build_commit_learning_signal_rows,
)


def test_commit_learning_signal_contract_is_closed_and_complete() -> None:
    rows = build_commit_learning_signal_rows()
    card = build_card(rows)
    assert rows
    assert card["passed"] is True
    assert card["contract_ready_rows"] == len(rows)
    assert card["commit_mining_authorized"] is False
    assert card["arxiv_repository_walk_authorized"] is False
    assert card["training_authorized"] is False
    assert card["decoder_ce_authorized"] is False
    for row in rows:
        assert row["route"] == "CONTRACT_ONLY_NO_MINING"
        assert row["required_fields"]
        assert row["acceptance_checks"]
        assert set(TARGET_SURFACES).issubset(row["target_surfaces"])
        assert set(REQUIRED_FILTER_SIGNALS).issubset(row["required_filter_signals"])
        assert set(COMMIT_SIZE_BUCKETS).issubset(row["commit_size_buckets"])
        assert not any(row["authority"].values())
        assert not any(row["loss_mask"].values())
        assert not any(row["anti_cheat"].values())


def test_large_commits_block_raw_decoder_targets() -> None:
    rows = build_commit_learning_signal_rows()
    for row in rows:
        large_policy = row["commit_size_buckets"]["large"]
        assert "decompose_first" in large_policy["use"]
        assert "retrieval_context" in large_policy["use"]
    decoder_row = next(row for row in rows if row["contract_id"] == "bounded_decoder_target_gate")
    assert "large_commit_decoder_blocked" in decoder_row["acceptance_checks"]
    assert decoder_row["loss_mask"]["decoder_ce"] is False
