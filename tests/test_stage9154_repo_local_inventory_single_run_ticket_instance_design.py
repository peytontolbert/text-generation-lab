from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9154_repo_local_inventory_single_run_ticket_instance_design import (  # noqa: E402
    ALLOWED_ROOTS,
    FORBIDDEN_ROOTS,
    NEGATIVE_CASES,
    TICKET_FIELDS,
    TICKET_INVARIANTS,
    build_summary,
    run_negative_cases,
    validate_design,
)


def test_stage9154_design_passes_and_keeps_ticket_inactive() -> None:
    summary = build_summary()
    design = summary["design"]
    template = design["ticket_instance_template"]

    assert summary["passed"] is True
    assert validate_design(design) == []
    assert template["approved_for_metadata_inventory_execution"] is False
    assert template["approved_for_route_card_materialization"] is False
    assert template["allowed_roots"] == ALLOWED_ROOTS
    assert "/arxiv" in template["forbidden_roots"]
    assert not any(summary["authority"].values())


def test_stage9154_rejects_negative_cases() -> None:
    negatives = run_negative_cases()

    assert set(NEGATIVE_CASES) == set(negatives)
    assert all(item["rejected"] for item in negatives.values())
    assert "source_stage9153_not_passed" in negatives["source_stage_missing"]["failures"]
    assert "missing_ticket_field:allowed_roots" in negatives["missing_ticket_field"]["failures"]
    assert "missing_ticket_invariant:allowed_roots_must_equal_repo_local_artifact_roots" in negatives["missing_ticket_invariant"]["failures"]
    assert "allowed_roots_not_exact" in negatives["allowed_root_missing"]["failures"]
    assert "missing_forbidden_root:/arxiv" in negatives["arxiv_not_forbidden"]["failures"]
    assert "metadata_inventory_execution_authorized_now" in negatives["execution_authorized_now"]["failures"]
    assert "route_card_materialization_authorized_now" in negatives["route_card_materialization_authorized_now"]["failures"]
    assert "list_paths_only_not_true" in negatives["list_paths_only_disabled"]["failures"]
    assert "no_file_content_reads_not_true" in negatives["file_content_read_allowed"]["failures"]
    assert "no_json_parse_not_true" in negatives["json_parse_allowed"]["failures"]
    assert "no_jsonl_row_count_not_true" in negatives["jsonl_row_count_allowed"]["failures"]
    assert "no_dataset_row_load_not_true" in negatives["dataset_row_load_allowed"]["failures"]
    assert "inventory_runner_executed_now" in negatives["inventory_executed_now"]["failures"]
    assert "route_cards_materialized_now" in negatives["route_cards_materialized"]["failures"]
    assert "loss_mask_cards_materialized_now" in negatives["loss_masks_materialized"]["failures"]
    assert "compiler_handoff_ready_now" in negatives["compiler_handoff_ready"]["failures"]
    assert "trainer_executed_now" in negatives["trainer_executed"]["failures"]
    assert "training_authorized" in negatives["training_authorized"]["failures"]
    assert "authority_open" in negatives["authority_open"]["failures"]


def test_stage9154_declares_ticket_shape() -> None:
    summary = build_summary()
    design = summary["design"]

    assert set(TICKET_FIELDS).issubset(set(design["ticket_fields"]))
    assert set(TICKET_INVARIANTS).issubset(set(design["ticket_invariants"]))
    assert set(ALLOWED_ROOTS) == set(design["ticket_instance_template"]["allowed_roots"])
    assert set(FORBIDDEN_ROOTS).issubset(set(design["ticket_instance_template"]["forbidden_roots"]))


def test_stage9154_keeps_inventory_route_and_training_closed() -> None:
    summary = build_summary()
    metrics = summary["metrics"]

    assert metrics["design_only"] is True
    assert metrics["ticket_instance_materialized_for_execution"] is False
    assert metrics["metadata_inventory_execution_authorized_now"] is False
    assert metrics["metadata_inventory_execution_authorized_next"] is False
    assert metrics["inventory_runner_executed_now"] is False
    assert metrics["file_content_read"] is False
    assert metrics["json_parsed"] is False
    assert metrics["jsonl_rows_counted"] is False
    assert metrics["dataset_rows_loaded"] is False
    assert metrics["arxiv_accessed"] is False
    assert metrics["route_cards_materialized_now"] is False
    assert metrics["loss_mask_cards_materialized_now"] is False
    assert metrics["compiler_handoff_ready_now"] is False
    assert metrics["trainer_executed_now"] is False
    assert metrics["training_authorized"] is False
    assert metrics["decoder_ce_authorized"] is False
    assert metrics["denoise_ce_authorized"] is False
    assert metrics["runtime_authorized_flag"] is False
