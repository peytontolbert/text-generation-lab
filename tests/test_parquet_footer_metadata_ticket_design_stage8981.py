from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8981_parquet_footer_metadata_ticket_design import (  # noqa: E402
    ALLOWED_PROBE_TYPE,
    AUTHORITY_CLOSED,
    FORBIDDEN_OPERATIONS,
    REQUIRED_TICKET_FIELDS,
    build_ticket_schema,
    build_ticket_template,
    validate_design,
    validate_ticket_template,
)


def registry(latest: int = 8980) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def base_card() -> dict[str, object]:
    return {
        "checks": {"ok": True},
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "template_failures": 0,
            "ticket_active": False,
            "execution_authorized": False,
            "parquet_footer_access_performed": False,
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


def test_stage8981_ticket_schema_has_required_fields_and_probe_type() -> None:
    schema = build_ticket_schema()
    assert schema["allowed_probe_type"] == ALLOWED_PROBE_TYPE
    for field in ["ticket_id", "selected_candidate_ids", "allowed_probe_type", "row_body_reads_allowed", "output_dir"]:
        assert field in REQUIRED_TICKET_FIELDS
        assert field in schema["required_fields"]


def test_stage8981_ticket_template_is_inactive_and_safe() -> None:
    template = build_ticket_template()
    assert template["active"] is False
    assert template["execution_authorized"] is False
    assert template["row_body_reads_allowed"] is False
    assert template["repository_source_body_reads_allowed"] is False
    assert validate_ticket_template(template) == []


def test_stage8981_forbidden_operations_cover_unsafe_access() -> None:
    for item in ["DATASET_ROW_SCAN", "PARQUET_BATCH_MATERIALIZATION", "REPOSITORY_SOURCE_BODY_READ", "ARXIV_WRITE", "TRAINING", "MODEL_EXECUTION"]:
        assert item in FORBIDDEN_OPERATIONS


def test_stage8981_validation_rejects_active_ticket_or_bad_frontier() -> None:
    assert validate_design(base_card(), registry()) == []
    bad = base_card()
    bad["metrics"] = {**bad["metrics"], "execution_authorized": True}
    assert "execution_authorized" in validate_design(bad, registry())
    assert "unexpected_registry_frontier:9999" in validate_design(base_card(), registry(9999))
