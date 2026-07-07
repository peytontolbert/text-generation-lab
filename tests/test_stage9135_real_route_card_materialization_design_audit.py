from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9135_real_route_card_materialization_design_audit import (  # noqa: E402
    NEGATIVE_CASES,
    build_audit,
    run_negative_cases,
)
from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # noqa: E402


def registry(latest: int = 9134) -> dict:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9135_audit_passes_base_design() -> None:
    audit = build_audit(registry())

    assert audit["passed"] is True
    assert audit["base_failures"] == []
    assert audit["checks"]["base_design_passes"] is True
    assert audit["checks"]["required_inputs_complete"] is True
    assert audit["checks"]["required_outputs_complete"] is True
    assert audit["checks"]["blockers_complete"] is True
    assert audit["checks"]["route_rules_complete"] is True
    assert audit["checks"]["no_route_materialization"] is True
    assert audit["checks"]["no_dataset_loading"] is True
    assert audit["checks"]["authority_closed"] is True


def test_stage9135_rejects_negative_design_cases() -> None:
    negatives = run_negative_cases()

    assert set(NEGATIVE_CASES) == set(negatives)
    assert all(item["rejected"] for item in negatives.values())
    assert "missing_required_input:judge_rows_jsonl" in negatives["missing_judge_input"]["failures"]
    assert "missing_required_input:junk_ranker_rows_jsonl" in negatives["missing_ranker_input"]["failures"]
    assert "missing_required_output:route_cards.jsonl" in negatives["missing_route_cards_output"]["failures"]
    assert "missing_blocker:shortcut_dominance" in negatives["missing_blocker_shortcut"]["failures"]
    assert "missing_blocker:authority_open" in negatives["missing_blocker_authority"]["failures"]
    assert "missing_route_source_rule:KEEP_BOUNDED_DECODER" in negatives["missing_keep_bounded_rule"]["failures"]
    assert "route_cards_materialized_now" in negatives["materializes_route_cards"]["failures"]
    assert "dataset_rows_loaded" in negatives["loads_dataset_rows"]["failures"]
    assert "compiler_handoff_ready_now" in negatives["opens_compiler_handoff"]["failures"]
    assert "training_authorized" in negatives["opens_training"]["failures"]
    assert "decoder_ce_authorized" in negatives["opens_decoder_ce"]["failures"]
    assert "runtime_authorized_flag" in negatives["opens_runtime"]["failures"]
    assert "authority_open" in negatives["opens_authority"]["failures"]
    assert "unexpected_registry_frontier:9999" in negatives["bad_registry_frontier"]["failures"]


def test_stage9135_keeps_real_data_and_execution_closed() -> None:
    audit = build_audit(registry())
    metrics = audit["metrics"]

    assert metrics["real_route_cards_used"] == 0
    assert metrics["route_cards_materialized_now"] is False
    assert metrics["loss_mask_cards_materialized_now"] is False
    assert metrics["compiler_handoff_ready_now"] is False
    assert metrics["dataset_rows_loaded"] is False
    assert metrics["repository_source_bodies_loaded"] is False
    assert metrics["trainer_executed_now"] is False
    assert metrics["model_forward_attempted"] is False
    assert metrics["training_authorized"] is False
    assert metrics["decoder_ce_authorized"] is False
    assert metrics["denoise_ce_authorized"] is False
    assert metrics["runtime_authorized_flag"] is False
    assert metrics["network_upload_performed"] is False
    assert metrics["cleanup_authorized_now"] is False
    assert not any(audit["authority"].values())
