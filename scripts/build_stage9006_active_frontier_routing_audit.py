#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9006
NAME = "stage9006_active_frontier_routing_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ACTIVE_FRONTIER_ROUTING_AUDIT_STAGE9006.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "active_frontier_routing_audit.json"

SOURCE_SUMMARIES = {
    "stage8997": ROOT / "runs/summaries/stage8997_locked_tiny_manifest_compile_contract.json",
    "stage9003": ROOT / "runs/summaries/stage9003_trainer_contract_dry_run_instance_design.json",
    "stage9005": ROOT / "runs/summaries/stage9005_post_training_diagnostics_instance_blocker_audit.json",
}
SOURCE_ARTIFACTS = {
    "stage9003": ROOT / "runs/local/artifacts/stage9003_trainer_contract_dry_run_instance_design/trainer_contract_dry_run_instance_design.json",
    "stage9005": ROOT / "runs/local/artifacts/stage9005_post_training_diagnostics_instance_blocker_audit/post_training_diagnostics_instance_blocker_audit.json",
}

ACTIVE_IMMEDIATE_INPUTS = [
    "locked_tiny_training_manifest.jsonl",
    "loss_mask_card.json",
    "manifest_schema_lock.json",
    "trainer_contract_dry_run_input.json",
    "contamination_and_leakage_proof.json",
]

EXECUTION_ORDER = [
    "materialize_locked_manifest_artifacts_no_training",
    "audit_locked_manifest_artifacts",
    "authorize_trainer_contract_dry_run_only_if_inputs_exist",
    "execute_trainer_contract_dry_run_metadata_only",
    "audit_dry_run_outputs",
    "instantiate_one_run_training_ticket_only_if_dry_run_passes",
    "execute_tiny_training_only_if_separately_authorized",
    "run_post_training_diagnostics_only_after_training_telemetry_exists",
]

CURRENTLY_BLOCKED_OPERATIONS = [
    "trainer_dry_run_execution",
    "one_run_training_ticket_instantiation",
    "model_weight_load",
    "model_forward",
    "optimizer_creation",
    "backward",
    "checkpoint_write",
    "decoder_ce_training",
    "denoise_ce_training",
    "runtime_execution",
    "gemma_execution",
    "harness_scoring",
    "promotion",
    "arxiv_write",
]

