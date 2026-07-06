from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8925_tokenizer_hash_lock_bridge_decision import (  # noqa: E402
    AUTHORITY_CLOSED,
    SOURCE_VOCAB,
    TARGET_VOCAB,
    VOCAB_DELTA,
    build_decision,
    validate_decision,
)


def registry() -> dict[str, object]:
    return {"metrics": {"latest_stage": 8924, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_hash_locks_source_tokenizer_and_target_config() -> None:
    decision = build_decision()
    locks = decision["file_locks"]
    assert locks["source_tokenizer_json"]["sha256"]
    assert locks["source_tokenizer_config"]["sha256"]
    assert locks["target_config"]["sha256"]
    assert decision["checks"]["source_tokenizer_json_hash_locked"] is True
    assert decision["checks"]["target_config_hash_locked"] is True


def test_decision_keeps_target_tokenizer_and_records_vocab_gap() -> None:
    decision = build_decision()
    metrics = decision["metrics"]
    assert metrics["source_vocab_size"] == SOURCE_VOCAB
    assert metrics["target_vocab_size"] == TARGET_VOCAB
    assert metrics["vocab_delta"] == VOCAB_DELTA
    assert decision["bridge_decision"]["active_tokenizer"] == "recovered_target_tokenizer_1506"
    assert decision["bridge_decision"]["source_export_tokenizer_status"] == "hash_locked_reference_only"
    assert decision["bridge_decision"]["bridge_mapping_status"] == "not_built"


def test_decision_authorizes_no_tokenizer_or_embedding_mutation() -> None:
    decision = build_decision()
    checks = decision["checks"]
    assert checks["no_tokenizer_swap_authorized"] is True
    assert checks["no_embedding_resize_authorized"] is True
    assert checks["no_embedding_copy_authorized"] is True
    assert checks["no_lm_head_copy_authorized"] is True
    assert checks["no_training_authorized"] is True
    assert checks["no_model_execution_authorized"] is True
    assert all(value is False for value in decision["authority"].values())


def test_validation_rejects_authority_or_bridge_drift() -> None:
    assert validate_decision(build_decision(), registry()) == []
    decision = build_decision()
    decision["checks"]["bridge_mapping_not_built"] = False
    assert "bridge_mapping_not_built" in validate_decision(decision, registry())
    bad_registry = registry()
    bad_registry["metrics"]["authority_counts"]["runtime_authorized"] = 1  # type: ignore[index]
    assert "registry_authority_counts_nonzero" in validate_decision(build_decision(), bad_registry)
