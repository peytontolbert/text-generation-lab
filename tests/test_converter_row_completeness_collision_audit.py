from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_stage8917_converter_row_completeness_collision_audit import (  # noqa: E402
    AUTHORITY_CLOSED,
    build_audit,
    classify,
    load_rows,
    validate_audit,
)


def test_converter_rows_are_complete_and_collision_free() -> None:
    audit = build_audit()
    assert audit["checks"]["expected_shape_row_count"] is True
    assert audit["checks"]["expected_dense_row_count"] is True
    assert audit["checks"]["expected_packed_row_count"] is True
    assert audit["checks"]["expected_new_init_row_count"] is True
    assert audit["checks"]["no_target_key_collisions"] is True
    assert audit["checks"]["no_source_artifact_collisions"] is True
    assert audit["checks"]["no_source_key_collisions"] is True


def test_converter_rows_keep_blocked_items_explicit() -> None:
    metrics = classify(load_rows())
    assert metrics["unknown_dense_rows"] == 0
    assert metrics["blocked_dense_artifacts"] == ["dense/enc_pos_embed_weight.f32.bin"]
    assert metrics["packed_status_blocked_rows"] == 109
    assert metrics["embedding_migration_rows"] == 2


def test_converter_audit_does_not_open_execution_or_read_binary_values() -> None:
    audit = build_audit()
    assert audit["checks"]["no_binary_tensor_values_read"] is True
    assert audit["checks"]["direct_load_allowed"] is False
    assert all(value is False for value in audit["authority"].values())


def test_validation_rejects_collision_or_authority_drift() -> None:
    registry = {"metrics": {"latest_stage": 8916, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}
    assert validate_audit(build_audit(), registry) == []
    audit = build_audit()
    audit["checks"]["no_target_key_collisions"] = False
    assert "no_target_key_collisions" in validate_audit(audit, registry)
    registry["metrics"]["authority_counts"]["runtime_authorized"] = 1
    assert "registry_authority_counts_nonzero" in validate_audit(build_audit(), registry)
