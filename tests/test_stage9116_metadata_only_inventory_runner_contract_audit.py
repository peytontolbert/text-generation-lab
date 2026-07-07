from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9116_metadata_only_inventory_runner_contract_audit import (  # noqa: E402
    build_audit,
    run_negative_cases,
)


def test_stage9116_base_audit_passes() -> None:
    audit = build_audit()

    assert audit["passed"] is True
    assert audit["base_failures"] == []
    assert audit["checks"]["base_contract_passes"] is True
    assert audit["checks"]["negative_cases_rejected"] is True
    assert audit["checks"]["required_cli_flags_recorded"] is True
    assert audit["checks"]["required_runtime_assertions_recorded"] is True
    assert audit["checks"]["forbidden_runtime_actions_recorded"] is True
    assert audit["checks"]["no_runner_execution_now"] is True
    assert audit["checks"]["no_arxiv_access_now"] is True
    assert audit["checks"]["no_row_or_source_body_reads_now"] is True
    assert audit["checks"]["authority_closed"] is True


def test_stage9116_rejects_negative_cases() -> None:
    negatives = run_negative_cases()

    assert negatives
    assert all(item["rejected"] for item in negatives.values())
    for name in [
        "runner_executed_now",
        "arxiv_access_performed",
        "arxiv_stat_performed",
        "dataset_file_names_read_now",
        "repository_root_names_read_now",
        "dataset_rows_loaded",
        "dataset_parquet_groups_read",
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
    assert "missing_required_cli_flag:--metadata-only" in negatives["missing_metadata_only_flag"]["failures"]
    assert "missing_runtime_assertion:source_body_reads_disabled" in negatives["missing_source_body_disabled_assertion"]["failures"]
    assert "missing_forbidden_runtime_action:open_source_file_for_body" in negatives["missing_source_body_forbidden_action"]["failures"]
    assert "authority_open" in negatives["authority_open"]["failures"]
    assert "unexpected_registry_frontier:9999" in negatives["unexpected_registry_frontier"]["failures"]


def test_stage9116_does_not_execute_or_access_now() -> None:
    audit = build_audit()
    metrics = audit["metrics"]

    assert metrics["runner_executed_now"] is False
    assert metrics["arxiv_access_performed"] is False
    assert metrics["arxiv_stat_performed"] is False
    assert metrics["dataset_file_names_read_now"] is False
    assert metrics["repository_root_names_read_now"] is False
    assert metrics["dataset_rows_loaded"] is False
    assert metrics["dataset_parquet_groups_read"] is False
    assert metrics["repository_source_bodies_loaded"] is False
    assert metrics["arxiv_write_authorized"] is False
    assert metrics["data_mining_authorized"] is False
    assert metrics["trainer_executed_now"] is False
    assert metrics["model_forward_attempted"] is False
    assert metrics["training_authorized"] is False
    assert metrics["network_upload_performed"] is False
    assert metrics["cleanup_authorized_now"] is False
    assert not any(audit["authority"].values())
