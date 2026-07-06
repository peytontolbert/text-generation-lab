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
STAGE = 9018
NAME = "stage9018_row_sample_judge_output_materialization_blocker_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9017_SUMMARY = ROOT / "runs/summaries/stage9017_row_sample_judge_output_materialization_contract.json"
SOURCE_9017_CONTRACT = ROOT / "runs/local/artifacts/stage9017_row_sample_judge_output_materialization_contract/row_sample_judge_output_materialization_contract.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ROW_SAMPLE_JUDGE_OUTPUT_MATERIALIZATION_BLOCKER_AUDIT_STAGE9018.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "row_sample_judge_output_materialization_blocker_audit.json"

REQUIRED_UPSTREAM_ARTIFACTS = {
    "row_sample_ticket_authorization_card.json": ROOT / "runs/local/artifacts/future_stage9xxx_row_sample_ticket/row_sample_ticket_authorization_card.json",
    "row_sample_manifest_metadata.jsonl": ROOT / "runs/local/artifacts/future_stage9xxx_row_sample_ticket/row_sample_manifest_metadata.jsonl",
    "row_sample_access_audit_card.json": ROOT / "runs/local/artifacts/future_stage9xxx_row_sample_ticket/row_sample_access_audit_card.json",
    "no_locked_eval_sample_proof.json": ROOT / "runs/local/artifacts/future_stage9xxx_row_sample_ticket/no_locked_eval_sample_proof.json",
}

REQUIRED_AUTHORIZATION_CONDITIONS = [
    "stage9017_contract_present",
    "stage9017_contract_passed",
    "row_sample_ticket_authorization_present",
    "row_sample_manifest_metadata_present",
    "row_sample_access_audit_present",
    "no_locked_eval_sample_proof_present",
    "row_sample_access_audit_passed",
    "no_locked_eval_sample_proof_passed",
    "separate_materialization_execution_ticket_present",
]

BLOCKING_REASONS_WHEN_MISSING = {
    "stage9017_contract_present": "row-sample judge-output materialization contract has not been materialized yet",
    "stage9017_contract_passed": "row-sample judge-output materialization contract has not passed yet",
    "row_sample_ticket_authorization_present": "row-sample ticket authorization card is absent",
    "row_sample_manifest_metadata_present": "row-sample manifest metadata is absent",
    "row_sample_access_audit_present": "row-sample access audit card is absent",
    "no_locked_eval_sample_proof_present": "no-locked-eval sample proof is absent",
    "row_sample_access_audit_passed": "row-sample access audit has not passed",
    "no_locked_eval_sample_proof_passed": "no-locked-eval sample proof has not passed",
    "separate_materialization_execution_ticket_present": "separate materialization execution ticket is absent",
}

