#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from coverage_test_selection import select_for_rows

STAGE = 8757
NAME = "stage8757_coverage_test_selection_readiness"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "COVERAGE_TEST_SELECTION_READINESS_STAGE8757.md"
AUTHORITY_CLOSED = {"model_execution_authorized_next": False, "decoder_ce_training_authorized_next": False, "denoise_ce_training_authorized_next": False, "runtime_authorized": False, "source_emission_authorized": False, "body_emission_authorized": False, "gemma_execution_authorized_next": False, "harness_execution_authorized_next": False, "scoring_authorized_next": False, "controller_complete_merge_authorized_next": False, "promotion_ready": False}
ROWS = [
    {"row_id": "ok", "repo_index": {"files": ["app/auth.py", "tests/test_auth.py"], "coverage_map": {"app/auth.py": ["tests/test_auth.py"]}}, "changes": [{"path": "app/auth.py", "symbol": "login"}]},
    {"row_id": "gap", "repo_index": {"files": ["app/auth.py"]}, "changes": [{"path": "app/auth.py"}]},
]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    test = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/test_coverage_test_selection.py"], cwd=ROOT, text=True, capture_output=True, check=False)
    sample = select_for_rows(ROWS)
    sample_path = OUT_DIR / "coverage_test_selection_sample_card.json"
    sample_path.write_text(json.dumps(sample, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    failures=[]
    if test.returncode != 0:
        failures.append("unit_tests_failed")
    if sample["metrics"]["pass_rows"] != 1 or sample["metrics"]["coverage_gap_rows"] != 1:
        failures.append("sample_route_counts_wrong")
    card={"stage": STAGE, "stage_name": NAME, "passed": not failures, "authority": AUTHORITY_CLOSED, "metrics": {**AUTHORITY_CLOSED, "sample_rows": len(ROWS), "pass_rows": sample["metrics"]["pass_rows"], "coverage_gap_rows": sample["metrics"]["coverage_gap_rows"], "failures": failures}, "artifacts": {"sample_card": str(sample_path.relative_to(ROOT)), "module": "scripts/coverage_test_selection.py", "tests": "tests/test_coverage_test_selection.py"}, "decision": "Coverage/test-selection module is ready as a no-execution static verifier-planning gate." if not failures else "Coverage/test-selection readiness failed.", "next_best_step": "Attach coverage_test_selection to central graph when commit/reconcile path is clear; recover flaky_test_detector next.", "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage8757 Coverage Test Selection Readiness", "", f"Passed: `{card['passed']}`", "", "Recovered a no-execution selector from changed files/symbols to candidate tests using coverage maps, path stems, and symbol-test metadata.", "", "Authority remains closed. This does not run tests or authorize runtime, mining, training, scoring, or promotion.", ""]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)

if __name__ == "__main__":
    main()
