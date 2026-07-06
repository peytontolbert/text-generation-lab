from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9070_long_context_compound_candidate_ratio_guard_audit import build_audit  # noqa: E402


def test_stage9070_compound_candidate_ratio_guard_passes() -> None:
    audit = build_audit()
    assert audit["passed"] is True
    assert audit["checks"]["compound_entity_relaxed_ratio_allows_0_02"] is True
    assert audit["checks"]["compound_entity_ratio_blocks_above_relaxed_cap"] is True
    assert audit["metrics"]["candidate_rows_materialized"] == 0


def test_stage9070_keeps_authority_closed() -> None:
    audit = build_audit()
    assert audit["metrics"]["training_authorized"] is False
    assert audit["metrics"]["model_execution_attempted"] is False
    assert not any(audit["authority"].values())
