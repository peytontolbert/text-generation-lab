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

from gradient_activation_interpretability import _sample

STAGE = 8710
NAME = "stage8710_gradient_activation_interpretability_readiness"
OUT_DIR = ROOT / f"runs/local/artifacts/{NAME}"
SUMMARY = ROOT / "runs/summaries/stage8710_gradient_activation_interpretability_readiness.json"
DOC = ROOT / "docs/GRADIENT_ACTIVATION_INTERPRETABILITY_READINESS_STAGE8710.md"

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


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    compile_result = run([sys.executable, "-m", "py_compile", "scripts/gradient_activation_interpretability.py"])
    tests = run([sys.executable, "-m", "pytest", "-q", "tests/test_gradient_activation_interpretability.py"])
    sample = _sample()
    passed = compile_result["passed"] and tests["passed"] and sample["bundle"]["passed"]
    metrics = {
        "authority_rows": 0,
        "row_gradient_norms_present": sample["bundle"]["row_gradient_norms_present"],
        "module_delta_norms_present": sample["bundle"]["module_delta_norms_present"],
        "activation_cache_summary_present": sample["bundle"]["activation_cache_summary_present"],
        "feature_ablation_present": sample["bundle"]["feature_ablation_present"],
        "activation_patch_present": sample["bundle"]["activation_patch_present"],
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
        "sample_interpretability": sample,
        "decision": "Recovered deterministic gradient/activation interpretability telemetry helpers; no model execution or training authority opened.",
        "next_best_step": "Attach gradient/activation interpretability to central graph, then recover GNN repo encoder or rubric judge calibration.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "gradient_activation_interpretability_readiness_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT_DIR / "sample_gradient_activation_interpretability.json").write_text(json.dumps(sample, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        f"# Stage {STAGE}: Gradient/Activation Interpretability Readiness",
        "",
        f"Passed: `{passed}`",
        "",
        "Recovered deterministic telemetry helpers:",
        "",
        "- row gradient norm cards",
        "- module delta norm cards",
        "- activation cache summaries",
        "- feature ablation attribution cards",
        "- activation patch recovery cards",
        "",
        "This stage is non-executing. It does not authorize training, decoder CE, runtime, source/body emission, Gemma, harness/scoring, or promotion.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
