from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9147_metadata_only_repo_local_path_inventory_design import (  # noqa: E402
    INVENTORY_OUTPUT_FIELDS,
    INVENTORY_RULES,
    REQUIRED_CANDIDATE_TYPES,
    SEARCH_PATTERNS,
    build_design,
    validate_design,
)
from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # noqa: E402


def registry(latest: int = 9146) -> dict:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9147_design_passes_without_inventory_execution() -> None:
    design = build_design(registry())

    assert validate_design(design, registry()) == []
    assert all(design["checks"].values())
    assert not any(design["authority"].values())
    assert design["metrics"]["path_inventory_design_created"] is True
    assert design["metrics"]["path_inventory_executed"] is False
    assert design["metrics"]["path_inventory_materialized"] is False
    assert design["metrics"]["file_content_read"] is False
    assert design["metrics"]["json_parsed"] is False
    assert design["metrics"]["jsonl_rows_counted"] is False


def test_stage9147_records_output_fields_rules_and_search_patterns() -> None:
    design = build_design(registry())

    assert set(INVENTORY_OUTPUT_FIELDS).issubset(set(design["inventory_output_fields"]))
    assert set(INVENTORY_RULES).issubset(set(design["inventory_rules"]))
    assert set(REQUIRED_CANDIDATE_TYPES).issubset(set(design["required_candidate_types"]))
    assert set(REQUIRED_CANDIDATE_TYPES).issubset(set(design["search_patterns"]))
    assert SEARCH_PATTERNS["objective_rows_jsonl"]
    assert "do_not_open_candidate_files" in design["inventory_rules"]
    assert "do_not_parse_json" in design["inventory_rules"]
    assert "do_not_count_jsonl_rows" in design["inventory_rules"]
    assert "no_training_or_runtime" in design["inventory_rules"]


def test_stage9147_keeps_real_input_and_execution_closed() -> None:
    design = build_design(registry())
    metrics = design["metrics"]

    assert metrics["dataset_rows_loaded"] is False
    assert metrics["arxiv_accessed"] is False
    assert metrics["ticket_instance_materialized"] is False
    assert metrics["real_input_authorized_now"] is False
    assert metrics["real_judge_rows_used"] == 0
    assert metrics["real_ranker_rows_used"] == 0
    assert metrics["real_route_cards_materialized"] == 0
    assert metrics["route_cards_materialized_now"] is False
    assert metrics["route_to_loss_translation_ready_now"] is False
    assert metrics["loss_mask_cards_materialized_now"] is False
    assert metrics["compiler_handoff_ready_now"] is False
    assert metrics["repository_source_bodies_loaded"] is False
    assert metrics["trainer_executed_now"] is False
    assert metrics["model_forward_attempted"] is False
    assert metrics["training_authorized"] is False
    assert metrics["decoder_ce_authorized"] is False
    assert metrics["denoise_ce_authorized"] is False
    assert metrics["runtime_authorized_flag"] is False
    assert metrics["cleanup_authorized_now"] is False


def test_stage9147_rejects_missing_controls_execution_and_bad_frontier() -> None:
    design = build_design(registry())
    design["inventory_rules"].remove("do_not_open_candidate_files")
    assert "missing_inventory_rule:do_not_open_candidate_files" in validate_design(design, registry())

    design = build_design(registry())
    design["inventory_output_fields"].remove("content_read")
    assert "missing_inventory_output_field:content_read" in validate_design(design, registry())

    design = build_design(registry())
    design["search_patterns"].pop("objective_rows_jsonl")
    assert "missing_search_pattern:objective_rows_jsonl" in validate_design(design, registry())

    design = build_design(registry())
    design["metrics"]["json_parsed"] = True
    assert "json_parsed" in validate_design(design, registry())

    design = build_design(registry())
    design["metrics"]["path_inventory_executed"] = True
    assert "path_inventory_executed" in validate_design(design, registry())

    design = build_design(registry())
    assert "unexpected_registry_frontier:9999" in validate_design(design, registry(latest=9999))