FORBIDDEN_OPERATIONS = [
    "RUN_TRAINER_DRY_RUN_NOW",
    "RUN_ONE_TRAINING_NOW",
    "READ_DATASET_ROW_BODIES_NOW",
    "LOAD_MODEL_WEIGHTS_NOW",
    "WRITE_CHECKPOINT_NOW",
    "PROMOTE_MODEL",
    "MERGE_MODEL",
    "WRITE_TO_ARXIV",
    "RUN_RUNTIME",
    "RUN_GEMMA",
    "RUN_HARNESS_SCORING",
    "AUTHORIZE_DECODER_CE",
    "AUTHORIZE_DENOISE_CE",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_audit(registry: dict[str, Any]) -> dict[str, Any]:
    summaries = {key: load_json(path) for key, path in SOURCE_SUMMARIES.items()}
    artifacts = {key: load_json(path) for key, path in SOURCE_ARTIFACTS.items()}
    stage9003_metrics = summaries["stage9003"].get("metrics") or {}
    stage9005_metrics = summaries["stage9005"].get("metrics") or {}
    checks = {
        "source_stage8997_present": SOURCE_SUMMARIES["stage8997"].exists(),
        "source_stage8997_passed": summaries["stage8997"].get("passed") is True,
        "source_stage9003_present": SOURCE_SUMMARIES["stage9003"].exists() and SOURCE_ARTIFACTS["stage9003"].exists(),
        "source_stage9003_passed": summaries["stage9003"].get("passed") is True,
        "source_stage9003_keeps_dry_run_blocked": stage9003_metrics.get("dry_run_instance_ready_to_execute") is False,
        "source_stage9003_records_required_inputs": set(ACTIVE_IMMEDIATE_INPUTS).issubset(set(artifacts["stage9003"].get("future_required_inputs") or [])),
        "source_stage9005_present": SOURCE_SUMMARIES["stage9005"].exists() and SOURCE_ARTIFACTS["stage9005"].exists(),
        "source_stage9005_passed": summaries["stage9005"].get("passed") is True,
        "source_stage9005_is_future_blocker": stage9005_metrics.get("diagnostics_instance_ready") is False and stage9005_metrics.get("missing_future_artifacts", 0) > 0,
        "active_inputs_recorded": len(ACTIVE_IMMEDIATE_INPUTS) >= 5,
        "execution_order_recorded": len(EXECUTION_ORDER) >= 8,
        "blocked_operations_recorded": len(CURRENTLY_BLOCKED_OPERATIONS) >= 14,
        "forbidden_operations_recorded": len(FORBIDDEN_OPERATIONS) >= 13,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "ACTIVE_FRONTIER_ROUTING_AUDIT_NO_EXECUTION",
        "indexed_frontier": {
            "stage": 9005,
            "role": "future_post_training_diagnostics_blocker",
            "does_not_change_active_pre_training_path": True,
        },
        "active_immediate_frontier": {
            "stage": 9003,
            "role": "trainer_contract_dry_run_instance_design",
            "next_required_action": "materialize_locked_manifest_loss_mask_schema_and_leakage_artifacts_without_training",
        },
        "active_immediate_inputs": ACTIVE_IMMEDIATE_INPUTS,
        "execution_order": EXECUTION_ORDER,
        "currently_blocked_operations": CURRENTLY_BLOCKED_OPERATIONS,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "checks": checks,
        "metrics": {
            "active_immediate_inputs": len(ACTIVE_IMMEDIATE_INPUTS),
            "execution_order_steps": len(EXECUTION_ORDER),
            "currently_blocked_operations": len(CURRENTLY_BLOCKED_OPERATIONS),
            "future_guardrails_present": True,
            "active_frontier_routed": True,
            "trainer_dry_run_execution_authorized_now": False,
            "training_ticket_instantiation_authorized_now": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "dataset_row_body_load_authorized": False,
            "model_execution_attempted": False,
            "model_weights_loaded": False,
            "optimizer_created": False,
            "checkpoint_written": False,
            "runtime_authorized_flag": False,
            "gemma_execution_attempted": False,
            "harness_scoring_attempted": False,
            "promotion_authorized": False,
            "arxiv_write_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Stage9005 is retained as a future post-training diagnostics blocker, but the active immediate path remains pre-training artifact materialization for Stage9003. No execution or training is authorized.",
    }


def validate_audit(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    if (card.get("indexed_frontier") or {}).get("role") != "future_post_training_diagnostics_blocker":
        failures.append("indexed_frontier_role")
    if (card.get("active_immediate_frontier") or {}).get("stage") != 9003:
        failures.append("active_immediate_frontier_stage")
    for required in ACTIVE_IMMEDIATE_INPUTS:
        if required not in card.get("active_immediate_inputs", []):
            failures.append(f"missing_active_input:{required}")
    for key in [
        "trainer_dry_run_execution_authorized_now",
        "training_ticket_instantiation_authorized_now",
        "training_authorized",
        "data_mining_authorized",
        "dataset_row_body_load_authorized",
        "model_execution_attempted",
        "model_weights_loaded",
        "optimizer_created",
        "checkpoint_written",
        "runtime_authorized_flag",
        "gemma_execution_attempted",
        "harness_scoring_attempted",
        "promotion_authorized",
        "arxiv_write_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_audit(registry)
    failures = validate_audit(card)
    AUDIT.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": 0, "failures": failures, **card["metrics"]},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "Build the no-training locked manifest artifact materialization ticket for Stage9003 inputs; do not execute trainer dry run, training, mining, runtime, Gemma, harness, or /arxiv writes.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9006 Active Frontier Routing Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage clarifies that Stage9005 is a future post-training diagnostics blocker, while the active immediate pre-training path remains Stage9003 input materialization.",
        "",
        f"Active immediate frontier: `{card['active_immediate_frontier']['stage']}`",
        f"Indexed future guardrail: `{card['indexed_frontier']['stage']}`",
        f"Trainer dry-run execution authorized now: `{summary['metrics']['trainer_dry_run_execution_authorized_now']}`",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))),
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage9006 Active Frontier Routing Audit"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "- Clarifies that Stage9005 is a future post-training diagnostics blocker, not the immediate pre-training execution path.",
            "- Routes the active next step back to Stage9003 input materialization: locked tiny manifest, loss mask, schema lock, trainer dry-run input, and contamination/leakage proof.",
            "- Keeps dry-run execution, training, model execution, mining, runtime, Gemma, harness scoring, promotion, and /arxiv writes closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
