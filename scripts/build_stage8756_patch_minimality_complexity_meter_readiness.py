#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from patch_minimality_complexity_meter import score_rows

STAGE = 8756
NAME = "stage8756_patch_minimality_complexity_meter_readiness"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "PATCH_MINIMALITY_COMPLEXITY_METER_READINESS_STAGE8756.md"
AUTHORITY_CLOSED = {"model_execution_authorized_next": False, "decoder_ce_training_authorized_next": False, "denoise_ce_training_authorized_next": False, "runtime_authorized": False, "source_emission_authorized": False, "body_emission_authorized": False, "gemma_execution_authorized_next": False, "harness_execution_authorized_next": False, "scoring_authorized_next": False, "controller_complete_merge_authorized_next": False, "promotion_ready": False}
ROWS = [
    {"row_id": "ok", "patch": "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-a=1\n+a=2"},
    {"row_id": "missing"},
    {"row_id": "dep", "patch": "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n+import requests"},
    {"row_id": "api", "patch": "diff --git a/api.py b/api.py\n--- a/api.py\n+++ b/api.py\n+def public_api():\n+    return 1"},
]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    test = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/test_patch_minimality_complexity_meter.py"], cwd=ROOT, text=True, capture_output=True, check=False)
    sample = score_rows(ROWS)
    sample_path = OUT_DIR / "patch_minimality_sample_card.json"
    sample_path.write_text(json.dumps(sample, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    failures=[]
    if test.returncode != 0:
        failures.append("unit_tests_failed")
    if sample["metrics"]["pass_rows"] != 1 or sample["metrics"]["review_rows"] != 2 or sample["metrics"]["blocked_rows"] != 1:
        failures.append("sample_route_counts_wrong")
    card={"stage": STAGE, "stage_name": NAME, "passed": not failures, "authority": AUTHORITY_CLOSED, "metrics": {**AUTHORITY_CLOSED, "sample_rows": len(ROWS), "pass_rows": sample["metrics"]["pass_rows"], "review_rows": sample["metrics"]["review_rows"], "blocked_rows": sample["metrics"]["blocked_rows"], "failures": failures}, "artifacts": {"sample_card": str(sample_path.relative_to(ROOT)), "module": "scripts/patch_minimality_complexity_meter.py", "tests": "tests/test_patch_minimality_complexity_meter.py"}, "decision": "Patch minimality/complexity meter is ready as a no-execution gate for future patch/body objectives." if not failures else "Patch minimality/complexity meter readiness failed.", "next_best_step": "Attach patch_minimality_complexity_meter to central graph when commit/reconcile path is clear; recover coverage_test_selection next.", "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage8756 Patch Minimality Complexity Meter Readiness", "", f"Passed: `{card['passed']}`", "", "Recovered a no-execution patch gate for changed-line budget, file-count budget, complexity delta, public API touches, and new dependency/import risk.", "", "Authority remains closed. This does not authorize mining, training, decoder CE, denoise CE, runtime, scoring, or promotion.", ""]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)

if __name__ == "__main__":
    main()
