from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from flaky_test_detector import classify_failure_stability, classify_rows


def test_holds_no_rerun_evidence() -> None:
    record = classify_failure_stability({"row_id": "none"})
    assert record["flaky_test_route"] == "HOLD_NO_RERUN_EVIDENCE"
    assert record["rerun_needed"] is True


def test_detects_flaky_pass_fail_mix() -> None:
    record = classify_failure_stability({"row_id": "flaky", "observations": [{"status": "failed", "error_type": "AssertionError"}, {"status": "passed"}]})
    assert record["flaky_test_route"] == "HOLD_FLAKY_FAILURE"
    assert record["route_to_holdout"] is True


def test_detects_stable_failure() -> None:
    record = classify_failure_stability({"row_id": "stable", "observations": [{"status": "failed", "error_type": "ImportError"}, {"status": "failed", "error_type": "ImportError"}]})
    assert record["flaky_test_route"] == "PASS_STABLE_FAILURE"
    assert record["failure_stability"] is True


def test_detects_unstable_failure_signature() -> None:
    record = classify_failure_stability({"row_id": "unstable", "observations": [{"status": "failed", "error_type": "ImportError"}, {"status": "failed", "error_type": "Timeout"}]})
    assert record["flaky_test_route"] == "HOLD_UNSTABLE_FAILURE_SIGNATURE"


def test_detects_stable_pass() -> None:
    record = classify_failure_stability({"row_id": "pass", "observations": [{"status": "passed"}, {"status": "passed"}]})
    assert record["flaky_test_route"] == "PASS_STABLE_PASS"


def test_manifest_counts_routes() -> None:
    card = classify_rows([
        {"row_id": "stable", "observations": [{"status": "failed", "error_type": "E"}, {"status": "failed", "error_type": "E"}]},
        {"row_id": "flaky", "observations": [{"status": "failed", "error_type": "E"}, {"status": "passed"}]},
        {"row_id": "none"},
    ])
    assert card["metrics"]["stable_rows"] == 1
    assert card["metrics"]["holdout_rows"] == 1
    assert card["metrics"]["rerun_needed_rows"] == 1
