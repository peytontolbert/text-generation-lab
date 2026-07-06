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
STAGE = 9005
NAME = "stage9005_post_training_diagnostics_instance_blocker_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "POST_TRAINING_DIAGNOSTICS_INSTANCE_BLOCKER_AUDIT_STAGE9005.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "post_training_diagnostics_instance_blocker_audit.json"

SOURCE_SUMMARY = ROOT / "runs/summaries/stage9004_post_training_diagnostics_gate_contract.json"
SOURCE_CONTRACT = ROOT / "runs/local/artifacts/stage9004_post_training_diagnostics_gate_contract/post_training_diagnostics_gate_contract.json"

# Future artifacts. Absence is expected until a bounded training run actually executes.
FUTURE_TRAINING_RUN_DIR = ROOT / "runs/local/artifacts/future_stage9xxx_one_run_bounded_training_execution"
FUTURE_REQUIRED_ARTIFACTS = {
    "training_run_card.json": FUTURE_TRAINING_RUN_DIR / "training_run_card.json",
    "loss_curve.jsonl": FUTURE_TRAINING_RUN_DIR / "loss_curve.jsonl",
    "per_field_metrics.json": FUTURE_TRAINING_RUN_DIR / "per_field_metrics.json",
    "confusion_matrices.json": FUTURE_TRAINING_RUN_DIR / "confusion_matrices.json",
    "high_confidence_wrong_rows.jsonl": FUTURE_TRAINING_RUN_DIR / "high_confidence_wrong_rows.jsonl",
    "loss_mask_enforcement_runtime_audit.json": FUTURE_TRAINING_RUN_DIR / "loss_mask_enforcement_runtime_audit.json",
    "gradient_norm_summary.json": FUTURE_TRAINING_RUN_DIR / "gradient_norm_summary.json",
    "checkpoint_cleanup_proof.json": FUTURE_TRAINING_RUN_DIR / "checkpoint_cleanup_proof.json",
    "promotion_blocker_report.json": FUTURE_TRAINING_RUN_DIR / "promotion_blocker_report.json",
}

REQUIRED_READINESS_CONDITIONS = [
    "stage9004_contract_present",
    "stage9004_contract_passed",
    "training_run_card_present",
    "loss_curve_present",
    "per_field_metrics_present",
    "confusion_matrices_present",
    "high_confidence_wrong_rows_present",
    "loss_mask_runtime_audit_present",
    "gradient_norm_summary_present",
    "checkpoint_cleanup_proof_present",
    "promotion_blocker_report_present",
    "training_run_card_passed",
    "loss_mask_runtime_audit_passed",
    "checkpoint_cleanup_passed",
]

BLOCKING_REASONS_WHEN_MISSING = {
    "stage9004_contract_present": "post-training diagnostics gate contract has not been materialized yet",
    "stage9004_contract_passed": "post-training diagnostics gate contract has not passed yet",
    "training_run_card_present": "bounded training run card has not been emitted",
    "loss_curve_present": "loss curve telemetry is absent",
    "per_field_metrics_present": "per-field metrics are absent",
    "confusion_matrices_present": "confusion matrices are absent",
    "high_confidence_wrong_rows_present": "high-confidence wrong-row report is absent",
    "loss_mask_runtime_audit_present": "runtime loss-mask enforcement audit is absent",
    "gradient_norm_summary_present": "gradient norm summary is absent",
    "checkpoint_cleanup_proof_present": "checkpoint cleanup proof is absent",
    "promotion_blocker_report_present": "promotion blocker report is absent",
    "training_run_card_passed": "no passing training run card is available",
    "loss_mask_runtime_audit_passed": "no passing runtime loss-mask audit is available",
    "checkpoint_cleanup_passed": "no passing checkpoint cleanup proof is available",
}

