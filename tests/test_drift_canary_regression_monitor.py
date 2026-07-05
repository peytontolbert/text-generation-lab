from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from drift_canary_regression_monitor import evaluate_canaries, evaluate_canary


def test_canary_passes_without_drop() -> None:
    record = evaluate_canary({"canary_id": "old_skill", "baseline_score": 0.9, "current_score": 0.91, "min_score": 0.8, "max_allowed_drop": 0.02})
    assert record["passed"] is True


def test_canary_blocks_regression_drop() -> None:
    record = evaluate_canary({"canary_id": "old_skill", "baseline_score": 0.9, "current_score": 0.7, "max_allowed_drop": 0.05})
    assert record["passed"] is False
    assert "regression_drop_exceeded" in record["promotion_block_reasons"]


def test_canary_blocks_locked_eval_leakage() -> None:
    record = evaluate_canary({"canary_id": "leak", "baseline_score": 1.0, "current_score": 1.0, "locked_eval_leakage": True})
    assert "locked_eval_leakage" in record["promotion_block_reasons"]


def test_canary_blocks_missing_metric_card() -> None:
    record = evaluate_canary({"canary_id": "missing", "baseline_score": 1.0, "current_score": 1.0, "metric_card_present": False})
    assert "missing_metric_card" in record["promotion_block_reasons"]


def test_canary_suite_reports_forgotten_skills() -> None:
    card = evaluate_canaries([
        {"canary_id": "stable", "baseline_score": 0.8, "current_score": 0.81, "max_allowed_drop": 0.05},
        {"canary_id": "forgotten", "baseline_score": 0.9, "current_score": 0.7, "max_allowed_drop": 0.05},
    ])
    assert card["passed"] is False
    assert card["metrics"]["forgotten_skills"] == ["forgotten"]
