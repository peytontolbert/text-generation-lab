#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from ngram_repetition_style_detectors import detect_rows

STAGE = 8771
NAME = "stage8771_ngram_repetition_style_detectors_readiness"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "NGRAM_REPETITION_STYLE_DETECTORS_READINESS_STAGE8771.md"
AUTHORITY_CLOSED = {"model_execution_authorized_next": False, "decoder_ce_training_authorized_next": False, "denoise_ce_training_authorized_next": False, "runtime_authorized": False, "source_emission_authorized": False, "body_emission_authorized": False, "gemma_execution_authorized_next": False, "harness_execution_authorized_next": False, "scoring_authorized_next": False, "controller_complete_merge_authorized_next": False, "promotion_ready": False}
ROWS = [
    {"row_id": "ok", "code": "def add(a, b):\n    return a + b\n"},
    {"row_id": "rep", "text": "foo bar foo bar foo bar foo bar"},
    {"row_id": "warn", "code": "def f():\n  return 1\n"},
]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    test = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/test_ngram_repetition_style_detectors.py"], cwd=ROOT, text=True, capture_output=True, check=False)
    sample = detect_rows(ROWS)
    sample_path = OUT_DIR / "ngram_repetition_style_sample_card.json"
    sample_path.write_text(json.dumps(sample, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    failures=[]
    if test.returncode != 0:
        failures.append("unit_tests_failed")
    if sample["metrics"]["pass_rows"] != 1 or sample["metrics"]["review_rows"] != 1 or sample["metrics"]["warning_rows"] != 1:
        failures.append("sample_route_counts_wrong")
    card={"stage": STAGE, "stage_name": NAME, "passed": not failures, "authority": AUTHORITY_CLOSED, "metrics": {**AUTHORITY_CLOSED, "sample_rows": len(ROWS), "pass_rows": sample["metrics"]["pass_rows"], "review_rows": sample["metrics"]["review_rows"], "warning_rows": sample["metrics"]["warning_rows"], "failures": failures}, "artifacts": {"sample_card": str(sample_path.relative_to(ROOT)), "module": "scripts/ngram_repetition_style_detectors.py", "tests": "tests/test_ngram_repetition_style_detectors.py"}, "decision": "N-gram repetition/style detectors are ready as non-authority ranker features for decoder/denoise rows." if not failures else "N-gram repetition/style detector readiness failed.", "next_best_step": "Attach ngram_repetition_style_detectors to central graph when commit/reconcile path is clear; attach ngram_repetition_style_detectors to central graph, then recover or attach memory_retrieval_evaluator.", "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage8771 Ngram Repetition Style Detectors Readiness", "", f"Passed: `{card['passed']}`", "", "Recovered static n-gram repetition and style-anomaly features for code/text rows. These are non-authority ranker features, not decoder/generation authorization.", "", "Authority remains closed. This does not mine, train, score, generate, or promote.", ""]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)

if __name__ == "__main__":
    main()
