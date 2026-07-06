from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_stage8919_tokenizer_embedding_migration_policy_design import (  # noqa: E402
    AUTHORITY_CLOSED,
    SOURCE_VOCAB,
    TARGET_VOCAB,
    VOCAB_DELTA,
    build_policy,
    validate_policy,
)


def test_policy_records_vocab_mismatch_and_safe_default() -> None:
    policy = build_policy()
    metrics = policy["metrics"]
    assert metrics["source_vocab_size"] == SOURCE_VOCAB
    assert metrics["recovered_target_vocab_size"] == TARGET_VOCAB
    assert metrics["vocab_delta"] == VOCAB_DELTA
    assert metrics["default_policy"] == "keep_recovered_target_tokenizer_1506_and_do_not_load_export_embeddings"


def test_policy_blocks_embedding_copy_resize_and_tokenizer_swap() -> None:
    policy = build_policy()
    checks = policy["checks"]
    assert checks["no_embedding_copy_authorized"] is True
    assert checks["no_lm_head_copy_authorized"] is True
    assert checks["no_embedding_resize_authorized"] is True
    assert checks["no_tokenizer_swap_authorized"] is True
    assert checks["no_state_dict_load_authorized"] is True
    assert all(value is False for value in policy["authority"].values())


def test_policy_keeps_v2_tokens_as_future_gaps() -> None:
    policy = build_policy()
    assert policy["checks"]["v2_tokens_are_future_gaps_not_current_edits"] is True
    assert "<AK_OBSERVE>" in policy["v2_special_token_gaps"]
    assert "<AK_VTR>" in policy["v2_special_token_gaps"]


def test_validation_rejects_authority_or_policy_drift() -> None:
    registry = {"metrics": {"latest_stage": 8918, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}
    assert validate_policy(build_policy(), registry) == []
    policy = build_policy()
    policy["checks"]["no_tokenizer_swap_authorized"] = False
    assert "no_tokenizer_swap_authorized" in validate_policy(policy, registry)
    registry["metrics"]["authority_counts"]["decoder_ce_training_authorized_next"] = 1
    assert "registry_authority_counts_nonzero" in validate_policy(build_policy(), registry)
