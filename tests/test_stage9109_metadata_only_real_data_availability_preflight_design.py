from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9109_metadata_only_real_data_availability_preflight_design import (  # noqa: E402
    AUTHORITY_CLOSED,
    FORBIDDEN_IN_THIS_STAGE,
    FUTURE_METADATA_ONLY_STEPS,
    PROTECTED_ROOTS,
    build_plan,
    validate_plan,
)


def registry(latest: int = 9108) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9109_declares_arxiv_backup_roots_and_metadata_only_steps() -> None:
    card = build_plan(registry())
    assert "/arxiv" in PROTECTED_ROOTS
    assert "/arxiv/datasets" in PROTECTED_ROOTS
    assert "/arxiv/repositories" in PROTECTED_ROOTS
    assert card["checks"]["protected_roots_declared"] is True
    assert "inventory_dataset_files_by_name_size_extension_mtime_only" in FUTURE_METADATA_ONLY_STEPS
    assert "count_candidate_dataset_files_without_opening_rows" in FUTURE_METADATA_ONLY_STEPS


def test_stage9109_forbids_body_reads_writes_training_and_cleanup() -> None:
    for item in [
        "read_dataset_rows",
        "read_dataset_parquet_groups",
        "read_repository_source_body",
        "write_to_arxiv",
        "delete_or_cleanup_arxiv",
        "execute_training",
    ]:
        assert item in FORBIDDEN_IN_THIS_STAGE
    card = build_plan(registry())
    metrics = card["metrics"]
    assert metrics["arxiv_access_performed"] is False
    assert metrics["arxiv_stat_performed"] is False
    assert metrics["dataset_rows_loaded"] is False
    assert metrics["repository_source_bodies_loaded"] is False
    assert metrics["arxiv_write_authorized"] is False
    assert metrics["cleanup_authorized_now"] is False
    assert not any(card["authority"].values())


def test_stage9109_validation_rejects_arxiv_access_rows_training_or_bad_frontier() -> None:
    card = build_plan(registry())
    assert validate_plan(card, registry()) == []
    stat = build_plan(registry())
    stat["metrics"]["arxiv_stat_performed"] = True
    assert "arxiv_stat_performed" in validate_plan(stat, registry())
    rows = build_plan(registry())
    rows["metrics"]["dataset_rows_loaded"] = True
    assert "dataset_rows_loaded" in validate_plan(rows, registry())
    source = build_plan(registry())
    source["metrics"]["repository_source_bodies_loaded"] = True
    assert "repository_source_bodies_loaded" in validate_plan(source, registry())
    training = build_plan(registry())
    training["metrics"]["training_authorized"] = True
    assert "training_authorized" in validate_plan(training, registry())
    authority = build_plan(registry())
    authority["authority"]["model_execution_authorized_next"] = True
    assert "authority_open" in validate_plan(authority, registry())
    assert "unexpected_registry_frontier:9999" in validate_plan(card, registry(latest=9999))
