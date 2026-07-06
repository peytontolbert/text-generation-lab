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
STAGE = 9004
NAME = "stage9004_post_training_diagnostics_gate_contract"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "POST_TRAINING_DIAGNOSTICS_GATE_CONTRACT_STAGE9004.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT = OUT_DIR / "post_training_diagnostics_gate_contract.json"

SOURCE_SUMMARY = ROOT / "runs/summaries/stage9000_one_run_bounded_training_ticket_contract.json"
SOURCE_CONTRACT = ROOT / "runs/local/artifacts/stage9000_one_run_bounded_training_ticket_contract/one_run_bounded_training_ticket_contract.json"

REQUIRED_INPUTS = [
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

REQUIRED_DIAGNOSTIC_CHECKS = [
    "run_card_authority_matches_ticket",
    "loss_curve_finite_no_nan_inf",
    "per_field_metrics_present_for_all_enabled_heads",
    "confusion_matrices_present_for_classification_heads",
    "high_confidence_wrong_rows_below_gate_or_blocked",
    "loss_mask_runtime_enforcement_passed",
    "gradient_norms_finite_and_bounded",
    "checkpoint_cleanup_proof_passed",
    "locked_eval_not_touched",
    "no_source_body_runtime_leak",
    "no_decoder_ce_unless_ticket_and_row_mask_allowed",
    "no_denoise_ce_unless_ticket_and_row_mask_allowed",
    "promotion_blocker_report_present",
]

REQUIRED_OUTPUTS = [
    "post_training_diagnostics_gate_report.json",
    "diagnostic_failure_clusters.jsonl",
    "dataset_compiler_feedback_patch_plan.json",
    "training_return_decision_card.json",
    "next_action_blocker_card.json",
]

POSSIBLE_DECISIONS = [
    "BLOCK_RETURN_TO_TRAINING_FIX_DATA",
    "BLOCK_RETURN_TO_TRAINING_FIX_TRAINER",
    "BLOCK_RETURN_TO_TRAINING_FIX_MODEL_HEAD",
    "ALLOW_NEXT_BOUNDED_DIAGNOSTIC_STAGE_ONLY",
    "ALLOW_NO_TRAINING_REGISTRY_UPDATE_ONLY",
]

FORBIDDEN_OPERATIONS = [
    "RUN_POST_TRAINING_DIAGNOSTICS_NOW",
    "PROMOTE_MODEL",
    "MERGE_MODEL",
    "EXPORT_FINAL_CHECKPOINT",
    "RUN_RUNTIME",
    "RUN_GEMMA",
    "RUN_HARNESS_SCORING",
    "READ_LOCKED_EVAL_FOR_TRAINING",
    "WRITE_TO_ARXIV",
    "START_ADDITIONAL_TRAINING",
    "AUTHORIZE_DECODER_CE",
    "AUTHORIZE_DENOISE_CE",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_contract(registry: dict[str, Any]) -> dict[str, Any]:
    source_summary = load_json(SOURCE_SUMMARY)
    source_contract = load_json(SOURCE_CONTRACT)
    source_required = set(source_contract.get("required_post_run_telemetry") or [])
    checks = {
        "source_stage9000_present": SOURCE_SUMMARY.exists() and SOURCE_CONTRACT.exists(),
        "source_stage9000_passed": source_summary.get("passed") is True,
        "source_stage9000_training_closed": (source_summary.get("metrics") or {}).get("training_ticket_authorized_now") is False,
        "source_stage9000_requires_same_inputs": set(REQUIRED_INPUTS).issubset(source_required),
        "required_inputs_recorded": len(REQUIRED_INPUTS) >= 9,
        "required_diagnostic_checks_recorded": len(REQUIRED_DIAGNOSTIC_CHECKS) >= 13,
        "required_outputs_recorded": len(REQUIRED_OUTPUTS) >= 5,
        "possible_decisions_recorded": len(POSSIBLE_DECISIONS) >= 5,
        "forbidden_operations_recorded": len(FORBIDDEN_OPERATIONS) >= 12,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "POST_TRAINING_DIAGNOSTICS_GATE_CONTRACT_NO_EXECUTION",
        "required_inputs": REQUIRED_INPUTS,
        "required_diagnostic_checks": REQUIRED_DIAGNOSTIC_CHECKS,
        "required_outputs": REQUIRED_OUTPUTS,
        "possible_decisions": POSSIBLE_DECISIONS,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "checks": checks,
        "metrics": {
            "required_inputs": len(REQUIRED_INPUTS),
            "required_diagnostic_checks": len(REQUIRED_DIAGNOSTIC_CHECKS),
            "required_outputs": len(REQUIRED_OUTPUTS),
            "possible_decisions": len(POSSIBLE_DECISIONS),
            "forbidden_operations": len(FORBIDDEN_OPERATIONS),
            "post_training_diagnostics_authorized_now": False,
            "post_training_diagnostics_executed_now": False,
            "promotion_authorized": False,
            "model_merge_authorized": False,
            "final_checkpoint_export_authorized": False,
            "runtime_authorized_flag": False,
            "gemma_execution_attempted": False,
            "harness_scoring_attempted": False,
            "locked_eval_training_use": False,
            "arxiv_write_authorized": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "model_execution_attempted": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Post-training diagnostics are specified as a future gate only. No bounded training result may progress without telemetry, loss-mask, high-confidence-wrong, gradient, cleanup, and blocker reports.",
    }


def validate_contract(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for required in [
        "high_confidence_wrong_rows_below_gate_or_blocked",
        "gradient_norms_finite_and_bounded",
        "checkpoint_cleanup_proof_passed",
        "promotion_blocker_report_present",
    ]:
        if required not in card.get("required_diagnostic_checks", []):
            failures.append(f"missing_check:{required}")
    for key in [
        "post_training_diagnostics_authorized_now",
        "post_training_diagnostics_executed_now",
        "promotion_authorized",
        "model_merge_authorized",
        "final_checkpoint_export_authorized",
        "runtime_authorized_flag",
        "gemma_execution_attempted",
        "harness_scoring_attempted",
        "locked_eval_training_use",
        "arxiv_write_authorized",
        "training_authorized",
        "data_mining_authorized",
        "model_execution_attempted",
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
        "next_best_step": "After a future one-run bounded training ticket executes, run this diagnostics gate before any further training, merge, promotion, scoring, or decoder expansion.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9004 Post-Training Diagnostics Gate Contract",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage defines the future post-training diagnostics gate. It does not run diagnostics, train, promote, merge, score, execute runtime/Gemma, or authorize decoder/denoise CE.",
        "",
        f"Diagnostic checks: `{summary['metrics']['required_diagnostic_checks']}`",
        f"Post-training diagnostics authorized now: `{summary['metrics']['post_training_diagnostics_authorized_now']}`",
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
