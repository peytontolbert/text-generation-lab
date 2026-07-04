#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from target_implementation_guard import (  # noqa: E402
    DEFAULT_TARGET_CONFIG,
    REQUIRED_FEATURES,
    evaluate_implementation_selection,
)

STAGE = 8688
NAME = "stage8688_v27_target_implementation_guard_readiness"
SUMMARY = ROOT / "runs/summaries/stage8688_target_implementation_guard_readiness.json"
ARTIFACT_DIR = ROOT / f"runs/local/artifacts/{NAME}"
DOC = ROOT / "docs/TARGET_IMPLEMENTATION_GUARD_READINESS_STAGE8688.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def _load_registry() -> dict[str, Any]:
    if REGISTRY.exists():
        return json.loads(REGISTRY.read_text(encoding="utf-8"))
    return {"stages": []}


def _write_registry(summary: dict[str, Any]) -> None:
    registry = _load_registry()
    stages = list(registry.get("stages") or [])
    stages = [row for row in stages if row.get("stage") != STAGE]
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


def _doc(summary: dict[str, Any]) -> str:
    transformer = summary["checks"]["transformer"]
    scaffold = summary["checks"]["scaffold"]
    missing = "\n".join(f"- `{item}`" for item in summary["remaining_missing_modules"])
    return f"""# Stage {STAGE}: Target Implementation Guard Readiness

## Result

- passed: `{summary["passed"]}`
- transformer allowed: `{transformer["allowed_for_recovered_100m_target"]}`
- scaffold blocked: `{not scaffold["allowed_for_recovered_100m_target"]}`
- transformer missing recovered features: `{transformer["missing_features"]}`
- scaffold missing recovered features: `{scaffold["missing_features"]}`
- authority rows: `{summary["metrics"]["authority_rows"]}`

## Decision

The recovered 100M target requires the transformer implementation, not the legacy GRU scaffold.

The earlier documentation that said recovered implementation features were missing is now scoped correctly:
those features are missing from `legacy_src/agentkernel_lite/modeling.py`, but present in
`legacy_src/agentkernel_lite/modeling_transformer.py`.

## Guarded Features

{chr(10).join(f"- `{item}`" for item in REQUIRED_FEATURES)}

## Still Missing After This Stage

{missing}

## Closed Authority

This stage does not authorize training, decoder CE, source/body emission, runtime execution, Gemma comparison,
harness scoring, controller merge, or promotion.
"""


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)

    transformer = evaluate_implementation_selection("transformer")
    scaffold = evaluate_implementation_selection("scaffold")
    unknown = evaluate_implementation_selection("unknown")

    passed = (
        transformer["allowed_for_recovered_100m_target"] is True
        and transformer["missing_features"] == []
        and scaffold["allowed_for_recovered_100m_target"] is False
        and set(scaffold["missing_features"]) == set(REQUIRED_FEATURES)
        and unknown["allowed_for_recovered_100m_target"] is False
    )

    created_at = datetime.now(timezone.utc).isoformat()
    summary: dict[str, Any] = {
        "stage": STAGE,
        "name": NAME,
        "created_at": created_at,
        "passed": passed,
        "target_config": str(DEFAULT_TARGET_CONFIG),
        "checks": {
            "transformer": transformer,
            "scaffold": scaffold,
            "unknown": unknown,
        },
        "metrics": {
            "authority_rows": 0,
            "decoder_ce_authorized": 0,
            "runtime_authorized": 0,
            "source_body_authorized": 0,
            "gemma_authorized": 0,
            "promotion_authorized": 0,
            "transformer_missing_feature_count": len(transformer["missing_features"]),
            "scaffold_missing_feature_count": len(scaffold["missing_features"]),
        },
        "remaining_missing_modules": [
            "runtime_verifier_loop",
            "context_packer_lost_in_middle_memory_retrieval",
            "state_space_repo_state_compressor",
            "rubric_llm_judge_calibrator",
            "training_telemetry",
            "trainer_integration_for_target_implementation_guard",
        ],
        "next_best_step": (
            "Integrate target_implementation_guard into the bounded trainer contract so recovered target "
            "runs cannot silently select the scaffold implementation; then recover context-packer/lost-in-middle."
        ),
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

    (ARTIFACT_DIR / "target_implementation_guard_card.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(_doc(summary), encoding="utf-8")
    _write_registry(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
