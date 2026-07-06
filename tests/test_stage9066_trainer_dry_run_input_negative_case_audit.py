from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9066_trainer_dry_run_input_negative_case_audit import build_audit, run_negative_cases  # noqa: E402


def test_stage9066_negative_case_audit_passes() -> None:
    audit = build_audit()
    assert audit["passed"] is True
    assert audit["base_failures"] == []
    assert audit["checks"]["negative_cases_rejected"] is True


def test_stage9066_all_negative_cases_are_rejected() -> None:
    negatives = run_negative_cases()
    assert negatives
    assert all(item["rejected"] for item in negatives.values())
    assert "model_forward_attempted" in negatives["model_forward_attempted"]["failures"]
    assert "authority_open" in negatives["authority_open_model_execution"]["failures"]
