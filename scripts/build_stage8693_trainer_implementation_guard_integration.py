#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
TESTS = [
    ROOT / "tests/test_recovered_trainer_contract.py",
    ROOT / "tests/test_target_implementation_guard.py",
]
SUMMARY = ROOT / "runs/summaries/stage8693_trainer_implementation_guard_integration.json"
NAME = "stage8693_v27_trainer_implementation_guard_integration"
ARTIFACT_DIR = ROOT / f"runs/local/artifacts/{NAME}"
DOC = ROOT / "docs/TRAINER_IMPLEMENTATION_GUARD_INTEGRATION_STAGE8693.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
STAGE = 8693


def run(cmd: list[str]) -> dict[str, Any]:
    result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    return {
        "cmd": cmd,
        "returncode": result.returncode,
        "stdout": result.stdout[-4000:],
        "stderr": result.stderr[-4000:],
        "passed": result.returncode == 0,
    }


def load_registry() -> dict[str, Any]:
    if REGISTRY.exists():
        return json.loads(REGISTRY.read_text(encoding="utf-8"))
    return {"stages": []}


def write_registry(summary: dict[str, Any]) -> None:
    registry = load_registry()
    stages = [row for row in registry.get("stages", []) if row.get("stage") != STAGE]
    stages.append(
        {
            "stage": STAGE,
            "name": NAME,
            "summary_path": str(SUMMARY),
            "artifact_dir": str(ARTIFACT_DIR),
            "passed": summary["passed"],
            "authority_rows": summary["metrics"]["authority_rows"],
            "created_at": summary["created_at"],
        }
    )
    registry["stages"] = sorted(stages, key=lambda row: int(row.get("stage", -1)))
    registry["latest_stage"] = STAGE
    registry["latest_name"] = NAME
    registry["latest_summary_path"] = str(SUMMARY)
    registry["updated_at"] = summary["created_at"]
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def doc(summary: dict[str, Any]) -> str:
    return f"""# Stage {STAGE}: Trainer Implementation Guard Integration

## Result

- passed: `{summary['passed']}`
- trainer default implementation is transformer: `{summary['checks']['default_transformer']}`
- trainer imports target guard: `{summary['checks']['imports_guard']}`
- contract embeds guard output: `{summary['checks']['embeds_guard']}`
- scaffold rejection test present: `{summary['checks']['scaffold_rejection_test_present']}`
- tests passed: `{summary['checks']['tests']['passed']}`

## Decision

The target implementation guard is now wired into `legacy_src/scripts/train_agentkernel_lite_encdec.py`.
Recovered-target probe contracts no longer accept the legacy GRU scaffold as a valid implementation.

## Closed Authority

This stage does not authorize model execution, decoder CE, source/body emission, runtime, Gemma, controller merge, or promotion.

## Next

Recover the context packer / lost-in-middle / memory-retrieval evaluator next, then training telemetry.
"""


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)

    trainer_text = TRAINER.read_text(encoding="utf-8")
    test_text = "\n".join(path.read_text(encoding="utf-8") for path in TESTS)
    compile_result = run([sys.executable, "-m", "py_compile", str(TRAINER.relative_to(ROOT))])
    tests_result = run([sys.executable, "-m", "pytest", "-q", "tests/test_recovered_trainer_contract.py", "tests/test_target_implementation_guard.py"])

    checks = {
        "default_transformer": 'default="transformer"' in trainer_text,
        "imports_guard": "from target_implementation_guard import evaluate_implementation_selection" in trainer_text,
        "embeds_guard": '"target_implementation_guard": implementation_guard' in trainer_text,
        "scaffold_rejection_test_present": "test_contract_rejects_scaffold_for_recovered_target" in test_text,
        "compile": compile_result,
        "tests": tests_result,
    }
    passed = all(
        bool(checks[key])
        for key in ("default_transformer", "imports_guard", "embeds_guard", "scaffold_rejection_test_present")
    ) and compile_result["passed"] and tests_result["passed"]

    summary: dict[str, Any] = {
        "stage": STAGE,
        "name": NAME,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "checks": checks,
        "metrics": {
            "authority_rows": 0,
            "model_execution_authorized_next": 0,
            "decoder_ce_training_authorized_next": 0,
            "runtime_authorized": 0,
            "source_body_authorized": 0,
            "gemma_authorized": 0,
            "promotion_authorized": 0,
        },
        "remaining_missing_modules": [
            "runtime_verifier_loop",
            "context_packer_lost_in_middle_memory_retrieval",
            "state_space_repo_state_compressor",
            "rubric_llm_judge_calibrator",
            "training_telemetry",
        ],
        "next_best_step": "Recover context packer/lost-in-middle/memory retrieval evaluator, then training telemetry.",
        "authority": {
            "model_native_execution": False,
            "decoder_ce": False,
            "runtime": False,
            "source_body": False,
            "gemma": False,
            "controller_merge": False,
            "promotion": False,
        },
    }
    (ARTIFACT_DIR / "trainer_implementation_guard_integration_card.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(doc(summary), encoding="utf-8")
    write_registry(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
