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
STAGE = 9000
NAME = "stage9000_one_run_bounded_training_ticket_contract"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ONE_RUN_BOUNDED_TRAINING_TICKET_CONTRACT_STAGE9000.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT = OUT_DIR / "one_run_bounded_training_ticket_contract.json"

SOURCE_SUMMARY = ROOT / "runs/summaries/stage8999_trainer_contract_dry_run_contract.json"
SOURCE_CONTRACT = ROOT / "runs/local/artifacts/stage8999_trainer_contract_dry_run_contract/trainer_contract_dry_run_contract.json"

REQUIRED_INPUTS = [
    "trainer_contract_dry_run_report.json",
    "loss_mask_enforcement_audit.json",
    "telemetry_artifact_plan.json",
    "no_model_forward_proof.json",
    "no_training_execution_proof.json",
    "next_one_run_training_ticket_input.json",
]

TICKET_FIELDS = [
    "ticket_id",
    "source_dry_run_stage",
    "manifest_ref",
    "loss_mask_card_ref",
    "allowed_mode",
    "max_train_rows",
    "max_eval_rows",
    "max_strict_rows",
    "max_steps",
    "max_wall_seconds",
    "allowed_loss_weights",
    "output_dir",
    "required_telemetry_outputs",
    "cleanup_policy",
    "rollback_policy",
    "post_run_gate",
]

BOUNDED_LIMITS = {
    "max_train_rows": 128,
    "max_eval_rows": 64,
    "max_strict_rows": 64,
    "max_steps": 20,
    "max_wall_seconds": 600,
    "max_checkpoints_retained": 0,
}

REQUIRED_POST_RUN_TELEMETRY = [
    "training_run_card.json",
    "loss_curve.jsonl",
    "per_field_metrics.json",
    "confusion_matrices.json",
    "high_confidence_wrong_rows.jsonl",
    "loss_mask_enforcement_runtime_audit.json",
    "gradient_norm_summary.json",
    "checkpoint_cleanup_proof.json",
    "promotion_blocker_report.json",
]

FORBIDDEN_OPERATIONS = [
    "TRAINING_EXECUTION_NOW",
    "FINAL_CHECKPOINT_EXPORT",
    "PROMOTION",
    "MODEL_MERGE",
    "RUNTIME_EXECUTION",
    "GEMMA_EXECUTION",
    "HARNESS_SCORING",
    "SOURCE_BODY_EMISSION",
    "BODY_EMISSION",
    "WRITE_TO_ARXIV",
    "USE_LOCKED_EVAL_FOR_TRAINING",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_contract(registry: dict[str, Any]) -> dict[str, Any]:
    source_summary = load_json(SOURCE_SUMMARY)
    source_contract = load_json(SOURCE_CONTRACT)
    checks = {
        "source_stage8999_present": SOURCE_SUMMARY.exists() and SOURCE_CONTRACT.exists(),
        "source_stage8999_passed": source_summary.get("passed") is True,
        "source_stage8999_dry_run_closed": (source_summary.get("metrics") or {}).get("trainer_dry_run_authorized_now") is False,
        "source_stage8999_emits_next_ticket_input": "next_one_run_training_ticket_input.json" in (source_contract.get("required_telemetry_outputs") or []),
        "required_inputs_recorded": len(REQUIRED_INPUTS) >= 6,
        "ticket_fields_recorded": len(TICKET_FIELDS) >= 16,
        "bounded_limits_recorded": len(BOUNDED_LIMITS) >= 6,
        "post_run_telemetry_recorded": len(REQUIRED_POST_RUN_TELEMETRY) >= 9,
        "forbidden_operations_recorded": len(FORBIDDEN_OPERATIONS) >= 11,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "ONE_RUN_BOUNDED_TRAINING_TICKET_CONTRACT_NO_EXECUTION",
        "required_inputs": REQUIRED_INPUTS,
        "ticket_fields": TICKET_FIELDS,
        "bounded_limits": BOUNDED_LIMITS,
        "required_post_run_telemetry": REQUIRED_POST_RUN_TELEMETRY,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "allowed_future_loss_weights": {
            "structured_aux": "ticket_explicit_only",
            "decoder_ce": "ticket_explicit_only_and_row_loss_mask_required",
            "denoise_ce": "ticket_explicit_only_and_row_loss_mask_required",
            "runtime_reward": "closed",
            "gemma_distill": "closed",
        },
        "checks": checks,
        "metrics": {
            "required_inputs": len(REQUIRED_INPUTS),
            "ticket_fields": len(TICKET_FIELDS),
            "bounded_limits": len(BOUNDED_LIMITS),
            "required_post_run_telemetry": len(REQUIRED_POST_RUN_TELEMETRY),
            "forbidden_operations": len(FORBIDDEN_OPERATIONS),
            "training_ticket_authorized_now": False,
            "training_executed_now": False,
            "final_checkpoint_export_authorized": False,
            "promotion_authorized": False,
            "model_merge_authorized": False,
            "dataset_rows_loaded": False,
            "repository_source_bodies_loaded": False,
            "arxiv_write_authorized": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "model_execution_attempted": False,
            "runtime_authorized_flag": False,
            "gemma_execution_attempted": False,
            "harness_scoring_attempted": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "One-run bounded training is specified as a future ticket contract only. This stage records exact inputs, limits, telemetry, and cleanup requirements, but does not authorize or execute training.",
    }


def validate_contract(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    limits = card.get("bounded_limits") or {}
    if limits.get("max_train_rows", 999999) > 128:
        failures.append("max_train_rows_too_high")
    if limits.get("max_steps", 999999) > 20:
        failures.append("max_steps_too_high")
    if limits.get("max_checkpoints_retained", 1) != 0:
        failures.append("checkpoints_retained_not_zero")
    for required in ["high_confidence_wrong_rows.jsonl", "gradient_norm_summary.json", "checkpoint_cleanup_proof.json", "promotion_blocker_report.json"]:
        if required not in card.get("required_post_run_telemetry", []):
            failures.append(f"missing_telemetry:{required}")
    for key in [
        "training_ticket_authorized_now",
        "training_executed_now",
        "final_checkpoint_export_authorized",
        "promotion_authorized",
        "model_merge_authorized",
        "dataset_rows_loaded",
        "repository_source_bodies_loaded",
        "arxiv_write_authorized",
        "training_authorized",
        "data_mining_authorized",
        "model_execution_attempted",
        "runtime_authorized_flag",
        "gemma_execution_attempted",
        "harness_scoring_attempted",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_contract(registry)
    failures = validate_contract(card)
    CONTRACT.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": 0, "failures": failures, **card["metrics"]},
        "artifacts": {"contract": str(CONTRACT.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "After a future trainer contract-only dry run executes and passes, instantiate exactly one bounded training ticket. This stage does not authorize that run.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9000 One-Run Bounded Training Ticket Contract",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage defines a future one-run bounded training ticket contract. It does not execute training, load rows, export checkpoints, promote, merge, score, or authorize decoder/denoise CE now.",
        "",
        f"Max train rows: `{BOUNDED_LIMITS['max_train_rows']}`",
        f"Max steps: `{BOUNDED_LIMITS['max_steps']}`",
        f"Training authorized now: `{summary['metrics']['training_authorized']}`",
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
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
