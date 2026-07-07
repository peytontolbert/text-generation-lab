from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9143_real_route_card_input_ticket_instance_schema_audit import (  # noqa: E402
    NEGATIVE_CASES,
    build_audit,
    run_negative_cases,
)
from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # noqa: E402


def registry(latest: int = 9142) -> dict:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9143_audit_passes_base_schema() -> None:
    audit = build_audit(registry())

    assert audit["passed"] is True
    assert audit["base_failures"] == []
    assert audit["checks"]["base_schema_passes"] is True
    assert audit["checks"]["instance_fields_complete"] is True
    assert audit["checks"]["instance_invariants_complete"] is True
    assert audit["checks"]["no_ticket_instance"] is True
    assert audit["checks"]["no_preflight_approval"] is True
    assert audit["checks"]["no_materialization_approval"] is True
    assert audit["checks"]["authority_closed"] is True


def test_stage9143_rejects_negative_cases() -> None:
    negatives = run_negative_cases()

    assert set(NEGATIVE_CASES) == set(negatives)
    assert all(item["rejected"] for item in negatives.values())
    assert "missing_instance_field:manual_approval_record" in negatives["missing_manual_approval_record"]["failures"]
    assert "missing_instance_invariant:approved_for_route_card_materialization_false" in negatives["missing_route_materialization_false_invariant"]["failures"]
    assert "missing_instance_invariant:arxiv_paths_forbidden_without_separate_authorization" in negatives["missing_arxiv_invariant"]["failures"]
    assert "ticket_instance_materialized" in negatives["ticket_instance_materialized"]["failures"]
    assert "approved_for_preflight_only" in negatives["preflight_approved_now"]["failures"]
    assert "approved_for_route_card_materialization" in negatives["route_materialization_approved_now"]["failures"]
    assert "real_input_authorized_now" in negatives["real_input_authorized_now"]["failures"]
    assert "dataset_rows_loaded" in negatives["dataset_rows_loaded"]["failures"]
    assert "training_authorized" in negatives["opens_training"]["failures"]
    assert "decoder_ce_authorized" in negatives["opens_decoder_ce"]["failures"]
    assert "runtime_authorized_flag" in negatives["opens_runtime"]["failures"]
    assert "authority_open" in negatives["authority_open"]["failures"]
    assert "unexpected_registry_frontier:9999" in negatives["bad_registry_frontier"]["failures"]


def test_stage9143_keeps_all_execution_and_real_input_closed() -> None:
    audit = build_audit(registry())
    metrics = audit["metrics"]

    assert metrics["ticket_instance_schema_audited"] is True
    assert metrics["ticket_instance_materialized"] is False
    assert metrics["approved_for_preflight_only"] is False
    assert metrics["approved_for_route_card_materialization"] is False
    assert metrics["real_input_authorized_now"] is False
    assert metrics["real_judge_rows_used"] == 0
    assert metrics["real_ranker_rows_used"] == 0
    assert metrics["real_route_cards_materialized"] == 0
    assert metrics["route_cards_materialized_now"] is False
    assert metrics["loss_mask_cards_materialized_now"] is False
    assert metrics["compiler_handoff_ready_now"] is False
    assert metrics["dataset_rows_loaded"] is False
    assert metrics["trainer_executed_now"] is False
    assert metrics["model_forward_attempted"] is False
    assert metrics["training_authorized"] is False
    assert metrics["decoder_ce_authorized"] is False
    assert metrics["denoise_ce_authorized"] is False
    assert metrics["runtime_authorized_flag"] is False
    assert metrics["cleanup_authorized_now"] is False


def test_stage9143_bad_live_registry_fails() -> None:
    audit = build_audit(registry(latest=9999))

    assert audit["passed"] is False
    assert "registry_frontier_stage9142" in audit["failures"]
