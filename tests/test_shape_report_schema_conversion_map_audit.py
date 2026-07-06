from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_stage8912_shape_report_schema_conversion_map_audit import (
    AUTHORITY_CLOSED,
    SHAPE_REPORT_SCHEMA,
    build_audit,
    validate_audit,
)


def test_shape_report_schema_has_required_safety_fields() -> None:
    required = set(SHAPE_REPORT_SCHEMA["required_fields"])
    for key in ["source_key", "target_key", "source_shape", "target_shape", "action", "status", "provenance"]:
        assert key in required
    assert "state_dict_load" in SHAPE_REPORT_SCHEMA["forbidden_in_this_stage"]
    assert "read_binary_tensor_values" in SHAPE_REPORT_SCHEMA["forbidden_in_this_stage"]


def test_conversion_map_records_embedding_migration_and_new_heads() -> None:
    audit = build_audit()
    rows = audit["conversion_rows"]
    enc_embed = next(row for row in rows if row["target_key"] == "enc_embed.weight")
    assert enc_embed["source_shape"] == [8207, 640]
    assert enc_embed["target_shape"] == [1506, 640]
    assert enc_embed["status"] == "needs_migration"
    assert any(row["target_key"] == "retrieval_query_head.weight" and row["status"] == "new_init_required" for row in rows)
    assert any(row["target_key"] == "structured_heads.*.weight/bias" and row["status"] == "new_init_required" for row in rows)


def test_metadata_shape_inference_does_not_allow_direct_load() -> None:
    audit = build_audit()
    assert audit["checks"]["embedding_file_sizes_match_export_vocab"] is True
    assert audit["checks"]["binary_tensor_values_read"] is False
    assert audit["checks"]["direct_load_allowed"] is False
    assert audit["checks"]["blocked_rows"] >= 2


def test_validation_rejects_direct_load_or_binary_value_read() -> None:
    registry = {"metrics": {"latest_stage": 8911, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}
    assert validate_audit(build_audit(), registry) == []
    audit = build_audit()
    audit["checks"]["direct_load_allowed"] = True
    assert "direct_load_was_incorrectly_allowed" in validate_audit(audit, registry)
    audit = build_audit()
    audit["checks"]["binary_tensor_values_read"] = True
    assert "binary_tensor_values_were_read" in validate_audit(audit, registry)
