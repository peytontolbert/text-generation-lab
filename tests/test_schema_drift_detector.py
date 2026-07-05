from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from schema_drift_detector import audit_row, audit_rows, normalize_row_keys


def schema() -> dict:
    return {
        "required_fields": ["row_id", "split", "gate_status"],
        "optional_fields": ["source_id", "objective_family"],
        "forbidden_fields": ["clean_state", "target_label", "raw_source_body"],
        "typed_fields": {"row_id": "str", "split": "str", "gate_status": "dict"},
        "aliases": {"package_split": "split", "gateStatus": "gate_status"},
        "allow_unknown_fields": False,
    }


def test_normalize_row_keys_tracks_aliases() -> None:
    row, used = normalize_row_keys({"package_split": "train", "gateStatus": {}}, {"package_split": "split", "gateStatus": "gate_status"})
    assert row["split"] == "train"
    assert row["gate_status"] == {}
    assert used == {"package_split": "split", "gateStatus": "gate_status"}


def test_passes_stable_schema() -> None:
    record = audit_row({"row_id": "r1", "split": "train", "gate_status": {}, "source_id": "s"}, schema())
    assert record["schema_drift_route"] == "PASS_SCHEMA_STABLE"


def test_holds_missing_required_for_review() -> None:
    record = audit_row({"row_id": "r1", "split": "train"}, schema())
    assert record["schema_drift_route"] == "HOLD_SCHEMA_REVIEW"
    assert "gate_status" in record["missing_required_fields"]


def test_blocks_forbidden_target_fields() -> None:
    record = audit_row({"row_id": "r1", "split": "train", "gate_status": {}, "target_label": "COPY_PRIOR"}, schema())
    assert record["schema_drift_route"] == "BLOCK_SCHEMA_DRIFT"
    assert "target_label" in record["forbidden_fields_present"]


def test_blocks_type_mismatch() -> None:
    record = audit_row({"row_id": "r1", "split": "train", "gate_status": []}, schema())
    assert record["schema_drift_route"] == "BLOCK_SCHEMA_DRIFT"
    assert record["type_mismatches"][0]["field"] == "gate_status"


def test_blocks_alias_collision() -> None:
    record = audit_row({"row_id": "r1", "split": "train", "package_split": "eval", "gate_status": {}}, schema())
    assert record["schema_drift_route"] == "BLOCK_SCHEMA_DRIFT"
    assert record["alias_collisions"]


def test_manifest_counts_routes() -> None:
    card = audit_rows([
        {"row_id": "ok", "split": "train", "gate_status": {}},
        {"row_id": "review", "split": "train"},
        {"row_id": "block", "split": "train", "gate_status": {}, "raw_source_body": "def x(): pass"},
    ], schema())
    assert card["metrics"]["pass_rows"] == 1
    assert card["metrics"]["review_rows"] == 1
    assert card["metrics"]["blocked_rows"] == 1
