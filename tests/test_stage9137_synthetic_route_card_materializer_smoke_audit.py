from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9137_synthetic_route_card_materializer_smoke_audit import (  # noqa: E402
    NEGATIVE_MUTATIONS,
    build_audit,
    run_negative_cases,
)
from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # noqa: E402
from scripts.route_card_materializer import materialize_synthetic_route_cards  # noqa: E402


def registry(latest: int = 9136) -> dict:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9137_audit_passes_synthetic_route_cards() -> None:
    audit = build_audit(registry())

    assert audit["passed"] is True
    assert audit["checks"]["route_card_count"] is True
    assert audit["checks"]["all_routes_covered"] is True
    assert audit["checks"]["card_failures_empty"] is True
    assert audit["checks"]["negative_cases_rejected"] is True
    assert audit["checks"]["no_real_inputs"] is True
    assert audit["checks"]["authority_closed"] is True
    assert audit["metrics"]["synthetic_route_cards_audited"] == 9
    assert audit["metrics"]["routes_covered"] == 9


def test_stage9137_rejects_mutated_route_cards() -> None:
    negatives = run_negative_cases(materialize_synthetic_route_cards())

    assert set(NEGATIVE_MUTATIONS) == set(negatives)
    assert all(item["rejected"] for item in negatives.values())
    assert any("authority_open" in failure for failure in negatives["open_authority"]["failures"])
    assert any("unknown_route" in failure for failure in negatives["unknown_route"]["failures"])
    assert any("missing_required_field:loss_mask_ref" in failure for failure in negatives["missing_required_field"]["failures"])
    assert any("missing_anti_cheat:label_leak_checked" in failure for failure in negatives["missing_anti_cheat"]["failures"])
    assert any("risk_bucket_route_mismatch" in failure for failure in negatives["risk_bucket_mismatch"]["failures"])
    assert any("recommended_action_route_mismatch" in failure for failure in negatives["recommended_action_mismatch"]["failures"])
    assert any("bounded_decoder_without_budget_ok" in failure for failure in negatives["bounded_decoder_budget_false"]["failures"])
    assert any("hold_long_output_without_long_bucket" in failure for failure in negatives["holdout_wrong_bucket"]["failures"])
    assert any("duplicate_row_id" in failure for failure in negatives["duplicate_row_id"]["failures"])


def test_stage9137_keeps_real_inputs_and_execution_closed() -> None:
    audit = build_audit(registry())
    metrics = audit["metrics"]

    assert metrics["real_judge_rows_used"] == 0
    assert metrics["real_ranker_rows_used"] == 0
    assert metrics["real_route_cards_materialized"] == 0
    assert metrics["route_cards_materialized_now"] is False
    assert metrics["route_to_loss_translation_ready_now"] is False
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


def test_stage9137_bad_registry_frontier_fails() -> None:
    audit = build_audit(registry(latest=9999))

    assert audit["passed"] is False
    assert "registry_frontier_stage9136" in audit["failures"]
