#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from cost_budget_scheduler import schedule_rows

STAGE = 8777
NAME = "stage8777_cost_budget_scheduler_readiness"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "COST_BUDGET_SCHEDULER_READINESS_STAGE8777.md"
AUTHORITY_CLOSED = {"model_execution_authorized_next": False, "decoder_ce_training_authorized_next": False, "denoise_ce_training_authorized_next": False, "runtime_authorized": False, "source_emission_authorized": False, "body_emission_authorized": False, "gemma_execution_authorized_next": False, "harness_execution_authorized_next": False, "scoring_authorized_next": False, "controller_complete_merge_authorized_next": False, "promotion_ready": False}
ROWS = [
    {"row_id": "retrieve", "used": {"tokens": 100}, "has_evidence": False},
    {"row_id": "exhausted", "used": {"tokens": 20000}},
    {"row_id": "verified", "used": {"tokens": 100}, "has_evidence": True, "tests_passed": True},
]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    test = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/test_cost_budget_scheduler.py"], cwd=ROOT, text=True, capture_output=True, check=False)
    sample = schedule_rows(ROWS, limits={"token_budget": 1000})
    sample_path = OUT_DIR / "cost_budget_scheduler_sample_card.json"
    sample_path.write_text(json.dumps(sample, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    failures=[]
    if test.returncode != 0:
        failures.append("unit_tests_failed")
    if sample["metrics"]["retrieve_rows"] != 1 or sample["metrics"]["stop_rows"] != 2:
        failures.append("sample_route_counts_wrong")
    card={"stage": STAGE, "stage_name": NAME, "passed": not failures, "authority": AUTHORITY_CLOSED, "metrics": {**AUTHORITY_CLOSED, "sample_rows": len(ROWS), "retrieve_rows": sample["metrics"]["retrieve_rows"], "stop_rows": sample["metrics"]["stop_rows"], "budget_ok_rows": sample["metrics"]["budget_ok_rows"], "failures": failures}, "artifacts": {"sample_card": str(sample_path.relative_to(ROOT)), "module": "scripts/cost_budget_scheduler.py", "tests": "tests/test_cost_budget_scheduler.py"}, "decision": "Cost budget scheduler is ready as a no-execution routing gate over token/tool/test/diff/time budgets." if not failures else "Cost budget scheduler readiness failed.", "next_best_step": "Attach cost_budget_scheduler to central graph when commit/reconcile path is clear; attach cost_budget_scheduler to central graph, then recover or attach static_analysis_security_scanner.", "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage8777 Cost Budget Scheduler Readiness", "", f"Passed: `{card['passed']}`", "", "Recovered a no-execution scheduler for token, tool-call, test, diff-line, and wall-time budgets. It emits continue/retrieve/hold/stop routes only.", "", "Authority remains closed. This does not execute tools, mine, train, score, or promote.", ""]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)

if __name__ == "__main__":
    main()
