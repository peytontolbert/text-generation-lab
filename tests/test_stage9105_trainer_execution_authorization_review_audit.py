from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9105_trainer_execution_authorization_review_audit import build_audit, run_negative_cases


def test_stage9105_base_audit_passes() -> None:
    audit = build_audit()
    assert audit["passed"] is True
    assert audit["base_failures"] == []
    assert audit["checks"]["base_review_passes"] is True
    assert audit["checks"]["negative_cases_rejected"] is True
    assert audit["checks"]["same_stage_execution_closed"] is True
    assert audit["checks"]["next_stage_execution_closed"] is True
    assert audit["checks"]["trainer_not_executed"] is True
    assert audit["checks"]["contract_only_not_invoked"] is True
    assert audit["checks"]["authority_closed"] is True


def test_stage9105_rejects_negative_cases() -> None:
    negatives = run_negative_cases()
    assert negatives
    assert all(item["rejected"] for item in negatives.values())
    assert "same_stage_execution_authorized" in negatives["same_stage_execution_authorized"]["failures"]
    assert "next_stage_execution_authorized" in negatives["next_stage_execution_authorized"]["failures"]
    assert "trainer_executed_now" in negatives["trainer_executed_now"]["failures"]
    assert "contract_only_invoked_now" in negatives["contract_only_invoked_now"]["failures"]
    assert "runtime_assertions_executed_now" in negatives["runtime_assertions_executed_now"]["failures"]
    assert "model_input_rows_now" in negatives["model_input_rows_now"]["failures"]
    assert "decoder_ce_authorized" in negatives["decoder_ce_authorized"]["failures"]
    assert "cleanup_authorized_now" in negatives["cleanup_authorized_now"]["failures"]
    assert "missing_future_execution_requirement:final_pre_execution_audit_passed" in negatives["missing_future_execution_requirement"]["failures"]
    assert "current_blockers_missing" in negatives["current_blockers_missing"]["failures"]
    assert "authority_open" in negatives["authority_open"]["failures"]
    assert "unexpected_registry_frontier:9999" in negatives["unexpected_registry_frontier"]["failures"]


def test_stage9105_keeps_execution_closed() -> None:
    audit = build_audit()
    metrics = audit["metrics"]
    assert metrics["same_stage_execution_authorized"] is False
    assert metrics["next_stage_execution_authorized"] is False
    assert metrics["trainer_executed_now"] is False
    assert metrics["contract_only_invoked_now"] is False
    assert metrics["runtime_assertions_executed_now"] is False
    assert metrics["model_input_rows_now"] == 0
    assert metrics["candidate_rows_materialized"] == 0
    assert metrics["model_forward_attempted"] is False
    assert metrics["training_authorized"] is False
    assert metrics["decoder_ce_authorized"] is False
    assert metrics["cleanup_authorized_now"] is False
    assert not any(audit["authority"].values())
