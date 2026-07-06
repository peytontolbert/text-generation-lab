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
STAGE = 9041
NAME = "stage9041_operator_detail_training_readiness_gate"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9034_SUMMARY = ROOT / "runs/summaries/stage9034_operator_detail_seed_gap_matrix.json"
SOURCE_9035_SUMMARY = ROOT / "runs/summaries/stage9035_operator_detail_recovery_ticket_contract.json"
SOURCE_9040_SUMMARY = ROOT / "runs/summaries/stage9040_operator_detail_metadata_patch_validator_contract.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "OPERATOR_DETAIL_TRAINING_READINESS_GATE_STAGE9041.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
GATE = OUT_DIR / "operator_detail_training_readiness_gate.json"

REQUIRED_PASSING_INPUTS = [
    "operator_detail_metadata_patch_validation_card.json",
    "operator_detail_field_coverage_card.json",
    "operator_detail_hash_audit.json",
    "operator_detail_no_raw_payload_proof_audit.json",
]

TRAINING_READINESS_CONDITIONS = [
    "all_108_operator_rows_present",
    "all_6_training_ready_fields_present",
    "inputs_outputs_are_symbolic_metadata",
    "confidence_score_semantics_documented",
    "failure_modes_are_reason_codes",
    "training_label_source_refs_approved",
    "metric_names_and_bounds_documented",
    "detail_hashes_present_and_stable",
    "no_raw_payload_proof_passed",
    "operator_category_consistent_with_stage8718",
    "operator_detail_refs_ready_for_judge_rows",
    "loss_policy_structured_aux_only_until_separate_training_ticket",
]

BLOCKING_REASONS = [
    "missing_operator_detail_metadata_patch_validation",
    "missing_field_coverage_card",
    "missing_hash_audit",
    "missing_no_raw_payload_proof",
    "not_all_108_operator_rows_ready",
    "raw_payload_risk",
    "loss_policy_not_separately_authorized",
]

ALLOWED_AFTER_FUTURE_PASS = [
    "attach_operator_detail_refs_to_future_judged_rows",
    "enable_operator_detail_metadata_as_nonpayload_features",
    "allow_structured_aux_loss_consideration_under_separate_ticket",
]

FORBIDDEN_OPERATIONS = [
    "AUTHORIZE_TRAINING_NOW",
    "AUTHORIZE_OPERATOR_SPECIFIC_TRAINING_NOW",
    "MATERIALIZE_TRAINING_ROWS_NOW",
    "RUN_TRAINER_DRY_RUN_NOW",
    "START_TRAINING",
    "AUTHORIZE_DECODER_CE",
    "AUTHORIZE_DENOISE_CE",
    "READ_RAW_SESSION_TEXT",
    "READ_REPOSITORY_SOURCE_BODY",
    "READ_ROW_BODY_TEXT",
    "RUN_MODEL",
    "RUN_RUNTIME",
    "RUN_GEMMA",
    "WRITE_TO_ARXIV",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_gate(registry: dict[str, Any]) -> dict[str, Any]:
    s9034 = load_json(SOURCE_9034_SUMMARY)
    s9035 = load_json(SOURCE_9035_SUMMARY)
    s9040 = load_json(SOURCE_9040_SUMMARY)
    checks = {
        "source_stage9034_present": SOURCE_9034_SUMMARY.exists(),
        "source_stage9034_passed": s9034.get("passed") is True,
        "source_stage9034_confirms_gaps": (s9034.get("metrics") or {}).get("rows_missing_training_ready_fields") == 108,
        "source_stage9035_present": SOURCE_9035_SUMMARY.exists(),
        "source_stage9035_passed": s9035.get("passed") is True,
        "source_stage9040_present": SOURCE_9040_SUMMARY.exists(),
        "source_stage9040_passed": s9040.get("passed") is True,
        "required_passing_inputs_recorded": len(REQUIRED_PASSING_INPUTS) >= 4,
        "training_readiness_conditions_recorded": len(TRAINING_READINESS_CONDITIONS) >= 12,
        "blocking_reasons_recorded": len(BLOCKING_REASONS) >= 7,
        "forbidden_operations_recorded": len(FORBIDDEN_OPERATIONS) >= 14,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "OPERATOR_DETAIL_TRAINING_READINESS_GATE_NO_EXECUTION",
        "required_passing_inputs": REQUIRED_PASSING_INPUTS,
        "training_readiness_conditions": TRAINING_READINESS_CONDITIONS,
        "blocking_reasons": BLOCKING_REASONS,
        "allowed_after_future_pass": ALLOWED_AFTER_FUTURE_PASS,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "checks": checks,
        "metrics": {
            "required_passing_inputs": len(REQUIRED_PASSING_INPUTS),
            "training_readiness_conditions": len(TRAINING_READINESS_CONDITIONS),
            "blocking_reasons": len(BLOCKING_REASONS),
            "allowed_after_future_pass": len(ALLOWED_AFTER_FUTURE_PASS),
            "forbidden_operations": len(FORBIDDEN_OPERATIONS),
            "training_readiness_gate_only": True,
            "operator_detail_training_ready_now": False,
            "operator_specific_training_authorized_now": False,
            "training_rows_materialized_now": False,
            "trainer_dry_run_execution_authorized_now": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "raw_session_text_read_now": False,
            "row_bodies_read_now": False,
            "repository_source_bodies_read_now": False,
            "model_execution_attempted": False,
            "runtime_authorized_flag": False,
            "gemma_execution_attempted": False,
            "harness_scoring_attempted": False,
            "arxiv_write_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Operator-detail metadata is not training-ready now. A future validated patch may only enable refs/features under a separate training ticket; this stage opens no training authority.",
    }


def validate_gate(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for condition in ["all_108_operator_rows_present", "all_6_training_ready_fields_present", "no_raw_payload_proof_passed", "loss_policy_structured_aux_only_until_separate_training_ticket"]:
        if condition not in card.get("training_readiness_conditions", []):
            failures.append(f"missing_training_condition:{condition}")
    for key in [
        "operator_detail_training_ready_now",
        "operator_specific_training_authorized_now",
        "training_rows_materialized_now",
        "trainer_dry_run_execution_authorized_now",
        "training_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "raw_session_text_read_now",
        "row_bodies_read_now",
        "repository_source_bodies_read_now",
        "model_execution_attempted",
        "runtime_authorized_flag",
        "gemma_execution_attempted",
        "harness_scoring_attempted",
        "arxiv_write_authorized",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_gate(registry)
    failures = validate_gate(card)
    GATE.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": 0, "failures": failures, **card["metrics"]},
        "artifacts": {"gate": str(GATE.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "Do not train. First materialize and validate an operator-detail metadata patch under the Stage9040 contract, then require a separate training ticket.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9041 Operator Detail Training Readiness Gate",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage defines the training-readiness gate for future operator-detail metadata. It does not train, materialize rows, run trainer dry-run, read raw payloads, execute models, or write `/arxiv`.",
        "",
        f"Training readiness conditions: `{summary['metrics']['training_readiness_conditions']}`",
        f"Operator-detail training ready now: `{summary['metrics']['operator_detail_training_ready_now']}`",
        f"Training authorized: `{summary['metrics']['training_authorized']}`",
        "",
    ]) + "\n", encoding="utf-8")
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