FORBIDDEN_OPERATIONS = [
    "RUN_POST_TRAINING_DIAGNOSTICS_NOW",
    "READ_TRAINING_OUTPUTS_OUTSIDE_TICKET",
    "PROMOTE_MODEL",
    "MERGE_MODEL",
    "EXPORT_FINAL_CHECKPOINT",
    "RUN_RUNTIME",
    "RUN_GEMMA",
    "RUN_HARNESS_SCORING",
    "WRITE_TO_ARXIV",
    "START_ADDITIONAL_TRAINING",
    "AUTHORIZE_DECODER_CE",
    "AUTHORIZE_DENOISE_CE",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def artifact_passed(path: Path) -> bool:
    data = load_json(path)
    metrics = data.get("metrics") or {}
    return data.get("passed") is True or data.get("audit_passed") is True or metrics.get("passed") is True or metrics.get("audit_passed") is True


def build_audit(registry: dict[str, Any]) -> dict[str, Any]:
    source_summary = load_json(SOURCE_SUMMARY)
    source_contract = load_json(SOURCE_CONTRACT)
    present = {name: path.exists() for name, path in FUTURE_REQUIRED_ARTIFACTS.items()}
    readiness = {
        "stage9004_contract_present": SOURCE_SUMMARY.exists() and SOURCE_CONTRACT.exists(),
        "stage9004_contract_passed": source_summary.get("passed") is True and SOURCE_CONTRACT.exists(),
        "training_run_card_present": present["training_run_card.json"],
        "loss_curve_present": present["loss_curve.jsonl"],
        "per_field_metrics_present": present["per_field_metrics.json"],
        "confusion_matrices_present": present["confusion_matrices.json"],
        "high_confidence_wrong_rows_present": present["high_confidence_wrong_rows.jsonl"],
        "loss_mask_runtime_audit_present": present["loss_mask_enforcement_runtime_audit.json"],
        "gradient_norm_summary_present": present["gradient_norm_summary.json"],
        "checkpoint_cleanup_proof_present": present["checkpoint_cleanup_proof.json"],
        "promotion_blocker_report_present": present["promotion_blocker_report.json"],
        "training_run_card_passed": artifact_passed(FUTURE_REQUIRED_ARTIFACTS["training_run_card.json"]),
        "loss_mask_runtime_audit_passed": artifact_passed(FUTURE_REQUIRED_ARTIFACTS["loss_mask_enforcement_runtime_audit.json"]),
        "checkpoint_cleanup_passed": artifact_passed(FUTURE_REQUIRED_ARTIFACTS["checkpoint_cleanup_proof.json"]),
    }
    blocking_reasons = {
        condition: BLOCKING_REASONS_WHEN_MISSING[condition]
        for condition, ok in readiness.items()
        if not ok and condition in BLOCKING_REASONS_WHEN_MISSING
    }
    source_artifacts_present = SOURCE_SUMMARY.exists() and SOURCE_CONTRACT.exists()
    checks = {
        "source_stage9004_status_recorded": True,
        "source_stage9004_safety_ok_if_present": (not source_artifacts_present) or ((source_summary.get("metrics") or {}).get("post_training_diagnostics_authorized_now") is False),
        "source_stage9004_artifact_requirements_ok_if_present": (not SOURCE_CONTRACT.exists()) or (set(source_contract.get("required_inputs") or []) >= set(FUTURE_REQUIRED_ARTIFACTS)),
        "required_readiness_conditions_recorded": len(REQUIRED_READINESS_CONDITIONS) >= 14,
        "forbidden_operations_recorded": len(FORBIDDEN_OPERATIONS) >= 12,
        "diagnostics_instance_blocked": bool(blocking_reasons),
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "POST_TRAINING_DIAGNOSTICS_INSTANCE_BLOCKER_AUDIT_NO_EXECUTION",
        "future_required_artifacts": {name: str(path.relative_to(ROOT)) for name, path in FUTURE_REQUIRED_ARTIFACTS.items()},
        "readiness": readiness,
        "blocking_reasons": blocking_reasons,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "checks": checks,
        "metrics": {
            "required_readiness_conditions": len(REQUIRED_READINESS_CONDITIONS),
            "future_required_artifacts": len(FUTURE_REQUIRED_ARTIFACTS),
            "missing_future_artifacts": sum(1 for ok in present.values() if not ok),
            "blocking_reasons": len(blocking_reasons),
            "diagnostics_instance_ready": False,
            "post_training_diagnostics_authorized_now": False,
            "post_training_diagnostics_executed_now": False,
            "promotion_authorized": False,
            "model_merge_authorized": False,
            "final_checkpoint_export_authorized": False,
            "runtime_authorized_flag": False,
            "gemma_execution_attempted": False,
            "harness_scoring_attempted": False,
            "arxiv_write_authorized": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "model_execution_attempted": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Post-training diagnostics execution is blocked until a real bounded training run emits all required telemetry and cleanup artifacts. No diagnostics instance is executed by this audit.",
    }


def validate_audit(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    if card["metrics"].get("diagnostics_instance_ready") is not False:
        failures.append("diagnostics_instance_ready")
    for required in ["training_run_card_present", "loss_curve_present", "promotion_blocker_report_present"]:
        if required not in card.get("readiness", {}):
            failures.append(f"missing_readiness:{required}")
    for key in [
        "post_training_diagnostics_authorized_now",
        "post_training_diagnostics_executed_now",
        "promotion_authorized",
        "model_merge_authorized",
        "final_checkpoint_export_authorized",
        "runtime_authorized_flag",
        "gemma_execution_attempted",
        "harness_scoring_attempted",
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
        "next_best_step": "Keep diagnostics execution blocked until a real bounded training run emits the required telemetry artifacts. Do not promote, merge, score, or expand decoder paths.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9005 Post-Training Diagnostics Instance Blocker Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage blocks future post-training diagnostics execution until a bounded training run emits all required telemetry artifacts. It does not run diagnostics, train, promote, merge, score, execute runtime/Gemma, or authorize decoder/denoise CE.",
        "",
        f"Missing future artifacts: `{summary['metrics']['missing_future_artifacts']}`",
        f"Blocking reasons: `{summary['metrics']['blocking_reasons']}`",
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
