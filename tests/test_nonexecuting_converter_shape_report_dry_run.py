from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_stage8916_nonexecuting_converter_shape_report_dry_run import (
    AUTHORITY_CLOSED,
    build_audit,
    validate_audit,
)


def test_dry_run_emits_dense_packed_and_new_init_rows() -> None:
    audit = build_audit()
    checks = audit["checks"]
    assert checks["dense_rows"] >= 43
    assert checks["packed_manifest_rows"] >= 109
    assert checks["new_init_rows"] >= 7
    assert checks["converter_emits_full_metadata_rows"] is True


def test_dry_run_never_reads_binary_values_or_allows_direct_load() -> None:
    audit = build_audit()
    assert audit["checks"]["binary_tensor_values_read"] is False
    assert audit["checks"]["direct_load_allowed"] is False
    assert all(row["binary_tensor_values_read"] is False for row in audit["shape_rows"])


def test_embedding_and_control_head_rows_are_present() -> None:
    audit = build_audit()
    rows = audit["shape_rows"]
    enc = next(row for row in rows if row["target_key"] == "enc_embed.weight")
    assert enc["source_shape"] == [8207, 640]
    assert enc["target_shape"] == [1506, 640]
    assert enc["status"] == "needs_migration"
    assert any(row["target_key"] == "retrieval_query_head.weight" and row["status"] == "new_init_required" for row in rows)
    assert any(row["target_key"] == "structured_heads.*.weight/bias" and row["status"] == "new_init_required" for row in rows)


def test_validation_rejects_direct_load_or_binary_value_read() -> None:
    registry = {"metrics": {"latest_stage": 8915, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}
    assert validate_audit(build_audit(), registry) == []
    audit = build_audit()
    audit["checks"]["direct_load_allowed"] = True
    assert "direct_load_was_incorrectly_allowed" in validate_audit(audit, registry)
    audit = build_audit()
    audit["checks"]["binary_tensor_values_read"] = True
    assert "binary_tensor_values_were_read" in validate_audit(audit, registry)
