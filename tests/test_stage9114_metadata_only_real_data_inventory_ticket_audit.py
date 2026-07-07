from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9114_metadata_only_real_data_inventory_ticket_audit import (  # noqa: E402
    build_audit,
    run_negative_cases,
)


def test_stage9114_base_audit_passes() -> None:
    audit = build_audit()

    assert audit["passed"] is True
    assert audit["base_failures"] == []
    assert audit["checks"]["base_ticket_passes"] is True
    assert audit["checks"]["negative_cases_rejected"] is True
    assert audit["checks"]["protected_roots_recorded"] is True
    assert audit["checks"]["forbidden_future_operations_recorded"] is True
    assert audit["checks"]["required_outputs_recorded"] is True
    assert audit["checks"]["no_arxiv_access_now"] is True
    assert audit["checks"]["no_row_or_source_body_reads_now"] is True
    assert audit["checks"]["authority_closed"] is True


def test_stage9114_rejects_negative_cases() -> None:
    negatives = run_negative_cases()

    assert negatives
    assert all(item["rejected"] for item in negatives.values())
    for name in [
        "arxiv_access_performed",
        "arxiv_stat_performed",
        "dataset_file_names_read_now",
        "repository_root_names_read_now",
        "dataset_rows_loaded",
        "dataset_parquet_groups_read",
        "repository_source_bodies_loaded",
        "arxiv_write_authorized",
        "data_mining_authorized",
        "route_cards_materialized_now",
        "route_to_loss_translation_ready_now",
        "trainer_executed_now",
        "contract_only_invoked_now",
        "model_forward_attempted",
        "training_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "network_upload_performed",
        "cleanup_authorized_now",
    ]:
        assert name in negatives[name]["failures"]
    assert "missing_protected_root:/arxiv" in negatives["missing_protected_arxiv_root"]["failures"]
    assert "missing_forbidden_operation:read_repository_source_bodies" in negatives["missing_repository_source_body_forbidden"]["failures"]
    assert "missing_required_output:protected_path_policy_card.json" in negatives["missing_protected_path_policy_output"]["failures"]
    assert "authority_open" in negatives["authority_open"]["failures"]
    assert "unexpected_registry_frontier:9999" in negatives["unexpected_registry_frontier"]["failures"]


def test_stage9114_does_not_inventory_or_train() -> None:
    audit = build_audit()
    metrics = audit["metrics"]

    assert metrics["arxiv_access_performed"] is False
    assert metrics["arxiv_stat_performed"] is False
    assert metrics["dataset_file_names_read_now"] is False
    assert metrics["repository_root_names_read_now"] is False
    assert metrics["dataset_rows_loaded"] is False
    assert metrics["dataset_parquet_groups_read"] is False
    assert metrics["repository_source_bodies_loaded"] is False
    assert metrics["arxiv_write_authorized"] is False
    assert metrics["data_mining_authorized"] is False
    assert metrics["route_cards_materialized_now"] is False
    assert metrics["trainer_executed_now"] is False
    assert metrics["contract_only_invoked_now"] is False
    assert metrics["model_forward_attempted"] is False
    assert metrics["training_authorized"] is False
    assert metrics["decoder_ce_authorized"] is False
    assert metrics["denoise_ce_authorized"] is False
    assert metrics["network_upload_performed"] is False
    assert metrics["cleanup_authorized_now"] is False
    assert not any(audit["authority"].values())
