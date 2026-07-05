#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from schema_drift_detector import audit_rows

STAGE = 8754
NAME = "stage8754_schema_drift_detector_readiness"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SCHEMA_DRIFT_DETECTOR_READINESS_STAGE8754.md"
AUTHORITY_CLOSED = {"model_execution_authorized_next": False, "decoder_ce_training_authorized_next": False, "denoise_ce_training_authorized_next": False, "runtime_authorized": False, "source_emission_authorized": False, "body_emission_authorized": False, "gemma_execution_authorized_next": False, "harness_execution_authorized_next": False, "scoring_authorized_next": False, "controller_complete_merge_authorized_next": False, "promotion_ready": False}
SCHEMA = {"required_fields": ["row_id", "split", "gate_status"], "optional_fields": ["source_id", "objective_family"], "forbidden_fields": ["clean_state", "target_label", "raw_source_body"], "typed_fields": {"row_id": "str", "split": "str", "gate_status": "dict"}, "aliases": {"package_split": "split", "gateStatus": "gate_status"}, "allow_unknown_fields": False}
ROWS = [
    {"row_id": "ok", "split": "train", "gate_status": {}, "source_id": "s"},
    {"row_id": "review_missing_gate", "split": "train"},
    {"row_id": "block_target", "split": "train", "gate_status": {}, "target_label": "COPY_PRIOR"},
    {"row_id": "block_alias_collision", "split": "train", "package_split": "eval", "gate_status": {}},
]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    test = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/test_schema_drift_detector.py"], cwd=ROOT, text=True, capture_output=True, check=False)
    sample = audit_rows(ROWS, SCHEMA)
    sample_path = OUT_DIR / "schema_drift_sample_card.json"
    schema_path = OUT_DIR / "schema_drift_sample_schema.json"
    sample_path.write_text(json.dumps(sample, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    schema_path.write_text(json.dumps(SCHEMA, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    failures=[]
    if test.returncode != 0:
        failures.append("unit_tests_failed")
    if sample["metrics"]["pass_rows"] != 1 or sample["metrics"]["review_rows"] != 1 or sample["metrics"]["blocked_rows"] != 2:
        failures.append("sample_route_counts_wrong")
    card={"stage": STAGE, "stage_name": NAME, "passed": not failures, "authority": AUTHORITY_CLOSED, "metrics": {**AUTHORITY_CLOSED, "sample_rows": len(ROWS), "pass_rows": sample["metrics"]["pass_rows"], "review_rows": sample["metrics"]["review_rows"], "blocked_rows": sample["metrics"]["blocked_rows"], "failures": failures}, "artifacts": {"sample_card": str(sample_path.relative_to(ROOT)), "sample_schema": str(schema_path.relative_to(ROOT)), "module": "scripts/schema_drift_detector.py", "tests": "tests/test_schema_drift_detector.py"}, "decision": "Schema drift detector is ready as a no-execution manifest gate for alias/schema parity before compiler ingestion." if not failures else "Schema drift detector readiness failed.", "next_best_step": "Attach schema_drift_detector to central graph when commit/reconcile path is clear; then recover patch_minimality_complexity_meter or coverage_test_selection.", "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage8754 Schema Drift Detector Readiness", "", f"Passed: `{card['passed']}`", "", "Recovered a reusable no-execution manifest gate for required fields, aliases, forbidden target/source fields, type mismatches, invalid splits, and alias collisions.", "", "Authority remains closed. This does not authorize mining, training, decoder CE, denoise CE, runtime, scoring, or promotion.", ""]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)

if __name__ == "__main__":
    main()
