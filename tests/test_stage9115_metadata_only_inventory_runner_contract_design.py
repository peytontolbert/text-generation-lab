from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9115_metadata_only_inventory_runner_contract_design import (  # noqa: E402
    AUTHORITY_CLOSED,
    FORBIDDEN_RUNTIME_ACTIONS,
    REQUIRED_CLI_FLAGS,
    REQUIRED_RUNTIME_ASSERTIONS,
    build_contract,
    validate_contract,
)


def registry(latest: int = 9114) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9115_records_runner_contract_requirements() -> None:
    contract = build_contract(registry())

    assert contract["checks"]["source_stage9114_passed"] is True
    assert contract["checks"]["source_stage9114_rejected_negative_cases"] is True
    assert set(REQUIRED_CLI_FLAGS).issubset(contract["required_cli_flags"])
    assert set(REQUIRED_RUNTIME_ASSERTIONS).issubset(contract["required_runtime_assertions"])
    assert set(FORBIDDEN_RUNTIME_ACTIONS).issubset(contract["forbidden_runtime_actions"])


def test_stage9115_runner_contract_does_not_execute_or_access_now() -> None:
    contract = build_contract(registry())
    metrics = contract["metrics"]

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
    assert not any(contract["authority"].values())


def test_stage9115_validation_rejects_missing_contract_parts_or_open_paths() -> None:
    contract = build_contract(registry())
    assert validate_contract(contract, registry()) == []

    missing_flag = build_contract(registry())
    missing_flag["required_cli_flags"].remove("--metadata-only")
    assert "missing_required_cli_flag:--metadata-only" in validate_contract(missing_flag, registry())

    missing_assertion = build_contract(registry())
    missing_assertion["required_runtime_assertions"].remove("row_reads_disabled")
    assert "missing_runtime_assertion:row_reads_disabled" in validate_contract(missing_assertion, registry())

    missing_action = build_contract(registry())
    missing_action["forbidden_runtime_actions"].remove("open_source_file_for_body")
    assert "missing_forbidden_runtime_action:open_source_file_for_body" in validate_contract(missing_action, registry())

    runner = build_contract(registry())
    runner["metrics"]["runner_executed_now"] = True
    assert "runner_executed_now" in validate_contract(runner, registry())

    arxiv = build_contract(registry())
    arxiv["metrics"]["arxiv_access_performed"] = True
    assert "arxiv_access_performed" in validate_contract(arxiv, registry())

    source = build_contract(registry())
    source["metrics"]["repository_source_bodies_loaded"] = True
    assert "repository_source_bodies_loaded" in validate_contract(source, registry())

    authority = build_contract(registry())
    authority["authority"]["model_execution_authorized_next"] = True
    assert "authority_open" in validate_contract(authority, registry())

    assert "unexpected_registry_frontier:9999" in validate_contract(contract, registry(latest=9999))
