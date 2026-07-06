from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8980_zero_row_runner_contract_audit import (  # noqa: E402
    AUTHORITY_CLOSED,
    FUTURE_TICKET_FORBIDDEN,
    REQUIRED_DRY_ROW_FIELDS,
    build_future_ticket_schema,
    count_routes,
    missing_fields,
    validate_audit,
)


def registry(latest: int = 8979) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def base_card() -> dict[str, object]:
    return {
        "checks": {"ok": True},
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "field_failure_rows": 0,
            "probe_executed_rows": 0,
            "arxiv_file_opened_rows": 0,
            "dataset_rows_loaded_rows": 0,
            "repository_source_body_read_rows": 0,
            "candidate_file_opened": False,
            "schema_or_header_read_performed": False,
            "dataset_rows_loaded": False,
            "repository_source_bodies_loaded": False,
            "arxiv_write_authorized": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "model_execution_attempted": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "network_upload_performed": False,
        },
    }


def test_stage8980_missing_fields_detects_incomplete_dry_row() -> None:
    assert "candidate_id" in missing_fields({})
    full = {field: None for field in REQUIRED_DRY_ROW_FIELDS}
    assert missing_fields(full) == []


def test_stage8980_route_counter_counts_routes() -> None:
    assert count_routes([{"route": "A"}, {"route": "A"}, {"route": "B"}]) == {"A": 2, "B": 1}


def test_stage8980_future_ticket_schema_forbids_rows_source_training() -> None:
    schema = build_future_ticket_schema()
    assert "PARQUET_FOOTER_SCHEMA_METADATA_ONLY" in schema["allowed_probe_types"]
    for item in ["DATASET_ROW_SCAN", "REPOSITORY_SOURCE_BODY_READ", "TRAINING", "MINING", "MODEL_EXECUTION"]:
        assert item in FUTURE_TICKET_FORBIDDEN
        assert item in schema["forbidden_operations"]


def test_stage8980_validation_rejects_probe_or_file_open_or_bad_frontier() -> None:
    assert validate_audit(base_card(), registry()) == []
    bad = base_card()
    bad["metrics"] = {**bad["metrics"], "probe_executed_rows": 1}
    assert "probe_executed_rows" in validate_audit(bad, registry())
    opened = base_card()
    opened["metrics"] = {**opened["metrics"], "candidate_file_opened": True}
    assert "candidate_file_opened" in validate_audit(opened, registry())
    assert "unexpected_registry_frontier:9999" in validate_audit(base_card(), registry(9999))
