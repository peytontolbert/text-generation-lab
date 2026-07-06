from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8976_zero_row_schema_preflight_design import (  # noqa: E402
    AUTHORITY_CLOSED,
    CANDIDATE_LIMITS,
    FORBIDDEN_ZERO_ROW_OPERATIONS,
    FUTURE_PASS_GATES,
    available_route_counts,
    planned_selection_counts,
    validate_design,
)


def registry(latest: int = 8975) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def base_card() -> dict[str, object]:
    return {
        "checks": {"ok": True},
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
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


def test_stage8976_counts_available_routes() -> None:
    counts = available_route_counts({"route_counts": {"NAMED_SOFTWARE_MAINTAINER_DATASET_CANDIDATE": 4, "PARQUET_TABLE_CANDIDATE": 9, "JSONL_MANIFEST_CANDIDATE": 2}})
    assert counts["named_software_maintainer_dataset_candidates"] == 4
    assert counts["parquet_candidates"] == 9
    assert counts["jsonl_candidates"] == 2


def test_stage8976_planned_selection_caps_jsonl_at_zero() -> None:
    planned = planned_selection_counts({"named_software_maintainer_dataset_candidates": 99, "parquet_candidates": 99, "jsonl_candidates": 99})
    assert planned["named_software_maintainer_dataset_candidates"] == CANDIDATE_LIMITS["named_software_maintainer_dataset_candidates"]
    assert planned["parquet_candidates"] == CANDIDATE_LIMITS["parquet_candidates"]
    assert planned["jsonl_candidates"] == 0


def test_stage8976_forbidden_ops_block_rows_source_training_and_arxiv_write() -> None:
    for item in ["read_any_dataset_record", "read_jsonl_first_line", "read_repository_source_body", "write_to_arxiv", "start_training"]:
        assert item in FORBIDDEN_ZERO_ROW_OPERATIONS


def test_stage8976_future_gates_require_zero_rows() -> None:
    assert "dataset_records_read_equals_0" in FUTURE_PASS_GATES
    assert "repository_source_bodies_read_equals_0" in FUTURE_PASS_GATES
    assert "explicit_ticket_required_for_any_parquet_footer_access" in FUTURE_PASS_GATES


def test_stage8976_validation_rejects_schema_read_or_bad_frontier() -> None:
    assert validate_design(base_card(), registry()) == []
    bad = base_card()
    bad["metrics"] = {**bad["metrics"], "schema_or_header_read_performed": True}
    assert "schema_or_header_read_performed" in validate_design(bad, registry())
    assert "unexpected_registry_frontier:9999" in validate_design(base_card(), registry(9999))
