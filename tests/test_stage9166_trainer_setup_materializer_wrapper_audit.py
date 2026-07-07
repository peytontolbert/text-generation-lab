from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9166_trainer_setup_materializer_wrapper_audit import (  # noqa: E402
    AUDIT_NEGATIVE_CASES,
    build_audit,
    registry,
    run_negative_cases,
)


def test_stage9166_audit_passes_with_stage9165_frontier() -> None:
    audit = build_audit(registry())

    assert audit["passed"] is True
    assert audit["failures"] == []
    assert audit["checks"]["source_stage9165_passed"] is True
    assert audit["checks"]["base_design_passes"] is True
    assert audit["checks"]["registry_frontier_stage9165"] is True
    assert audit["checks"]["trainer_input_blocked"] is True
    assert audit["checks"]["model_input_rows_blocked"] is True


def test_stage9166_rejects_negative_cases() -> None:
    negatives = run_negative_cases()

    assert set(AUDIT_NEGATIVE_CASES) == set(negatives)
    assert all(item["rejected"] for item in negatives.values())
    assert "source_stage9164_not_passed" in negatives["source_stage_missing"]["failures"]
    assert "registry_frontier_stage9164" in negatives["registry_frontier_bad"]["failures"]
    assert "materializer_present" in negatives["materializer_missing"]["failures"]
    assert "missing_wrapper_input:stage9164_materializer_audit_ref" in negatives["missing_wrapper_input"]["failures"]
    assert "missing_wrapper_guard:wrapper_rejects_trainer_input_write_without_ticket" in negatives["missing_wrapper_guard"]["failures"]
    assert "missing_contract_only_output:materializer_wrapper_ticket.json" in negatives["missing_contract_only_output"]["failures"]
    assert "missing_blocked_output:trainer_dry_run_input.json" in negatives["missing_blocked_output"]["failures"]
    assert "missing_blocked_output:model_input_rows.jsonl" in negatives["missing_blocked_model_input_rows"]["failures"]
    assert "materializer_invoked_now" in negatives["materializer_invoked"]["failures"]
    assert "trainer_input_materialized_now" in negatives["trainer_input_materialized"]["failures"]
    assert "model_input_rows_materialized_now" in negatives["model_input_rows_materialized"]["failures"]
    assert "model_forward_attempted" in negatives["model_forward"]["failures"]
    assert "optimizer_created" in negatives["optimizer_created"]["failures"]
    assert "backward_called" in negatives["backward_called"]["failures"]
    assert "arxiv_accessed" in negatives["arxiv_accessed"]["failures"]
    assert "training_authorized" in negatives["training_authorized"]["failures"]
    assert "decoder_ce_authorized" in negatives["decoder_ce_authorized"]["failures"]
    assert "denoise_ce_authorized" in negatives["denoise_ce_authorized"]["failures"]
    assert "runtime_authorized_flag" in negatives["runtime_authorized"]["failures"]
    assert "authority_open" in negatives["authority_open"]["failures"]
    assert "unexpected_registry_frontier:9999" in negatives["bad_registry_frontier"]["failures"]


def test_stage9166_keeps_execution_closed() -> None:
    audit = build_audit(registry())
    metrics = audit["metrics"]

    assert metrics["materializer_invoked_now"] is False
    assert metrics["trainer_input_materialized_now"] is False
    assert metrics["model_input_rows_materialized_now"] is False
    assert metrics["model_forward_attempted"] is False
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
    assert not any(audit["authority"].values())
