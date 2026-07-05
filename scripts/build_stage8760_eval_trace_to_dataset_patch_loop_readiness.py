#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from eval_trace_to_dataset_patch_loop import build_patch_card

STAGE = 8760
NAME = "stage8760_eval_trace_to_dataset_patch_loop_readiness"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EVAL_TRACE_TO_DATASET_PATCH_LOOP_READINESS_STAGE8760.md"
AUTHORITY_CLOSED = {"model_execution_authorized_next": False, "training_authorized_next": False, "decoder_ce_training_authorized_next": False, "denoise_ce_training_authorized_next": False, "runtime_authorized": False, "source_emission_authorized": False, "body_emission_authorized": False, "gemma_execution_authorized_next": False, "harness_execution_authorized_next": False, "scoring_authorized_next": False, "controller_complete_merge_authorized_next": False, "promotion_ready": False}
ROWS = [
    {"row_id": "long", "target_over_decoder_budget": True},
    {"row_id": "leak", "leak_detected": True},
    {"row_id": "missing", "evidence_state": "missing"},
    {"row_id": "hcw", "high_confidence_wrong": True},
    {"row_id": "polarity", "prediction": "SAFE", "target": "UNSAFE"},
    {"row_id": "dup", "duplicate_semantic_key": True},
]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    test = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/test_eval_trace_to_dataset_patch_loop.py"], cwd=ROOT, text=True, capture_output=True, check=False)
    sample = build_patch_card(ROWS)
    sample_path = OUT_DIR / "eval_trace_to_dataset_patch_sample_card.json"
    sample_path.write_text(json.dumps(sample, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    failures=[]
    if test.returncode != 0:
        failures.append("unit_tests_failed")
    expected_actions = {"HOLDOUT_LONG_OUTPUT", "ADD_VERIFIER_REPAIR_ROW", "REQUEST_SOURCE_EVIDENCE", "RELABEL_OR_REVIEW", "ADD_COUNTERFACTUAL_NEIGHBOR", "DOWNWEIGHT_OR_PRUNE"}
    if set(sample["metrics"]["action_counts"]) != expected_actions:
        failures.append("sample_action_counts_wrong")
    card={"stage": STAGE, "stage_name": NAME, "passed": not failures, "authority": AUTHORITY_CLOSED, "metrics": {**AUTHORITY_CLOSED, "sample_rows": len(ROWS), "patches": sample["metrics"]["patches"], "valid_patch_actions": sample["metrics"]["valid_patch_actions"], "action_counts": sample["metrics"]["action_counts"], "failures": failures}, "artifacts": {"sample_card": str(sample_path.relative_to(ROOT)), "module": "scripts/eval_trace_to_dataset_patch_loop.py", "tests": "tests/test_eval_trace_to_dataset_patch_loop.py"}, "decision": "Eval trace to dataset patch loop is ready as a no-execution failure-to-curriculum repair contract." if not failures else "Eval trace to dataset patch loop readiness failed.", "next_best_step": "Attach eval_trace_to_dataset_patch_loop to central graph, then update source-backed builders to emit full gate_status cards.", "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage8760 Eval Trace To Dataset Patch Loop Readiness", "", f"Passed: `{card['passed']}`", "", "Recovered a no-execution loop that converts eval failures into dataset patch operations: add counterfactuals, add retrieval negatives, hold long output, add verifier repair rows, request source evidence, relabel/review, or prune/downweight.", "", "Authority remains closed.", ""]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)

if __name__ == "__main__":
    main()
