#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
    from scripts.build_stage9003_trainer_contract_dry_run_instance_design import (
        DRY_RUN_FLAGS,
        NO_EXECUTION_METRICS,
        REQUIRED_ASSERTIONS,
        REQUIRED_OUTPUTS,
    )
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from build_stage9003_trainer_contract_dry_run_instance_design import (  # type: ignore
        DRY_RUN_FLAGS,
        NO_EXECUTION_METRICS,
        REQUIRED_ASSERTIONS,
        REQUIRED_OUTPUTS,
    )

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9065
NAME = "stage9065_trainer_dry_run_input_refresh_after_long_context_controls"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9003 = ROOT / "runs/summaries/stage9003_trainer_contract_dry_run_instance_design.json"
SOURCE_9064 = ROOT / "runs/summaries/stage9064_training_readiness_refresh_after_long_context_controls.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRAINER_DRY_RUN_INPUT_REFRESH_AFTER_LONG_CONTEXT_CONTROLS_STAGE9065.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
DESIGN = OUT_DIR / "trainer_dry_run_input_refresh_after_long_context_controls.json"

REQUIRED_LONG_CONTEXT_INPUTS = [
    "long_context_compiler_handoff_blocker_audit.json",
    "long_context_loss_mask_compiler_preflight.json",
    "long_context_route_card_materialization_audit_contract.json",
    "training_readiness_refresh_after_long_context_controls.json",
]

FUTURE_DRY_RUN_INPUTS = [
    "locked_tiny_training_manifest.jsonl",
    "loss_mask_card.json",
    "manifest_schema_lock.json",
    "trainer_contract_dry_run_input.json",
    "contamination_and_leakage_proof.json",
    *REQUIRED_LONG_CONTEXT_INPUTS,
]

ADDITIONAL_ASSERTIONS = [
    "long_context_compiler_handoff_blocker_passed",
    "long_context_loss_mask_preflight_passed",
    "route_card_materialization_audit_passed_if_route_rows_present",
    "route_to_trainer_loss_translation_blocks_decoder_denoise_runtime",
    "no_long_context_rows_loaded_without_source_ticket",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_design(registry: dict[str, Any]) -> dict[str, Any]:
    source_9003 = load_json(SOURCE_9003)
    source_9064 = load_json(SOURCE_9064)
    assertions = list(dict.fromkeys([*REQUIRED_ASSERTIONS, *ADDITIONAL_ASSERTIONS]))
    outputs = list(dict.fromkeys([*REQUIRED_OUTPUTS, "long_context_gate_input_audit.json", "route_to_trainer_loss_translation_audit.json"]))
    checks = {
        "source_stage9003_present": SOURCE_9003.exists(),
        "source_stage9003_passed": source_9003.get("passed") is True,
        "source_stage9064_present": SOURCE_9064.exists(),
        "source_stage9064_passed": source_9064.get("passed") is True,
        "future_inputs_include_long_context_controls": set(REQUIRED_LONG_CONTEXT_INPUTS).issubset(set(FUTURE_DRY_RUN_INPUTS)),
        "required_flags_preserved": {"--manifest", "--mode", "--require-loss-mask-enforcement-audit", "--no-final-checkpoint-export"}.issubset(set(DRY_RUN_FLAGS)),
        "no_execution_assertions_preserved": {"dry_run_stops_before_model_forward", "no_model_weights_loaded", "no_optimizer_created", "no_backward_called"}.issubset(set(assertions)),
        "long_context_assertions_added": set(ADDITIONAL_ASSERTIONS).issubset(set(assertions)),
        "long_context_outputs_added": {"long_context_gate_input_audit.json", "route_to_trainer_loss_translation_audit.json"}.issubset(set(outputs)),
        "stage9064_training_still_blocked": (source_9064.get("metrics") or {}).get("training_ready") is False,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
        "registry_frontier_stage9064_or_followup": int((registry.get("metrics") or {}).get("latest_stage", -1)) in {9064, STAGE, 9066},
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "TRAINER_DRY_RUN_INPUT_REFRESH_NO_EXECUTION",
        "future_required_inputs": list(FUTURE_DRY_RUN_INPUTS),
        "dry_run_flags": list(DRY_RUN_FLAGS),
        "required_assertions": assertions,
        "required_outputs": outputs,
        "blocked_until": [
            "all future dry-run inputs exist",
            "long-context source/output ticket is granted if route rows are present",
            "Stage9061 compiler handoff blocker passes on materialized route cards",
            "Stage9062 route-to-trainer loss-mask preflight passes",
            "separate dry-run execution authorization stage passes",
        ],
        "checks": checks,
        "metrics": {
            "future_required_inputs": len(FUTURE_DRY_RUN_INPUTS),
            "required_long_context_inputs": len(REQUIRED_LONG_CONTEXT_INPUTS),
            "required_assertions": len(assertions),
            "required_outputs": len(outputs),
            "dry_run_instance_ready_to_execute": False,
            "dry_run_command_materialized_now": False,
            "long_context_inputs_materialized_now": False,
            **NO_EXECUTION_METRICS,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Trainer dry-run input contract now requires long-context compiler handoff and loss-mask preflight artifacts, but this stage does not run the trainer or load rows.",
    }


def validate_design(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9064, STAGE, 9066}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for required in REQUIRED_LONG_CONTEXT_INPUTS:
        if required not in card.get("future_required_inputs", []):
            failures.append(f"missing_long_context_input:{required}")
    for required in ADDITIONAL_ASSERTIONS:
        if required not in card.get("required_assertions", []):
            failures.append(f"missing_long_context_assertion:{required}")
    for key in [*NO_EXECUTION_METRICS.keys(), "dry_run_instance_ready_to_execute", "dry_run_command_materialized_now", "long_context_inputs_materialized_now"]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    design = build_design(registry)
    failures = validate_design(design, registry)
    DESIGN.write_text(json.dumps(design, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": 0, "failures": failures, **design["metrics"]},
        "artifacts": {"design": str(DESIGN.relative_to(ROOT))},
        "decision": design["decision"] if not failures else "Trainer dry-run input refresh after long-context controls failed.",
        "next_best_step": "Continue no-data recovery by auditing trainer dry-run input negative cases or refreshing the central graph/training docs; do not execute trainer.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9065 Trainer Dry-Run Input Refresh After Long-Context Controls",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Future trainer contract-only dry-run inputs must include Stage9061 compiler handoff and Stage9062 route-to-trainer loss-mask artifacts. This stage executes nothing.",
        "",
        f"Future required inputs: `{design['metrics']['future_required_inputs']}`",
        f"Dry-run ready now: `{design['metrics']['dry_run_instance_ready_to_execute']}`",
        "",
        f"Next: {summary['next_best_step']}",
    ]) + "\n", encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))), "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
