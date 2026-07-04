#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from rubric_judge_calibrator import calibration_card

STAGE = 8716
NAME = "stage8716_rubric_judge_calibrator_readiness"
OUT_DIR = ROOT / f"runs/local/artifacts/{NAME}"
SUMMARY = ROOT / "runs/summaries/stage8716_rubric_judge_calibrator_readiness.json"
DOC = ROOT / "docs/RUBRIC_JUDGE_CALIBRATOR_READINESS_STAGE8716.md"

AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}


def run(cmd: list[str]) -> dict[str, Any]:
    result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    return {"cmd": cmd, "returncode": result.returncode, "passed": result.returncode == 0, "stdout": result.stdout[-4000:], "stderr": result.stderr[-4000:]}


def sample_rows() -> list[dict[str, Any]]:
    return [
        {"row_id": "accept", "rubric": {"correctness": 1, "grounding": 1, "minimality": .9, "safety": 1, "style": .8, "test_plan": .8}, "judge_score": .9, "judge_confidence": .8, "verifier_pass": True},
        {"row_id": "repair", "rubric": {"correctness": .2, "grounding": .5, "minimality": .4, "safety": .7, "style": .6, "test_plan": .3}, "judge_score": .4, "judge_confidence": .7, "verifier_pass": False},
        {"row_id": "review", "rubric": {"correctness": .9, "grounding": .8, "minimality": .8, "safety": .9, "style": .8, "test_plan": .8}, "judge_score": .82, "judge_confidence": .7, "verifier_pass": False},
    ]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    compile_result = run([sys.executable, "-m", "py_compile", "scripts/rubric_judge_calibrator.py"])
    tests = run([sys.executable, "-m", "pytest", "-q", "tests/test_rubric_judge_calibrator.py"])
    sample = calibration_card(sample_rows())
    passed = compile_result["passed"] and tests["passed"] and sample["high_confidence_disagreement_rows"] == 0
    metrics = {
        "authority_rows": 0,
        "sample_rows": sample["rows"],
        "sample_verifier_disagreement_rows": sample["verifier_disagreement_rows"],
        "sample_high_confidence_disagreement_rows": sample["high_confidence_disagreement_rows"],
        "mean_brier": sample["mean_brier"],
        **AUTHORITY_CLOSED,
    }
    card = {
        "stage": STAGE,
        "name": NAME,
        "stage_name": NAME,
        "passed": passed,
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "checks": {"compile": compile_result, "tests": tests},
        "sample_calibration": sample,
        "decision": "Recovered deterministic rubric/verifier judge calibration; high-confidence judge/verifier disagreement blocks acceptance.",
        "next_best_step": "Attach rubric judge calibrator to central graph, then recover operator inventory/codelength interfaces.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "rubric_judge_calibrator_readiness_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT_DIR / "sample_rubric_judge_calibration.json").write_text(json.dumps(sample, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        f"# Stage {STAGE}: Rubric Judge Calibrator Readiness",
        "",
        f"Passed: `{passed}`",
        "",
        "Recovered calibration signals:",
        "",
        "- weighted rubric score",
        "- judge confidence",
        "- verifier disagreement",
        "- manual review route",
        "- quarantine for authority/leak risk",
        "",
        "Rubrics and LLM/teacher judges remain calibration signals only, not ground truth. Authority remains closed.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
