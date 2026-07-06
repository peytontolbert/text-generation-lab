from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9093_trainer_command_surface_static_audit import (  # noqa: E402
    build_audit,
    run_negative_cases,
)


def test_stage9093_base_audit_passes() -> None:
    audit = build_audit()
    assert audit["passed"] is True
    assert audit["base_failures"] == []
    assert audit["checks"]["required_flags_present"] is True
    assert audit["checks"]["required_modes_present"] is True
    assert audit["checks"]["required_guard_terms_present"] is True
    assert audit["checks"]["trainer_not_executed"] is True
    assert audit["checks"]["authority_closed"] is True


def test_stage9093_rejects_negative_cases() -> None:
    negatives = run_negative_cases()
    assert negatives
    assert all(item["rejected"] for item in negatives.values())
    assert "missing_required_flag:--manifest" in negatives["missing_manifest_flag"]["failures"]
    assert "missing_required_mode:bounded_decoder_ce_probe" in negatives["missing_bounded_decoder_mode"]["failures"]
    assert "missing_required_guard_term:safe_cleanup_checkpoints" in negatives["missing_safe_cleanup_guard"]["failures"]
    assert "trainer_executed_now" in negatives["trainer_executed_now"]["failures"]
    assert "contract_only_invoked_now" in negatives["contract_only_invoked_now"]["failures"]
    assert "model_input_rows_now" in negatives["model_input_rows_now"]["failures"]
    assert "route_to_loss_translation_ready_now" in negatives["route_to_loss_translation_ready_now"]["failures"]
    assert "decoder_ce_authorized" in negatives["decoder_ce_authorized"]["failures"]
    assert "authority_open" in negatives["authority_open"]["failures"]
    assert "unexpected_registry_frontier:9999" in negatives["unexpected_registry_frontier"]["failures"]


def test_stage9093_keeps_current_execution_closed() -> None:
    audit = build_audit()
    metrics = audit["metrics"]
    assert metrics["trainer_static_inspection_only"] is True
    assert metrics["trainer_executed_now"] is False
    assert metrics["contract_only_invoked_now"] is False
    assert metrics["route_to_loss_translation_ready_now"] is False
    assert metrics["model_input_rows_now"] == 0
    assert metrics["candidate_rows_materialized"] == 0
    assert metrics["model_forward_attempted"] is False
    assert metrics["training_authorized"] is False
    assert metrics["arxiv_read_authorized_for_compiler"] is False
    assert not any(audit["authority"].values())
