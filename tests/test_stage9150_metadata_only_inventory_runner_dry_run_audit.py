from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9150_metadata_only_inventory_runner_dry_run_audit import (  # noqa: E402
    NEGATIVE_CASES,
    build_audit,
    run_negative_cases,
)
from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # noqa: E402


def registry(latest: int = 9149) -> dict:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9150_audit_passes_base_dry_run() -> None:
    audit = build_audit(registry())

    assert audit["passed"] is True
    assert audit["base_failures"] == []
    assert audit["checks"]["base_dry_run_passes"] is True
    assert audit["checks"]["synthetic_paths_only"] is True
    assert audit["checks"]["forbidden_arxiv_path_blocked"] is True
    assert audit["checks"]["all_rows_content_unread"] is True
    assert audit["checks"]["all_rows_counts_unread"] is True
    assert audit["checks"]["real_inventory_not_executed"] is True
    assert audit["checks"]["inventory_not_materialized"] is True
    assert audit["checks"]["authority_closed"] is True


def test_stage9150_rejects_negative_cases() -> None:
    negatives = run_negative_cases()

    assert set(NEGATIVE_CASES) == set(negatives)
    assert all(item["rejected"] for item in negatives.values())
    assert "source_stage9148_passed" in negatives["source_stage_missing"]["failures"]
    assert "synthetic_paths_only" in negatives["not_synthetic_paths_only"]["failures"]
    assert "forbidden_arxiv_path_blocked" in negatives["arxiv_not_blocked"]["failures"]
    assert "content_read" in negatives["row_content_read"]["failures"]
    assert "row_count_read" in negatives["row_count_read"]["failures"]
    assert "real_inventory_executed" in negatives["real_inventory_executed"]["failures"]
    assert "path_inventory_materialized" in negatives["path_inventory_materialized"]["failures"]
    assert "file_content_read" in negatives["file_content_read"]["failures"]
    assert "json_parsed" in negatives["json_parsed"]["failures"]
    assert "jsonl_rows_counted" in negatives["jsonl_rows_counted"]["failures"]
    assert "dataset_rows_loaded" in negatives["dataset_rows_loaded"]["failures"]
    assert "arxiv_accessed" in negatives["arxiv_accessed"]["failures"]
    assert "ticket_instance_materialized" in negatives["ticket_instance_materialized"]["failures"]
    assert "route_cards_materialized_now" in negatives["route_cards_materialized"]["failures"]
    assert "loss_mask_cards_materialized_now" in negatives["loss_masks_materialized"]["failures"]
    assert "training_authorized" in negatives["training_authorized"]["failures"]
    assert "runtime_authorized_flag" in negatives["runtime_authorized"]["failures"]
    assert "authority_open" in negatives["authority_open"]["failures"]
    assert "unexpected_registry_frontier:9999" in negatives["bad_registry_frontier"]["failures"]


def test_stage9150_keeps_real_inventory_and_execution_closed() -> None:
    audit = build_audit(registry())
    metrics = audit["metrics"]

    assert metrics["dry_run_audited"] is True
    assert metrics["real_inventory_executed"] is False
    assert metrics["path_inventory_materialized"] is False
    assert metrics["file_content_read"] is False
    assert metrics["json_parsed"] is False
    assert metrics["jsonl_rows_counted"] is False
    assert metrics["dataset_rows_loaded"] is False
    assert metrics["arxiv_accessed"] is False
    assert metrics["ticket_instance_materialized"] is False
    assert metrics["real_input_authorized_now"] is False
    assert metrics["real_judge_rows_used"] == 0
    assert metrics["real_ranker_rows_used"] == 0
    assert metrics["real_route_cards_materialized"] == 0
    assert metrics["route_cards_materialized_now"] is False
    assert metrics["loss_mask_cards_materialized_now"] is False
    assert metrics["trainer_executed_now"] is False
    assert metrics["model_forward_attempted"] is False
    assert metrics["training_authorized"] is False
    assert metrics["decoder_ce_authorized"] is False
    assert metrics["runtime_authorized_flag"] is False
    assert metrics["cleanup_authorized_now"] is False


def test_stage9150_bad_live_registry_fails() -> None:
    audit = build_audit(registry(latest=9999))

    assert audit["passed"] is False
    assert "registry_frontier_stage9149" in audit["failures"]
