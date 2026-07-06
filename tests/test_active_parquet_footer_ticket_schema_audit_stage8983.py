from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8983_active_parquet_footer_ticket_schema_audit import (  # noqa: E402
    AUTHORITY_CLOSED,
    REQUIRED_FALSE_TEMPLATE_FLAGS,
    REQUIRED_FORBIDDEN_OPERATIONS,
    REQUIRED_PASS_GATES,
    audit_schema,
    candidate_ids,
    validate_audit,
)


def registry(latest: int = 8982) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def base_card() -> dict[str, object]:
    return {
        "checks": {"ok": True},
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "missing_template_fields": 0,
            "missing_forbidden_operations": 0,
            "missing_pass_gates": 0,
            "false_flag_failures": 0,
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


def test_stage8983_required_lists_cover_safety_surface() -> None:
    assert "active" in REQUIRED_FALSE_TEMPLATE_FLAGS
    assert "DATASET_ROW_SCAN" in REQUIRED_FORBIDDEN_OPERATIONS
    assert "selected_candidate_ids_subset_of_stage8979_dry_run_rows" in REQUIRED_PASS_GATES


def test_stage8983_candidate_ids_extracts_ids() -> None:
    assert candidate_ids([{"candidate_id": "a"}, {"candidate_id": "b"}, {}]) == {"a", "b"}


def test_stage8983_audit_schema_detects_missing_fields_and_flags() -> None:
    schema = {"required_fields": ["ticket_id"], "forbidden_operations": [], "pass_gates": []}
    template = {"active": True, "selected_candidate_ids": ["missing"], "max_candidates": 1}
    audit = audit_schema(schema, template, [{"candidate_id": "present"}])
    assert audit["missing_template_fields"] == ["ticket_id"]
    assert "DATASET_ROW_SCAN" in audit["missing_forbidden_operations"]
    assert "active" in audit["false_flag_failures"]
    assert audit["selected_candidate_ids_subset"] is False


def test_stage8983_validation_rejects_active_ticket_or_bad_frontier() -> None:
    assert validate_audit(base_card(), registry()) == []
    bad = base_card()
    bad["metrics"] = {**bad["metrics"], "ticket_active": True}
    assert "ticket_active" in validate_audit(bad, registry())
    bad_missing = base_card()
    bad_missing["metrics"] = {**bad_missing["metrics"], "missing_pass_gates": 1}
    assert "missing_pass_gates" in validate_audit(bad_missing, registry())
    assert "unexpected_registry_frontier:9999" in validate_audit(base_card(), registry(9999))
