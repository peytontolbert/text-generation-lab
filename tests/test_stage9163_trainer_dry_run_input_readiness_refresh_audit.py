from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9163_trainer_dry_run_input_readiness_refresh_audit import (  # noqa: E402
    AUDIT_NEGATIVE_CASES,
    build_audit,
    registry,
    run_negative_cases,
)


def test_stage9163_audit_passes_with_stage9162_frontier() -> None:
    audit = build_audit(registry())

    assert audit["passed"] is True
    assert audit["failures"] == []
    assert audit["checks"]["source_stage9162_passed"] is True
    assert audit["checks"]["base_card_passes"] is True
    assert audit["checks"]["registry_frontier_stage9162"] is True
    assert audit["checks"]["required_interpretability_telemetry_present"] is True
    assert audit["checks"]["trainer_input_blocked"] is True
    assert audit["checks"]["contract_only_output_blocked"] is True
    assert audit["checks"]["model_input_rows_blocked"] is True


def test_stage9163_rejects_negative_cases() -> None:
    negatives = run_negative_cases()

    assert set(AUDIT_NEGATIVE_CASES) == set(negatives)
    assert all(item["rejected"] for item in negatives.values())
    assert "unexpected_registry_frontier:9999" in negatives["bad_registry_frontier"]["failures"]
    assert "missing_telemetry_stub:row_token_loss.jsonl" in negatives["missing_row_token_loss_telemetry"]["failures"]
    assert "missing_telemetry_stub:activation_probe_cache.pt" in negatives["missing_activation_cache_telemetry"]["failures"]
    assert "trainer_contract_only_invoked_now" in negatives["trainer_contract_only_invoked"]["failures"]
    assert "model_weights_loaded" in negatives["model_weights_loaded"]["failures"]
    assert "optimizer_created" in negatives["optimizer_created"]["failures"]
    assert "backward_called" in negatives["backward_called"]["failures"]
    assert "model_input_rows_now" in negatives["model_input_rows_nonzero"]["failures"]


def test_stage9163_rejects_bad_registry_frontier() -> None:
    audit = build_audit(registry(latest=9999))

    assert audit["passed"] is False
    assert "registry_frontier_stage9162" in audit["failures"]


def test_stage9163_keeps_training_and_runtime_closed() -> None:
    audit = build_audit(registry())
    metrics = audit["metrics"]

    assert metrics["trainer_input_materialized_now"] is False
    assert metrics["trainer_contract_only_invoked_now"] is False
    assert metrics["trainer_dry_run_ready_now"] is False
    assert metrics["trainer_executed_now"] is False
    assert metrics["model_input_rows_now"] == 0
    assert metrics["model_forward_attempted"] is False
    assert metrics["model_weights_loaded"] is False
    assert metrics["optimizer_created"] is False
    assert metrics["backward_called"] is False
    assert metrics["training_authorized"] is False
    assert metrics["decoder_ce_authorized"] is False
    assert metrics["denoise_ce_authorized"] is False
    assert metrics["runtime_authorized_flag"] is False
    assert metrics["arxiv_accessed"] is False
    assert metrics["file_content_read"] is False
    assert metrics["dataset_rows_loaded"] is False
    assert metrics["repository_source_bodies_loaded"] is False
    assert metrics["cleanup_authorized_now"] is False
    assert not any(audit["authority"].values())
