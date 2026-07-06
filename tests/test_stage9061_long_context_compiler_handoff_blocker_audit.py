from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9061_long_context_compiler_handoff_blocker_audit import (  # noqa: E402
    audit_handoff_candidate,
    build_audit,
    closed_handoff_candidate,
    run_negative_cases,
)


def test_stage9061_compiler_handoff_blocker_passes() -> None:
    audit = build_audit()
    assert audit["passed"] is True
    assert audit["metrics"]["compiler_ready_rows_now"] == 0
    assert audit["metrics"]["training_ready_rows_now"] == 0
    assert audit["checks"]["negative_cases_rejected"] is True


def test_stage9061_closed_candidate_has_no_failures() -> None:
    assert audit_handoff_candidate(closed_handoff_candidate()) == []


def test_stage9061_negative_cases_rejected() -> None:
    negatives = run_negative_cases()
    assert negatives
    assert all(item["rejected"] for item in negatives.values())
