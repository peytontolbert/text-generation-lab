from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9145_route_card_input_candidate_locator_design import (  # noqa: E402
    ALLOWED_SEARCH_ROOTS,
    FORBIDDEN_SEARCH_ROOTS,
    LOCATOR_RULES,
    REQUIRED_CANDIDATE_TYPES,
    build_design,
    validate_design,
)
from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # noqa: E402


def registry(latest: int = 9144) -> dict:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9145_design_passes_without_scan_or_read() -> None:
    design = build_design(registry())

    assert validate_design(design, registry()) == []
    assert all(design["checks"].values())
    assert not any(design["authority"].values())
    assert design["metrics"]["candidate_locator_designed"] is True
    assert design["metrics"]["candidate_locator_executed"] is False
    assert design["metrics"]["path_inventory_materialized"] is False
    assert design["metrics"]["file_content_read"] is False
    assert design["metrics"]["dataset_rows_loaded"] is False


def test_stage9145_records_allowed_forbidden_roots_candidate_types_and_rules() -> None:
    design = build_design(registry())

    assert set(ALLOWED_SEARCH_ROOTS).issubset(set(design["allowed_search_roots"]))
    assert set(FORBIDDEN_SEARCH_ROOTS).issubset(set(design["forbidden_search_roots"]))
    assert set(REQUIRED_CANDIDATE_TYPES).issubset(set(design["required_candidate_types"]))
    assert set(LOCATOR_RULES).issubset(set(design["locator_rules"]))
    assert "/arxiv" in design["forbidden_search_roots"]
    assert "no_arxiv_reads" in design["locator_rules"]
    assert "no_file_content_reads" in design["locator_rules"]
    assert "objective_rows_jsonl" in design["required_candidate_types"]
    assert "junk_ranker_rows_jsonl" in design["required_candidate_types"]


def test_stage9145_keeps_real_input_and_execution_closed() -> None:
    design = build_design(registry())
    metrics = design["metrics"]

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


def test_stage9145_rejects_missing_controls_and_bad_frontier() -> None:
    design = build_design(registry())
    design["forbidden_search_roots"].remove("/arxiv")
    assert "missing_forbidden_search_root:/arxiv" in validate_design(design, registry())

    design = build_design(registry())
    design["locator_rules"].remove("no_file_content_reads")
    assert "missing_locator_rule:no_file_content_reads" in validate_design(design, registry())

    design = build_design(registry())
    design["metrics"]["candidate_locator_executed"] = True
    assert "candidate_locator_executed" in validate_design(design, registry())

    design = build_design(registry())
    design["authority"]["model_execution_authorized_next"] = True
    assert "authority_open" in validate_design(design, registry())

    design = build_design(registry())
    assert "unexpected_registry_frontier:9999" in validate_design(design, registry(latest=9999))
