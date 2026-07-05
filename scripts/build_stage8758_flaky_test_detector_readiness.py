#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from flaky_test_detector import classify_rows

STAGE = 8758
NAME = "stage8758_flaky_test_detector_readiness"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "FLAKY_TEST_DETECTOR_READINESS_STAGE8758.md"
AUTHORITY_CLOSED = {"model_execution_authorized_next": False, "decoder_ce_training_authorized_next": False, "denoise_ce_training_authorized_next": False, "runtime_authorized": False, "source_emission_authorized": False, "body_emission_authorized": False, "gemma_execution_authorized_next": False, "harness_execution_authorized_next": False, "scoring_authorized_next": False, "controller_complete_merge_authorized_next": False, "promotion_ready": False}
ROWS = [
    {"row_id": "stable", "observations": [{"status": "failed", "error_type": "ImportError"}, {"status": "failed", "error_type": "ImportError"}]},
    {"row_id": "flaky", "observations": [{"status": "failed", "error_type": "Timeout"}, {"status": "passed"}]},
    {"row_id": "none"},
]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    test = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/test_flaky_test_detector.py"], cwd=ROOT, text=True, capture_output=True, check=False)
    sample = classify_rows(ROWS)
    sample_path = OUT_DIR / "flaky_test_detector_sample_card.json"
    sample_path.write_text(json.dumps(sample, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    failures=[]
    if test.returncode != 0:
        failures.append("unit_tests_failed")
    if sample["metrics"]["stable_rows"] != 1 or sample["metrics"]["holdout_rows"] != 1 or sample["metrics"]["rerun_needed_rows"] != 1:
        failures.append("sample_route_counts_wrong")
    card={"stage": STAGE, "stage_name": NAME, "passed": not failures, "authority": AUTHORITY_CLOSED, "metrics": {**AUTHORITY_CLOSED, "sample_rows": len(ROWS), "stable_rows": sample["metrics"]["stable_rows"], "holdout_rows": sample["metrics"]["holdout_rows"], "rerun_needed_rows": sample["metrics"]["rerun_needed_rows"], "failures": failures}, "artifacts": {"sample_card": str(sample_path.relative_to(ROOT)), "module": "scripts/flaky_test_detector.py", "tests": "tests/test_flaky_test_detector.py"}, "decision": "Flaky test detector is ready as a no-runtime failure-stability metadata gate." if not failures else "Flaky test detector readiness failed.", "next_best_step": "Attach flaky_test_detector to central graph when commit/reconcile path is clear; recover eval_trace_to_dataset_patch_loop next.", "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage8758 Flaky Test Detector Readiness", "", f"Passed: `{card['passed']}`", "", "Recovered a no-runtime failure-stability gate over provided rerun observations. It separates stable failures, flaky pass/fail mixes, unstable signatures, stable passes, and missing rerun evidence.", "", "Authority remains closed. This does not run tests or authorize runtime, mining, training, scoring, or promotion.", ""]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)

if __name__ == "__main__":
    main()
