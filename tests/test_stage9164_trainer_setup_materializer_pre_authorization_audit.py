from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9164_trainer_setup_materializer_pre_authorization_audit import (  # noqa: E402
    NEGATIVE_CASES,
    REQUIRED_BLOCKING_FINDINGS,
    REQUIRED_OUTPUTS_DETECTED,
    REQUIRED_PRESENT_SYMBOLS,
    build_audit,
    registry,
    run_negative_cases,
)


def test_stage9164_detects_materializer_and_blocking_findings() -> None:
    audit = build_audit(registry())

    assert audit["passed"] is True
    assert audit["failures"] == []
    assert audit["checks"]["source_stage9163_passed"] is True
    assert audit["checks"]["registry_frontier_stage9163"] is True
    assert audit["checks"]["materializer_present"] is True
    assert audit["checks"]["required_symbols_present"] is True
    assert audit["checks"]["required_outputs_detected"] is True
    assert audit["checks"]["blocking_findings_present"] is True
    assert set(REQUIRED_PRESENT_SYMBOLS).issubset(set(audit["analysis"]["required_symbols_present"]))
    assert set(REQUIRED_OUTPUTS_DETECTED).issubset(set(audit["analysis"]["outputs_detected"]))
    assert set(REQUIRED_BLOCKING_FINDINGS).issubset(set(audit["analysis"]["blocking_findings"]))


def test_stage9164_rejects_negative_cases() -> None:
    negatives = run_negative_cases()

    assert set(NEGATIVE_CASES) == set(negatives)
    assert all(item["rejected"] for item in negatives.values())
    assert "source_stage9163_passed" in negatives["source_stage_missing"]["failures"]
    assert "registry_frontier_stage9163" in negatives["registry_frontier_bad"]["failures"]
    assert "materializer_present" in negatives["materializer_missing"]["failures"]
    assert "required_symbols_present" in negatives["missing_required_symbol"]["failures"]
    assert "required_outputs_detected" in negatives["missing_required_output"]["failures"]
    assert "blocking_findings_present" in negatives["missing_blocking_finding"]["failures"]
    assert "authority_closed" in negatives["authority_open"]["failures"]


def test_stage9164_keeps_execution_closed() -> None:
    audit = build_audit(registry())
    metrics = audit["metrics"]

    assert metrics["trainer_input_materialized_now"] is False
    assert metrics["trainer_executed_now"] is False
    assert metrics["model_forward_attempted"] is False
    assert metrics["training_authorized"] is False
    assert metrics["decoder_ce_authorized"] is False
    assert metrics["denoise_ce_authorized"] is False
    assert metrics["runtime_authorized_flag"] is False
    assert metrics["arxiv_accessed"] is False
    assert metrics["file_content_read"] is False
    assert metrics["dataset_rows_loaded"] is False
    assert metrics["repository_source_bodies_loaded"] is False
    assert not any(audit["authority"].values())
