from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9151_route_card_candidate_quality_gate_contract import (  # noqa: E402
    FUTURE_INPUTS,
    NEGATIVE_CASES,
    QUALITY_GATE_RULES,
    REQUIRED_CANDIDATE_FIELDS,
    build_summary,
    run_negative_cases,
    validate_contract,
)


def test_stage9151_contract_passes_and_declares_candidate_shape() -> None:
    summary = build_summary()
    contract = summary["contract"]

    assert summary["passed"] is True
    assert validate_contract(contract) == []
    assert set(FUTURE_INPUTS).issubset(set(contract["future_inputs"]))
    assert set(REQUIRED_CANDIDATE_FIELDS).issubset(set(contract["required_candidate_fields"]))
    assert set(QUALITY_GATE_RULES).issubset(set(contract["quality_gate_rules"]))
    assert "source_inventory_lineage" in contract["required_candidate_fields"]
    assert "source_provenance" in contract["required_candidate_fields"]
    assert "loss_mask_policy" in contract["required_candidate_fields"]
    assert "authority" in contract["required_candidate_fields"]


def test_stage9151_rejects_negative_cases() -> None:
    negatives = run_negative_cases()

    assert set(NEGATIVE_CASES) == set(negatives)
    assert all(item["rejected"] for item in negatives.values())
    assert "missing_future_input:metadata_only_repo_local_path_inventory_manifest" in negatives["missing_future_input"]["failures"]
    assert "missing_required_candidate_field:source_provenance" in negatives["missing_required_candidate_field"]["failures"]
    assert "missing_quality_gate_rule:no_file_content_or_body_fields" in negatives["missing_quality_gate_rule"]["failures"]
    assert "inventory_runner_executed_now" in negatives["inventory_executed_now"]["failures"]
    assert "metadata_path_inventory_loaded_now" in negatives["path_inventory_loaded_now"]["failures"]
    assert "path_inventory_rows_loaded" in negatives["path_inventory_loaded_now"]["failures"]
    assert "file_content_read" in negatives["file_content_read"]["failures"]
    assert "hidden_eval_allowed" in negatives["hidden_eval_allowed"]["failures"]
    assert "route_cards_materialized_now" in negatives["route_cards_materialized"]["failures"]
    assert "candidate_rows_loaded" in negatives["route_cards_materialized"]["failures"]
    assert "loss_mask_cards_materialized_now" in negatives["loss_masks_materialized"]["failures"]
    assert "compiler_handoff_ready_now" in negatives["compiler_handoff_ready"]["failures"]
    assert "training_authorized" in negatives["training_authorized"]["failures"]
    assert "decoder_ce_authorized" in negatives["decoder_ce_authorized"]["failures"]
    assert "denoise_ce_authorized" in negatives["denoise_ce_authorized"]["failures"]
    assert "authority_open" in negatives["authority_open"]["failures"]


def test_stage9151_keeps_execution_materialization_and_training_closed() -> None:
    summary = build_summary()
    metrics = summary["metrics"]
    contract_metrics = summary["contract"]["metrics"]

    assert metrics["contract_only"] is True
    assert contract_metrics["inventory_runner_executed_now"] is False
    assert contract_metrics["metadata_path_inventory_loaded_now"] is False
    assert contract_metrics["path_inventory_rows_loaded"] == 0
    assert contract_metrics["candidate_rows_loaded"] == 0
    assert contract_metrics["file_content_read"] is False
    assert contract_metrics["dataset_rows_loaded"] is False
    assert contract_metrics["arxiv_accessed"] is False
    assert contract_metrics["hidden_eval_allowed"] is False
    assert contract_metrics["locked_eval_allowed"] is False
    assert contract_metrics["route_cards_materialized_now"] is False
    assert contract_metrics["loss_mask_cards_materialized_now"] is False
    assert contract_metrics["compiler_handoff_ready_now"] is False
    assert contract_metrics["trainer_dry_run_passed_now"] is False
    assert contract_metrics["trainer_executed_now"] is False
    assert contract_metrics["model_forward_attempted"] is False
    assert contract_metrics["training_authorized"] is False
    assert contract_metrics["decoder_ce_authorized"] is False
    assert contract_metrics["denoise_ce_authorized"] is False
    assert contract_metrics["runtime_authorized_flag"] is False
    assert contract_metrics["cleanup_authorized_now"] is False
    assert not any(summary["authority"].values())
