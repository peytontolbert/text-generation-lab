from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_stage8918_converter_key_mapping_init_policy_contract import (  # noqa: E402
    AUTHORITY_CLOSED,
    build_contract,
    summarize,
    validate_contract,
)


def test_contract_classifies_all_converter_rows() -> None:
    contract = build_contract()
    checks = contract["checks"]
    assert checks["expected_compatible_mapping_rows"] is True
    assert checks["expected_embedding_migration_policy_rows"] is True
    assert checks["expected_new_init_policy_rows"] is True
    assert checks["expected_blocked_policy_rows"] is True
    assert checks["no_unknown_policy_rows"] is True


def test_contract_preserves_no_execution_boundary() -> None:
    contract = build_contract()
    assert contract["checks"]["no_binary_tensor_values_read"] is True
    assert contract["checks"]["no_load_authorized_rows"] is True
    assert contract["checks"]["no_execution_authorized_rows"] is True
    assert contract["checks"]["no_training_authorized_rows"] is True
    assert all(value is False for value in contract["authority"].values())


def test_contract_has_expected_policy_targets() -> None:
    metrics = summarize(build_contract()["contract_rows"])
    assert metrics["embedding_targets"] == ["dec_embed.weight", "enc_embed.weight"]
    assert "retrieval_query_head.weight" in metrics["new_init_targets"]
    assert "structured_heads.*.weight/bias" in metrics["new_init_targets"]
    assert metrics["target_key_collision_count"] == 0


def test_validation_rejects_policy_or_authority_drift() -> None:
    registry = {"metrics": {"latest_stage": 8917, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}
    assert validate_contract(build_contract(), registry) == []
    contract = build_contract()
    contract["checks"]["no_load_authorized_rows"] = False
    assert "no_load_authorized_rows" in validate_contract(contract, registry)
    registry["metrics"]["authority_counts"]["model_execution_authorized_next"] = 1
    assert "registry_authority_counts_nonzero" in validate_contract(build_contract(), registry)
