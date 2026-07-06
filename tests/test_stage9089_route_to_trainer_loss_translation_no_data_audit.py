from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9089_route_to_trainer_loss_translation_no_data_audit import (  # noqa: E402
    build_audit,
    run_negative_cases,
)


def test_stage9089_base_audit_passes() -> None:
    audit = build_audit()
    assert audit["passed"] is True
    assert audit["base_failures"] == []
    assert audit["checks"]["required_inputs_present"] is True
    assert audit["checks"]["translation_outputs_present"] is True
    assert audit["checks"]["translation_closed"] is True
    assert audit["checks"]["authority_closed"] is True


def test_stage9089_rejects_negative_cases() -> None:
    negatives = run_negative_cases()
    assert negatives
    assert all(item["rejected"] for item in negatives.values())
    assert "translation_ready_now" in negatives["translation_ready_now"]["failures"]
    assert "model_input_rows_now" in negatives["model_input_rows_now"]["failures"]
    assert "compiler_handoff_ready_now" in negatives["compiler_handoff_ready_now"]["failures"]
    assert "trainer_dry_run_ready_now" in negatives["trainer_dry_run_ready_now"]["failures"]
    assert "decoder_ce_authorized" in negatives["decoder_ce_authorized"]["failures"]
    assert "authority_open" in negatives["authority_open"]["failures"]
    assert "unexpected_registry_frontier:9999" in negatives["unexpected_registry_frontier"]["failures"]


def test_stage9089_keeps_current_execution_closed() -> None:
    audit = build_audit()
    metrics = audit["metrics"]
    assert metrics["translation_ready_now"] is False
    assert metrics["compiler_handoff_ready_now"] is False
    assert metrics["trainer_dry_run_ready_now"] is False
    assert metrics["trainer_dry_run_executed_now"] is False
    assert metrics["model_input_rows_now"] == 0
    assert metrics["candidate_rows_materialized"] == 0
    assert metrics["model_forward_attempted"] is False
    assert metrics["training_authorized"] is False
    assert metrics["arxiv_read_authorized_for_compiler"] is False
    assert not any(audit["authority"].values())
