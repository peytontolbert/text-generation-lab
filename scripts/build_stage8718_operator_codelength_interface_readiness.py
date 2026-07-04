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

from operator_codelength_interface import codelength_card, operator_inventory

STAGE = 8718
NAME = "stage8718_operator_codelength_interface_readiness"
OUT_DIR = ROOT / f"runs/local/artifacts/{NAME}"
SUMMARY = ROOT / "runs/summaries/stage8718_operator_codelength_interface_readiness.json"
DOC = ROOT / "docs/OPERATOR_CODELENGTH_INTERFACE_READINESS_STAGE8718.md"

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
    compile_result = run([sys.executable, "-m", "py_compile", "scripts/operator_codelength_interface.py"])
    tests = run([sys.executable, "-m", "pytest", "-q", "tests/test_operator_codelength_interface.py"])
    inventory = operator_inventory()
    code = codelength_card([
        {"row_id": "easy", "probabilities": [0.05, 0.9, 0.03, 0.02], "target_index": 1},
        {"row_id": "hard", "probabilities": [0.4, 0.3, 0.2, 0.1], "target_index": 1},
    ])
    passed = compile_result["passed"] and tests["passed"] and inventory["operator_count"] >= 80 and code["rows"] == 2
    metrics = {"authority_rows": 0, "operator_count": inventory["operator_count"], "category_count": inventory["category_count"], "sample_rows": code["rows"], "sample_exact": code["exact"], "sample_compression_gain_bits": code["compression_gain_bits"], **AUTHORITY_CLOSED}
    card = {"stage": STAGE, "name": NAME, "stage_name": NAME, "passed": passed, "authority": AUTHORITY_CLOSED, "metrics": metrics, "checks": {"compile": compile_result, "tests": tests}, "operator_inventory": inventory, "sample_codelength": code, "decision": "Recovered operator inventory and codelength interfaces for candidate selection/compression evaluation; no model execution or scoring authority opened.", "next_best_step": "Attach operator/codelength interfaces to central graph, then run a module gap review before data mining resumes.", "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (OUT_DIR / "operator_codelength_interface_readiness_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT_DIR / "operator_inventory.json").write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT_DIR / "sample_codelength_card.json").write_text(json.dumps(code, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([f"# Stage {STAGE}: Operator/Codelength Interface Readiness", "", f"Passed: `{passed}`", "", f"Operators: `{inventory['operator_count']}`", f"Categories: `{inventory['category_count']}`", "", "Recovered probability/codelength metrics: uniform bits, model NLL bits, compression gain, exact choice, and bits per row.", "", "This is a measurement interface only. It does not authorize model execution, scoring, training, runtime, Gemma, or promotion.", ""]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
