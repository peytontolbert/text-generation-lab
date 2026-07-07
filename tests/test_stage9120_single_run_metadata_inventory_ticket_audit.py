from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9120_single_run_metadata_inventory_ticket_audit import (  # noqa: E402
    build_audit,
    run_negative_cases,
)


def test_stage9120_base_audit_passes() -> None:
    audit = build_audit()

    assert audit["passed"] is True
    assert audit["base_failures"] == []
    assert audit["checks"]["base_ticket_passes"] is True
    assert audit["checks"]["negative_cases_rejected"] is True
    assert audit["checks"]["safe_command_flags_present"] is True
    assert audit["checks"]["pre_execution_requirements_recorded"] is True
    assert audit["checks"]["forbidden_stage_operations_recorded"] is True
    assert audit["checks"]["no_execution_now"] is True
    assert audit["checks"]["authority_closed"] is True


def test_stage9120_rejects_negative_cases() -> None:
    negatives = run_negative_cases()

    assert negatives
    assert all(item["rejected"] for item in negatives.values())
    for name in [
        "inventory_execution_authorized_now",
        "inventory_execution_authorized_next",
        "runner_executed_now",
        "arxiv_access_performed",
        "arxiv_stat_performed",
        "dataset_file_names_read_now",
        "repository_root_names_read_now",
        "dataset_rows_loaded",
        "repository_source_bodies_loaded",
        "arxiv_write_authorized",
        "data_mining_authorized",
        "trainer_executed_now",
        "model_forward_attempted",
        "training_authorized",
        "network_upload_performed",
        "cleanup_authorized_now",
    ]:
        assert name in negatives[name]["failures"]
    assert "missing_pre_execution_requirement:final_pre_execution_audit_passed" in negatives["missing_final_pre_execution_requirement"]["failures"]
    assert "missing_forbidden_operation:runner_execution" in negatives["missing_runner_execution_forbidden"]["failures"]
    assert "missing_command_flag:--no-source-body-reads" in negatives["missing_no_source_body_reads_command_flag"]["failures"]
    assert "authority_open" in negatives["authority_open"]["failures"]
    assert "unexpected_registry_frontier:9999" in negatives["unexpected_registry_frontier"]["failures"]


def test_stage9120_does_not_execute_or_authorize_inventory() -> None:
    audit = build_audit()
    metrics = audit["metrics"]

    assert metrics["inventory_execution_authorized_now"] is False
    assert metrics["inventory_execution_authorized_next"] is False
    assert metrics["runner_executed_now"] is False
    assert metrics["arxiv_access_performed"] is False
    assert metrics["dataset_file_names_read_now"] is False
    assert metrics["repository_root_names_read_now"] is False
    assert metrics["dataset_rows_loaded"] is False
    assert metrics["repository_source_bodies_loaded"] is False
    assert metrics["arxiv_write_authorized"] is False
    assert metrics["data_mining_authorized"] is False
    assert metrics["trainer_executed_now"] is False
    assert metrics["model_forward_attempted"] is False
    assert metrics["training_authorized"] is False
    assert metrics["network_upload_performed"] is False
    assert metrics["cleanup_authorized_now"] is False
    assert not any(audit["authority"].values())
