from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9113_metadata_only_real_data_inventory_ticket_design import (  # noqa: E402
    AUTHORITY_CLOSED,
    FORBIDDEN_FUTURE_OPERATIONS,
    PROTECTED_ROOTS,
    REQUIRED_OUTPUTS,
    build_ticket,
    validate_ticket,
)


def registry(latest: int = 9112) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9113_ticket_design_records_scope_and_outputs() -> None:
    ticket = build_ticket(registry())

    assert ticket["checks"]["source_stage9112_passed"] is True
    assert ticket["checks"]["protected_roots_recorded"] is True
    assert ticket["checks"]["allowed_future_operations_recorded"] is True
    assert ticket["checks"]["forbidden_future_operations_recorded"] is True
    assert ticket["checks"]["required_outputs_recorded"] is True
    assert set(PROTECTED_ROOTS).issubset(ticket["protected_roots"])
    assert set(REQUIRED_OUTPUTS).issubset(ticket["required_outputs"])


def test_stage9113_ticket_design_does_not_access_or_train_now() -> None:
    ticket = build_ticket(registry())
    metrics = ticket["metrics"]

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
    assert metrics["route_to_loss_translation_ready_now"] is False
    assert metrics["trainer_executed_now"] is False
    assert metrics["contract_only_invoked_now"] is False
    assert metrics["model_forward_attempted"] is False
    assert metrics["training_authorized"] is False
    assert metrics["decoder_ce_authorized"] is False
    assert metrics["denoise_ce_authorized"] is False
    assert metrics["network_upload_performed"] is False
    assert metrics["cleanup_authorized_now"] is False
    assert not any(ticket["authority"].values())


def test_stage9113_validation_rejects_missing_guards_or_open_paths() -> None:
    ticket = build_ticket(registry())
    assert validate_ticket(ticket, registry()) == []

    missing_root = build_ticket(registry())
    missing_root["protected_roots"].remove("/arxiv")
    assert "missing_protected_root:/arxiv" in validate_ticket(missing_root, registry())

    missing_forbidden = build_ticket(registry())
    missing_forbidden["forbidden_future_operations"].remove("read_repository_source_bodies")
    assert "missing_forbidden_operation:read_repository_source_bodies" in validate_ticket(missing_forbidden, registry())

    missing_output = build_ticket(registry())
    missing_output["required_outputs"].remove("protected_path_policy_card.json")
    assert "missing_required_output:protected_path_policy_card.json" in validate_ticket(missing_output, registry())

    arxiv = build_ticket(registry())
    arxiv["metrics"]["arxiv_access_performed"] = True
    assert "arxiv_access_performed" in validate_ticket(arxiv, registry())

    rows = build_ticket(registry())
    rows["metrics"]["dataset_rows_loaded"] = True
    assert "dataset_rows_loaded" in validate_ticket(rows, registry())

    trainer = build_ticket(registry())
    trainer["metrics"]["trainer_executed_now"] = True
    assert "trainer_executed_now" in validate_ticket(trainer, registry())

    authority = build_ticket(registry())
    authority["authority"]["model_execution_authorized_next"] = True
    assert "authority_open" in validate_ticket(authority, registry())

    assert "unexpected_registry_frontier:9999" in validate_ticket(ticket, registry(latest=9999))


def test_stage9113_forbids_all_body_training_and_cleanup_operations() -> None:
    ticket = build_ticket(registry())

    for operation in [
        "read_dataset_rows",
        "read_dataset_parquet_row_groups",
        "read_repository_source_bodies",
        "write_to_arxiv",
        "delete_from_arxiv",
        "start_mining",
        "execute_trainer",
        "model_forward",
        "decoder_ce_training",
        "denoise_ce_training",
        "network_upload",
        "cleanup_execution",
    ]:
        assert operation in FORBIDDEN_FUTURE_OPERATIONS
        assert operation in ticket["forbidden_future_operations"]
