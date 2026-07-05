#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from eval_trace_to_dataset_patch_loop import compile_traces

STAGE = 8768
NAME = "stage8768_eval_trace_to_dataset_patch_loop_v2_readiness"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EVAL_TRACE_TO_DATASET_PATCH_LOOP_V2_READINESS_STAGE8768.md"
AUTHORITY_CLOSED = {"model_execution_authorized_next": False, "decoder_ce_training_authorized_next": False, "denoise_ce_training_authorized_next": False, "runtime_authorized": False, "source_emission_authorized": False, "body_emission_authorized": False, "gemma_execution_authorized_next": False, "harness_execution_authorized_next": False, "scoring_authorized_next": False, "controller_complete_merge_authorized_next": False, "promotion_ready": False}
TRACES = [
    {"trace_id": "retrieval_gap", "failure_type": "missing_evidence", "slice_tags": ["retrieval"]},
    {"trace_id": "minimality", "failure_type": "overbroad_patch", "slice_tags": ["patch"]},
    {"trace_id": "locked", "failure_type": "bad_label", "locked_eval_trace": True},
]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    test = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/test_eval_trace_to_dataset_patch_loop.py"], cwd=ROOT, text=True, capture_output=True, check=False)
    sample = compile_traces(TRACES)
    sample_path = OUT_DIR / "eval_trace_to_dataset_patch_sample_card.json"
    sample_path.write_text(json.dumps(sample, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    failures=[]
    if test.returncode != 0:
        failures.append("unit_tests_failed")
    if sample["metrics"]["proposed_patches"] != 2 or sample["metrics"]["blocked_patches"] != 1:
        failures.append("sample_route_counts_wrong")
    card={"stage": STAGE, "stage_name": NAME, "passed": not failures, "authority": AUTHORITY_CLOSED, "metrics": {**AUTHORITY_CLOSED, "sample_traces": len(TRACES), "proposed_patches": sample["metrics"]["proposed_patches"], "blocked_patches": sample["metrics"]["blocked_patches"], "failures": failures}, "artifacts": {"sample_card": str(sample_path.relative_to(ROOT)), "module": "scripts/eval_trace_to_dataset_patch_loop.py", "tests": "tests/test_eval_trace_to_dataset_patch_loop.py"}, "decision": "Eval-trace-to-dataset-patch loop is ready as a no-generation audit compiler from failures to dataset patch operations." if not failures else "Eval-trace-to-dataset-patch readiness failed.", "next_best_step": "Attach eval_trace_to_dataset_patch_loop to central graph when commit/reconcile path is clear; recover or attach skill_tool_registry next.", "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage8768 Eval Trace To Dataset Patch Loop V2 Readiness", "", f"Passed: `{card['passed']}`", "", "Recovered a no-generation compiler from eval/failure traces to auditable dataset patch operations: add, relabel, rebalance, quarantine, counterfactual, preference-pair, holdout, or route-change.", "", "Locked/hidden eval traces and traces containing target answers are blocked from becoming training patches.", "", "Authority remains closed. This does not mine, generate rows, train, score, run runtime, or promote.", ""]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)

if __name__ == "__main__":
    main()
