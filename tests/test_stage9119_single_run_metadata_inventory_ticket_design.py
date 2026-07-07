from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9119_single_run_metadata_inventory_ticket_design import (  # noqa: E402
    AUTHORITY_CLOSED,
    FORBIDDEN_IN_TICKET_STAGE,
    PRE_EXECUTION_REQUIREMENTS,
    RUN_COMMAND_SPEC,
    build_ticket,
    validate_ticket,
)


def registry(latest: int = 9118) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9119_records_single_run_command_and_requirements() -> None:
    ticket = build_ticket(registry())

    assert ticket["checks"]["source_stage9118_passed"] is True
    assert ticket["checks"]["source_stage9118_execution_not_authorized"] is True
    assert set(PRE_EXECUTION_REQUIREMENTS).issubset(ticket["pre_execution_requirements"])
    assert set(FORBIDDEN_IN_TICKET_STAGE).issubset(ticket["forbidden_in_this_stage"])
    for item in [
        "scripts/metadata_only_inventory_runner.py",
        "--datasets-root",
        "/arxiv/datasets",
        "--repositories-root",
        "/arxiv/repositories",
        "--metadata-only",
        "--no-row-reads",
        "--no-source-body-reads",
        "--no-arxiv-writes",
        "--no-follow-symlinks",
    ]:
        assert item in RUN_COMMAND_SPEC
        assert item in ticket["run_command_spec"]


def test_stage9119_does_not_authorize_or_execute_inventory() -> None:
    ticket = build_ticket(registry())
    metrics = ticket["metrics"]

    assert metrics["inventory_execution_authorized_now"] is False
    assert metrics["inventory_execution_authorized_next"] is False
    assert metrics["runner_executed_now"] is False
    assert metrics["arxiv_access_performed"] is False
    assert metrics["arxiv_stat_performed"] is False
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
    assert not any(ticket["authority"].values())


def test_stage9119_validation_rejects_missing_requirements_or_open_paths() -> None:
    ticket = build_ticket(registry())
    assert validate_ticket(ticket, registry()) == []

    missing_requirement = build_ticket(registry())
    missing_requirement["pre_execution_requirements"].remove("final_pre_execution_audit_passed")
    assert "missing_pre_execution_requirement:final_pre_execution_audit_passed" in validate_ticket(missing_requirement, registry())

    missing_forbidden = build_ticket(registry())
    missing_forbidden["forbidden_in_this_stage"].remove("runner_execution")
    assert "missing_forbidden_operation:runner_execution" in validate_ticket(missing_forbidden, registry())

    authorized = build_ticket(registry())
    authorized["metrics"]["inventory_execution_authorized_now"] = True
    assert "inventory_execution_authorized_now" in validate_ticket(authorized, registry())

    runner = build_ticket(registry())
    runner["metrics"]["runner_executed_now"] = True
    assert "runner_executed_now" in validate_ticket(runner, registry())

    arxiv = build_ticket(registry())
    arxiv["metrics"]["arxiv_access_performed"] = True
    assert "arxiv_access_performed" in validate_ticket(arxiv, registry())

    authority = build_ticket(registry())
    authority["authority"]["model_execution_authorized_next"] = True
    assert "authority_open" in validate_ticket(authority, registry())

    assert "unexpected_registry_frontier:9999" in validate_ticket(ticket, registry(latest=9999))
