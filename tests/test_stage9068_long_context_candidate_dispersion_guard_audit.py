from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9068_long_context_candidate_dispersion_guard_audit import build_audit  # noqa: E402


def test_stage9068_dispersion_guard_audit_passes() -> None:
    audit = build_audit()
    assert audit["passed"] is True
    assert audit["checks"]["single_doc_single_repo_dispersion_low"] is True
    assert audit["checks"]["multi_doc_cross_source_dispersion_passes"] is True
    assert audit["metrics"]["candidate_rows_materialized"] == 0


def test_stage9068_keeps_authority_closed() -> None:
    audit = build_audit()
    assert audit["metrics"]["training_authorized"] is False
    assert audit["metrics"]["model_execution_attempted"] is False
    assert not any(audit["authority"].values())
