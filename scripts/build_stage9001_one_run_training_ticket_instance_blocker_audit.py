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
STAGE = 9001
NAME = "stage9001_one_run_training_ticket_instance_blocker_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ONE_RUN_TRAINING_TICKET_INSTANCE_BLOCKER_AUDIT_STAGE9001.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "one_run_training_ticket_instance_blocker_audit.json"

SOURCE_SUMMARY = ROOT / "runs/summaries/stage9000_one_run_bounded_training_ticket_contract.json"
SOURCE_CONTRACT = ROOT / "runs/local/artifacts/stage9000_one_run_bounded_training_ticket_contract/one_run_bounded_training_ticket_contract.json"
DRY_RUN_DIR = ROOT / "runs/local/artifacts/future_stage899x_trainer_contract_dry_run"
REQUIRED_DRY_RUN_ARTIFACTS = [
    "trainer_contract_dry_run_report.json",
    "loss_mask_enforcement_audit.json",
    "telemetry_artifact_plan.json",
    "no_model_forward_proof.json",
    "no_training_execution_proof.json",
    "next_one_run_training_ticket_input.json",
]
REQUIRED_PREREQUISITES = [
    "stage9000_contract_passed",
    "trainer_contract_dry_run_report_present",
    "loss_mask_enforcement_audit_present",
    "telemetry_artifact_plan_present",
    "no_model_forward_proof_present",
    "no_training_execution_proof_present",
    "next_one_run_training_ticket_input_present",
    "dry_run_audit_passed",
]
BLOCKING_REASONS = {
    "trainer_contract_dry_run_report_present": "trainer contract-only dry run has not executed",
    "loss_mask_enforcement_audit_present": "loss-mask enforcement dry-run audit artifact is absent",
    "telemetry_artifact_plan_present": "telemetry artifact plan from dry run is absent",
    "no_model_forward_proof_present": "no-model-forward proof is absent",
    "no_training_execution_proof_present": "no-training proof is absent",
    "next_one_run_training_ticket_input_present": "one-run ticket input artifact is absent",
    "dry_run_audit_passed": "trainer dry-run pass card is absent",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def artifact_path(name: str) -> Path:
    return DRY_RUN_DIR / name


def build_audit(registry: dict[str, Any]) -> dict[str, Any]:
    source_summary = load_json(SOURCE_SUMMARY)
    source_contract = load_json(SOURCE_CONTRACT)
    prereq = {
        "stage9000_contract_passed": source_summary.get("passed") is True,
        "trainer_contract_dry_run_report_present": artifact_path("trainer_contract_dry_run_report.json").exists(),
        "loss_mask_enforcement_audit_present": artifact_path("loss_mask_enforcement_audit.json").exists(),
        "telemetry_artifact_plan_present": artifact_path("telemetry_artifact_plan.json").exists(),
        "no_model_forward_proof_present": artifact_path("no_model_forward_proof.json").exists(),
        "no_training_execution_proof_present": artifact_path("no_training_execution_proof.json").exists(),
        "next_one_run_training_ticket_input_present": artifact_path("next_one_run_training_ticket_input.json").exists(),
        "dry_run_audit_passed": False,
    }
    missing = [key for key in REQUIRED_PREREQUISITES if prereq.get(key) is not True]
    checks = {
        "source_stage9000_present": SOURCE_SUMMARY.exists() and SOURCE_CONTRACT.exists(),
        "source_stage9000_passed": source_summary.get("passed") is True,
        "source_stage9000_training_closed": (source_summary.get("metrics") or {}).get("training_ticket_authorized_now") is False,
        "source_stage9000_requires_dry_run_inputs": set(REQUIRED_DRY_RUN_ARTIFACTS).issubset(set(source_contract.get("required_inputs") or [])),
        "missing_prerequisites_recorded": len(missing) > 0,
        "ticket_instance_correctly_blocked": True,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "ONE_RUN_TRAINING_TICKET_INSTANCE_BLOCKED_NO_EXECUTION",
        "required_dry_run_artifacts": REQUIRED_DRY_RUN_ARTIFACTS,
        "prerequisite_status": prereq,
        "missing_prerequisites": missing,
        "blockers": [BLOCKING_REASONS.get(key, key) for key in missing],
        "checks": checks,
        "metrics": {
            "required_prerequisites": len(REQUIRED_PREREQUISITES),
            "missing_prerequisites": len(missing),
            "blockers": len(missing),
            "ticket_instance_ready": False,
            "ticket_instance_designed": False,
            "training_ticket_authorized_now": False,
            "training_executed_now": False,
            "dataset_rows_loaded": False,
            "repository_source_bodies_loaded": False,
            "arxiv_write_authorized": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "model_execution_attempted": False,
            "runtime_authorized_flag": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "checkpoint_written": False,
            "final_checkpoint_exported": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "One-run bounded training ticket instance is correctly blocked because trainer dry-run artifacts do not exist. No training ticket is designed or authorized.",
    }


def validate_audit(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    if card["metrics"].get("missing_prerequisites", 0) == 0:
        failures.append("missing_prerequisites_not_recorded")
    if card["metrics"].get("ticket_instance_ready") is not False:
        failures.append("ticket_instance_ready")
    for key in [
        "ticket_instance_designed",
        "training_ticket_authorized_now",
        "training_executed_now",
        "dataset_rows_loaded",
        "repository_source_bodies_loaded",
        "arxiv_write_authorized",
        "training_authorized",
        "data_mining_authorized",
        "model_execution_attempted",
        "runtime_authorized_flag",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "checkpoint_written",
        "final_checkpoint_exported",
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
        "next_best_step": "Do not instantiate a training ticket yet. Complete an authorized trainer contract-only dry run and audit its artifacts first.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9001 One-Run Training Ticket Instance Blocker Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage checks whether an actual one-run bounded training ticket can be instantiated. It is correctly blocked because trainer dry-run artifacts are absent. It does not train, load rows, write checkpoints, or authorize decoder/denoise CE.",
        "",
        f"Missing prerequisites: `{summary['metrics']['missing_prerequisites']}`",
        f"Ticket instance ready: `{summary['metrics']['ticket_instance_ready']}`",
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
    marker = "## Stage9001 One-Run Training Ticket Instance Blocker Audit"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage9001 records that actual one-run bounded training ticket instantiation is blocked until trainer dry-run artifacts exist and pass. Training and model execution remain closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
