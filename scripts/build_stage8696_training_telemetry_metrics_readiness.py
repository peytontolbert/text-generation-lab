#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from training_telemetry_metrics import high_confidence_wrong_rows, row_field_telemetry, summarize_failure_buckets, token_loss_map

STAGE = 8696
NAME = "stage8696_v27_training_telemetry_metrics_readiness"
SUMMARY = ROOT / "runs/summaries/stage8696_training_telemetry_metrics_readiness.json"
ARTIFACT_DIR = ROOT / f"runs/local/artifacts/{NAME}"
DOC = ROOT / "docs/TRAINING_TELEMETRY_METRICS_READINESS_STAGE8696.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def run(cmd: list[str]) -> dict[str, Any]:
    result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    return {"cmd": cmd, "returncode": result.returncode, "passed": result.returncode == 0, "stdout": result.stdout[-4000:], "stderr": result.stderr[-4000:]}


def write_registry(summary: dict[str, Any]) -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8")) if REGISTRY.exists() else {"stages": []}
    stages = [row for row in registry.get("stages", []) if row.get("stage") != STAGE]
    stages.append({"stage": STAGE, "name": NAME, "summary_path": str(SUMMARY), "artifact_dir": str(ARTIFACT_DIR), "passed": summary["passed"], "authority_rows": summary["metrics"]["authority_rows"], "created_at": summary["created_at"]})
    registry["stages"] = sorted(stages, key=lambda row: int(row.get("stage", -1)))
    registry["latest_stage"] = STAGE
    registry["latest_name"] = NAME
    registry["latest_summary_path"] = str(SUMMARY)
    registry["updated_at"] = summary["created_at"]
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def doc(summary: dict[str, Any]) -> str:
    return f"""# Stage {STAGE}: Training Telemetry Metrics Readiness

## Result

- passed: `{summary['passed']}`
- tests passed: `{summary['checks']['tests']['passed']}`
- compile passed: `{summary['checks']['compile']['passed']}`
- high-confidence wrong sample count: `{len(summary['sample_metrics']['high_confidence_wrong_rows'])}`

## Recovered Metrics

- row-field margin/confidence/entropy
- high-confidence wrong row filtering
- per-token loss map schema
- failure bucket summary

## Boundary

This is a metrics/support module only. It does not authorize model execution, training, decoder CE, denoise CE, runtime, source/body emission, Gemma, controller merge, or promotion.

## Next

Attach telemetry to the central graph, then recover runtime verifier loop and gradient/activation interpretability on top of this telemetry schema.
"""


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    compile_result = run([sys.executable, "-m", "py_compile", "scripts/training_telemetry_metrics.py", "scripts/training_telemetry.py", "scripts/structured_telemetry_contract.py"])
    tests = run([sys.executable, "-m", "pytest", "-q", "tests/test_training_telemetry_metrics.py"])
    sample_rows = [
        row_field_telemetry("r1", "action", [0.1, 3.0], ["RETRIEVE", "CORRECT"], "RETRIEVE"),
        row_field_telemetry("r2", "action", [0.1, 3.0], ["RETRIEVE", "CORRECT"], "CORRECT"),
    ]
    token_map = token_loss_map("r2", [1, 2, 3], [0.1, 1.2, 0.4], token_texts=["def", "bad", ":"])
    sample_metrics = {
        "field_rows": sample_rows,
        "high_confidence_wrong_rows": high_confidence_wrong_rows(sample_rows, confidence_threshold=0.8),
        "token_loss_map": token_map,
        "failure_buckets": summarize_failure_buckets(sample_rows + [{"short_output": True, "correct": False, "confidence": 0.2}]),
    }
    passed = compile_result["passed"] and tests["passed"] and len(sample_metrics["high_confidence_wrong_rows"]) == 1
    summary: dict[str, Any] = {
        "stage": STAGE,
        "name": NAME,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "checks": {"compile": compile_result, "tests": tests},
        "sample_metrics": sample_metrics,
        "metrics": {
            "authority_rows": 0,
            "model_execution_authorized_next": 0,
            "decoder_ce_training_authorized_next": 0,
            "denoise_ce_training_authorized_next": 0,
            "runtime_authorized": 0,
            "source_body_authorized": 0,
            "gemma_authorized": 0,
            "promotion_authorized": 0,
        },
        "remaining_missing_modules": [
            "runtime_verifier_loop",
            "state_space_repo_state_compressor",
            "rubric_llm_judge_calibrator",
            "gradient_activation_interpretability",
            "central_graph_attachment_for_training_telemetry",
        ],
        "next_best_step": "Attach telemetry metrics to the central graph, then recover runtime verifier loop.",
        "authority": {"model_native_execution": False, "training": False, "runtime": False, "source_body": False, "gemma": False, "controller_merge": False, "promotion": False},
    }
    (ARTIFACT_DIR / "training_telemetry_metrics_card.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(doc(summary), encoding="utf-8")
    write_registry(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
