from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9060_long_context_candidate_quality_guard_refresh_audit import build_audit


def test_stage9060_candidate_quality_guard_refresh_passes() -> None:
    audit = build_audit()
    assert audit["passed"] is True
    assert audit["checks"]["generic_names_rejected"] is True
    assert audit["checks"]["implementation_paths_sort_first"] is True
    assert audit["checks"]["no_real_index_read"] is True


def test_stage9060_no_authority_or_materialization() -> None:
    audit = build_audit()
    assert audit["metrics"]["real_index_rows_read"] == 0
    assert audit["metrics"]["candidate_rows_materialized"] == 0
    assert audit["metrics"]["training_authorized"] is False
    assert not any(audit["authority"].values())
