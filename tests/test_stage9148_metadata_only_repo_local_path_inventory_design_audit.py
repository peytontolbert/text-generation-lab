from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9148_metadata_only_repo_local_path_inventory_design_audit import (  # noqa: E402
    NEGATIVE_CASES,
    build_audit,
    run_negative_cases,
)
from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # noqa: E402


def registry(latest: int = 9147) -> dict:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9148_audit_passes_base_inventory_design() -> None:
    audit = build_audit(registry())

    assert audit["passed"] is True
    assert audit["base_failures"] == []
    assert audit["checks"]["base_design_passes"] is True
    assert audit["checks"]["inventory_output_fields_complete"] is True
    assert audit["checks"]["inventory_rules_complete"] is True
    assert audit["checks"]["candidate_patterns_complete"] is True
    assert audit["checks"]["inventory_not_executed"] is True
    assert audit["checks"]["inventory_not_materialized"] is True
    assert audit["checks"]["file_content_not_read"] is True
    assert audit["checks"]["json_not_parsed"] is True
    assert audit["checks"]["jsonl_rows_not_counted"] is True
    assert audit["checks"]["arxiv_not_accessed"] is True
    assert audit["checks"]["authority_closed"] is True


def test_stage9148_rejects_negative_cases() -> None:
    negatives = run_negative_cases()

    assert set(NEGATIVE_CASES) == set(negatives)
    assert all(item["rejected"] for item in negatives.values())
    assert "missing_inventory_output_field:content_read" in negatives["missing_content_read_field"]["failures"]
    assert "missing_inventory_output_field:row_count_read" in negatives["missing_row_count_field"]["failures"]
    assert "missing_inventory_rule:do_not_open_candidate_files" in negatives["missing_no_open_rule"]["failures"]
    assert "missing_inventory_rule:do_not_parse_json" in negatives["missing_no_parse_rule"]["failures"]
    assert "missing_inventory_rule:do_not_count_jsonl_rows" in negatives["missing_no_row_count_rule"]["failures"]
    assert "missing_search_pattern:objective_rows_jsonl" in negatives["missing_objective_pattern"]["failures"]
    assert "path_inventory_executed" in negatives["inventory_executed"]["failures"]
    assert "path_inventory_materialized" in negatives["inventory_materialized"]["failures"]
    assert "file_content_read" in negatives["file_content_read"]["failures"]
    assert "json_parsed" in negatives["json_parsed"]["failures"]
    assert "jsonl_rows_counted" in negatives["jsonl_rows_counted"]["failures"]
    assert "dataset_rows_loaded" in negatives["dataset_rows_loaded"]["failures"]
    assert "arxiv_accessed" in negatives["arxiv_accessed"]["failures"]
    assert "ticket_instance_materialized" in negatives["ticket_instance_materialized"]["failures"]
    assert "route_cards_materialized_now" in negatives["route_cards_materialized"]["failures"]
    assert "training_authorized" in negatives["training_authorized"]["failures"]
    assert "runtime_authorized_flag" in negatives["runtime_authorized"]["failures"]
    assert "authority_open" in negatives["authority_open"]["failures"]
    assert "unexpected_registry_frontier:9999" in negatives["bad_registry_frontier"]["failures"]


def test_stage9148_keeps_inventory_and_execution_closed() -> None:
    audit = build_audit(registry())
    metrics = audit["metrics"]

    assert metrics["path_inventory_design_audited"] is True
    assert metrics["path_inventory_executed"] is False
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
    assert metrics["compiler_handoff_ready_now"] is False
    assert metrics["trainer_executed_now"] is False
    assert metrics["model_forward_attempted"] is False
    assert metrics["training_authorized"] is False
    assert metrics["decoder_ce_authorized"] is False
    assert metrics["denoise_ce_authorized"] is False
    assert metrics["runtime_authorized_flag"] is False
    assert metrics["cleanup_authorized_now"] is False


def test_stage9148_bad_live_registry_fails() -> None:
    audit = build_audit(registry(latest=9999))

    assert audit["passed"] is False
    assert "registry_frontier_stage9147" in audit["failures"]
