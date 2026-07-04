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

from context_packer_v1 import evaluate_memory_items, pack_context

STAGE = 8694
NAME = "stage8694_v27_context_packer_lost_in_middle_readiness"
SUMMARY = ROOT / "runs/summaries/stage8694_context_packer_lost_in_middle_readiness.json"
ARTIFACT_DIR = ROOT / f"runs/local/artifacts/{NAME}"
DOC = ROOT / "docs/CONTEXT_PACKER_LOST_IN_MIDDLE_READINESS_STAGE8694.md"
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
    return f"""# Stage {STAGE}: Context Packer / Lost-In-Middle Readiness

## Result

- passed: `{summary['passed']}`
- packer test passed: `{summary['checks']['tests']['passed']}`
- required evidence selected: `{summary['sample_pack']['required_selected']}`
- selected count: `{summary['sample_pack']['selected_count']}`
- dropped count: `{summary['sample_pack']['dropped_count']}`
- memory contaminated ids: `{summary['memory_eval']['contaminated_ids']}`

## What This Recovers

- budgeted evidence packing
- deterministic lost-in-middle mitigation by putting high-value evidence at the front/back
- contamination/leak marker blocking before encoder context construction
- duplicate evidence suppression
- stale/duplicate/contaminated memory evaluation

## Boundary

This is a deterministic support module. It does not authorize model execution, training, decoder CE, denoise CE, runtime, source/body emission, Gemma, controller merge, or promotion.

## Next

Attach this module to the central graph, then recover training telemetry and runtime verifier loop.
"""


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)

    tests = run([sys.executable, "-m", "pytest", "-q", "tests/test_context_packer_v1.py"])
    compile_result = run([sys.executable, "-m", "py_compile", "scripts/context_packer_v1.py"])
    sample_rows = [
        {"item_id": "symbol", "text": "target symbol definition and binding evidence", "source_type": "symbol", "token_len": 8, "retrieval_score": 0.95, "grounding_score": 1.0, "required": True},
        {"item_id": "test", "text": "failing test assertion evidence", "source_type": "test", "token_len": 7, "retrieval_score": 0.9, "grounding_score": 1.0},
        {"item_id": "memory_old", "text": "stale prior trace", "source_type": "memory", "token_len": 6, "freshness_score": 0.1, "memory_score": 0.3},
        {"item_id": "leak", "text": "oracle expected_answer target_body", "source_type": "source", "token_len": 5, "retrieval_score": 1.0},
    ]
    sample_pack = pack_context(sample_rows, token_budget=20, min_required=1)
    memory_eval = evaluate_memory_items(sample_rows)
    passed = compile_result["passed"] and tests["passed"] and sample_pack["passed"] and "leak" in memory_eval["contaminated_ids"]
    summary: dict[str, Any] = {
        "stage": STAGE,
        "name": NAME,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "checks": {"compile": compile_result, "tests": tests},
        "sample_pack": {k: v for k, v in sample_pack.items() if k != "packed_text"},
        "memory_eval": memory_eval,
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
            "training_telemetry",
            "central_graph_attachment_for_context_packer",
        ],
        "next_best_step": "Attach context_packer_v1 to the central graph, then recover training telemetry.",
        "authority": {"model_native_execution": False, "training": False, "runtime": False, "source_body": False, "gemma": False, "controller_merge": False, "promotion": False},
    }
    (ARTIFACT_DIR / "context_packer_readiness_card.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(doc(summary), encoding="utf-8")
    write_registry(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