FORBIDDEN_OPERATIONS = [
    "MATERIALIZE_JUDGE_OUTPUTS_NOW",
    "RUN_ROW_SAMPLE_JUDGE_NOW",
    "READ_ROW_BODIES_NOW",
    "OPEN_ADDITIONAL_DATASET_FILES",
    "MATERIALIZE_MANIFEST_NOW",
    "RUN_TRAINER_DRY_RUN_NOW",
    "START_TRAINING",
    "RUN_MODEL",
    "RUN_RUNTIME",
    "RUN_GEMMA",
    "WRITE_TO_ARXIV",
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
    s9017 = load_json(SOURCE_9017_SUMMARY)
    c9017 = load_json(SOURCE_9017_CONTRACT)
    present = {name: path.exists() for name, path in REQUIRED_UPSTREAM_ARTIFACTS.items()}
    readiness = {
        "stage9017_contract_present": SOURCE_9017_SUMMARY.exists() and SOURCE_9017_CONTRACT.exists(),
        "stage9017_contract_passed": s9017.get("passed") is True and SOURCE_9017_CONTRACT.exists(),
        "row_sample_ticket_authorization_present": present["row_sample_ticket_authorization_card.json"],
        "row_sample_manifest_metadata_present": present["row_sample_manifest_metadata.jsonl"],
        "row_sample_access_audit_present": present["row_sample_access_audit_card.json"],
        "no_locked_eval_sample_proof_present": present["no_locked_eval_sample_proof.json"],
        "row_sample_access_audit_passed": artifact_passed(REQUIRED_UPSTREAM_ARTIFACTS["row_sample_access_audit_card.json"]),
        "no_locked_eval_sample_proof_passed": artifact_passed(REQUIRED_UPSTREAM_ARTIFACTS["no_locked_eval_sample_proof.json"]),
        "separate_materialization_execution_ticket_present": False,
    }
    blocking_reasons = {
        condition: BLOCKING_REASONS_WHEN_MISSING[condition]
        for condition, ok in readiness.items()
        if not ok and condition in BLOCKING_REASONS_WHEN_MISSING
    }
    checks = {
        "stage9017_status_recorded": True,
        "stage9017_safety_ok_if_present": (not SOURCE_9017_SUMMARY.exists()) or ((s9017.get("metrics") or {}).get("materialization_authorized_now") is False),
        "stage9017_contract_outputs_ok_if_present": (not SOURCE_9017_CONTRACT.exists()) or len(c9017.get("future_outputs") or []) >= 5,
        "authorization_conditions_recorded": len(REQUIRED_AUTHORIZATION_CONDITIONS) >= 9,
        "forbidden_operations_recorded": len(FORBIDDEN_OPERATIONS) >= 13,
        "materialization_blocked": bool(blocking_reasons),
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "ROW_SAMPLE_JUDGE_OUTPUT_MATERIALIZATION_BLOCKER_AUDIT_NO_EXECUTION",
        "required_upstream_artifacts": {name: str(path.relative_to(ROOT)) for name, path in REQUIRED_UPSTREAM_ARTIFACTS.items()},
        "readiness": readiness,
        "blocking_reasons": blocking_reasons,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "checks": checks,
        "metrics": {
            "required_upstream_artifacts": len(REQUIRED_UPSTREAM_ARTIFACTS),
            "authorization_conditions": len(REQUIRED_AUTHORIZATION_CONDITIONS),
            "missing_upstream_artifacts": sum(1 for ok in present.values() if not ok),
            "blocking_reasons": len(blocking_reasons),
            "materialization_ready": False,
            "materialization_authorized_now": False,
            "judge_outputs_materialized_now": False,
            "row_sample_judge_executed_now": False,
            "row_bodies_read_now": False,
            "additional_dataset_files_opened": False,
            "manifest_materialized_now": False,
            "trainer_dry_run_execution_authorized_now": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "model_execution_attempted": False,
            "runtime_authorized_flag": False,
            "gemma_execution_attempted": False,
            "harness_scoring_attempted": False,
            "arxiv_write_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Row-sample judge-output materialization remains blocked until Stage9017 is materialized, upstream row-sample artifacts exist and pass, and a separate execution ticket exists.",
    }


def validate_audit(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    if card["metrics"].get("materialization_ready") is not False:
        failures.append("materialization_ready")
    for key in [
        "materialization_authorized_now",
        "judge_outputs_materialized_now",
        "row_sample_judge_executed_now",
        "row_bodies_read_now",
        "additional_dataset_files_opened",
        "manifest_materialized_now",
        "trainer_dry_run_execution_authorized_now",
        "training_authorized",
        "data_mining_authorized",
        "model_execution_attempted",
        "runtime_authorized_flag",
        "gemma_execution_attempted",
        "harness_scoring_attempted",
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
        "next_best_step": "Let Stage9017 materialization-contract work finish, then instantiate a separate materialization execution ticket only if upstream row-sample artifacts exist. Keep manifest/training closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9018 Row-Sample Judge Output Materialization Blocker Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage blocks row-sample judge-output materialization until Stage9017, upstream row-sample artifacts, and a separate execution ticket exist. It does not run a judge, read row bodies, materialize manifest, run trainer dry-run, train, mine, or write `/arxiv`.",
        "",
        f"Missing upstream artifacts: `{summary['metrics']['missing_upstream_artifacts']}`",
        f"Blocking reasons: `{summary['metrics']['blocking_reasons']}`",
        f"Materialization authorized now: `{summary['metrics']['materialization_authorized_now']}`",
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
