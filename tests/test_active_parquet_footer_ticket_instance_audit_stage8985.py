from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8985_active_parquet_footer_ticket_instance_audit import (  # noqa: E402
    AUTHORITY_CLOSED,
    EXPECTED_PROBE_TYPE,
    EXPECTED_TICKET_STATE,
    build_audit,
    validate_audit,
    validate_ticket,
)


def registry() -> dict[str, object]:
    return {"metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage8985_audits_pending_ticket_without_execution() -> None:
    card = build_audit(registry())
    assert card["metrics"]["selected_candidate_count"] == 5
    assert card["metrics"]["ticket_failures"] == 0
    assert card["metrics"]["ticket_pending_audit"] is True
    assert card["metrics"]["execution_authorized"] is False
    assert card["metrics"]["parquet_footer_access_performed"] is False


def test_stage8985_ticket_validation_rejects_executable_or_wrong_probe() -> None:
    ticket = {
        "ticket_state": EXPECTED_TICKET_STATE,
        "allowed_probe_type": EXPECTED_PROBE_TYPE,
        "selected_candidate_ids": ["candidate_0001"],
        "max_candidates": 5,
        "row_body_reads_allowed": False,
        "repository_source_body_reads_allowed": False,
        "arxiv_write_allowed": False,
        "batch_materialization_allowed": False,
        "footer_access_authorized_now": False,
        "execution_authorized": False,
        "forbidden_operations": ["DATASET_ROW_SCAN", "REPOSITORY_SOURCE_BODY_READ", "ARXIV_WRITE", "TRAINING", "MINING", "MODEL_EXECUTION"],
        "output_dir": "runs/local/artifacts/x",
    }
    selected = [{"candidate_id": "candidate_0001", "candidate_file_opened": False}]
    dry = [{"candidate_id": "candidate_0001", "planned_probe": "future_parquet_footer_schema_ticket_required", "probe_executed_now": False, "arxiv_file_opened_now": False}]
    assert validate_ticket(ticket, selected, dry) == []
    bad = dict(ticket)
    bad["execution_authorized"] = True
    assert "execution_authorized" in validate_ticket(bad, selected, dry)
    wrong = dict(ticket)
    wrong["allowed_probe_type"] = "ROW_SCAN"
    assert "allowed_probe_type" in validate_ticket(wrong, selected, dry)


def test_stage8985_validation_rejects_open_authority_or_training_flag() -> None:
    card = build_audit(registry())
    assert validate_audit(card) == []
    bad = build_audit(registry())
    bad["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_audit(bad)
    train = build_audit(registry())
    train["metrics"]["training_authorized"] = True
    assert "training_authorized" in validate_audit(train)
