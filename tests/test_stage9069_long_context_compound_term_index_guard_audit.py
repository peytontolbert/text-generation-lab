from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9069_long_context_compound_term_index_guard_audit import build_audit  # noqa: E402


def test_stage9069_compound_term_index_guard_passes() -> None:
    audit = build_audit()
    assert audit["passed"] is True
    assert audit["checks"]["compound_terms_extracted"] is True
    assert audit["checks"]["mention_rows_include_compound_terms"] is True
    assert audit["metrics"]["real_index_rows_written"] == 0


def test_stage9069_keeps_authority_closed() -> None:
    audit = build_audit()
    assert audit["metrics"]["training_authorized"] is False
    assert audit["metrics"]["candidate_rows_materialized"] == 0
    assert not any(audit["authority"].values())
