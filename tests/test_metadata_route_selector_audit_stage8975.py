from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8975_metadata_route_selector_audit import (  # noqa: E402
    AUTHORITY_CLOSED,
    NEXT_STAGE_REQUIREMENTS,
    REQUIRED_DATASET_ROUTES,
    route_count,
    validate_audit,
)


def registry(latest: int = 8974) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def base_card() -> dict[str, object]:
    return {
        "checks": {"ok": True},
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
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


def test_stage8975_required_dataset_routes_include_core_candidates() -> None:
    assert "PARQUET_TABLE_CANDIDATE" in REQUIRED_DATASET_ROUTES
    assert "JSONL_MANIFEST_CANDIDATE" in REQUIRED_DATASET_ROUTES


def test_stage8975_route_count_reads_zero_when_missing() -> None:
    assert route_count({"route_counts": {"A": 3}}, "A") == 3
    assert route_count({"route_counts": {"A": 3}}, "B") == 0


def test_stage8975_next_requirements_keep_zero_row_boundary() -> None:
    assert "zero_row_only" in NEXT_STAGE_REQUIREMENTS
    assert "no_training_or_mining" in NEXT_STAGE_REQUIREMENTS


def test_stage8975_validation_rejects_training_or_bad_frontier() -> None:
    assert validate_audit(base_card(), registry()) == []
    bad = base_card()
    bad["metrics"] = {**bad["metrics"], "training_authorized": True}
    assert "training_authorized" in validate_audit(bad, registry())
    assert "unexpected_registry_frontier:9999" in validate_audit(base_card(), registry(9999))
