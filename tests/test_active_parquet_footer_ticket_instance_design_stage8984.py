from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8984_active_parquet_footer_ticket_instance_design import (  # noqa: E402
    ALLOWED_PROBE_TYPE,
    AUTHORITY_CLOSED,
    SELECTED_LIMIT,
    TICKET_STATE,
    build_ticket,
    parquet_candidate_rows,
    select_candidate_ids,
    validate_design,
    validate_ticket,
)


def registry(latest: int = 8983) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def base_card() -> dict[str, object]:
    return {
        "checks": {"ok": True},
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "ticket_failures": 0,
            "footer_access_authorized_now": False,
            "execution_authorized": False,
            "parquet_footer_access_performed": False,
            "candidate_file_opened": False,
            "dataset_rows_loaded": False,
            "repository_source_bodies_loaded": False,
            "arxiv_write_authorized": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "model_execution_attempted": False,
            "schema_or_header_read_performed": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "network_upload_performed": False,
        },
    }


def sample_rows() -> list[dict[str, object]]:
    return [
        {"candidate_id": f"candidate_{idx:04d}", "relative_path": f"p{idx}.parquet", "route": "PARQUET_TABLE_CANDIDATE", "extension": ".parquet", "planned_probe": "future_parquet_footer_schema_ticket_required", "probe_executed_now": False, "arxiv_file_opened_now": False, "dataset_rows_loaded": False}
        for idx in range(8)
    ]


def test_stage8984_selects_only_parquet_dry_run_candidates() -> None:
    rows = sample_rows() + [{"candidate_id": "jsonl", "extension": ".jsonl", "planned_probe": "metadata_path_only"}]
    assert len(parquet_candidate_rows(rows)) == 8
    selected = select_candidate_ids(rows)
    assert len(selected) == SELECTED_LIMIT
    assert all(row["extension"] == ".parquet" for row in selected)
    assert all(row["footer_access_authorized_now"] is False for row in selected)


def test_stage8984_ticket_is_pending_and_not_executable() -> None:
    rows = sample_rows()
    selected = select_candidate_ids(rows)
    ticket = build_ticket(selected, {"required_artifacts": ["a"], "forbidden_operations": ["b"], "pass_gates": ["c"]})
    assert ticket["ticket_state"] == TICKET_STATE
    assert ticket["allowed_probe_type"] == ALLOWED_PROBE_TYPE
    assert ticket["execution_authorized"] is False
    assert validate_ticket(ticket, selected, rows) == []


def test_stage8984_validation_rejects_execution_or_bad_frontier() -> None:
    assert validate_design(base_card(), registry()) == []
    bad = base_card()
    bad["metrics"] = {**bad["metrics"], "execution_authorized": True}
    assert "execution_authorized" in validate_design(bad, registry())
    assert "unexpected_registry_frontier:9999" in validate_design(base_card(), registry(9999))
