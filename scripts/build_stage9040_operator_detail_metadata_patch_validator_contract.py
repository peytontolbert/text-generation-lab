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
STAGE = 9040
NAME = "stage9040_operator_detail_metadata_patch_validator_contract"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9034_SUMMARY = ROOT / "runs/summaries/stage9034_operator_detail_seed_gap_matrix.json"
SOURCE_9035_SUMMARY = ROOT / "runs/summaries/stage9035_operator_detail_recovery_ticket_contract.json"
SOURCE_9036_SUMMARY = ROOT / "runs/summaries/stage9036_operator_detail_metadata_source_agreement.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "OPERATOR_DETAIL_METADATA_PATCH_VALIDATOR_CONTRACT_STAGE9040.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT = OUT_DIR / "operator_detail_metadata_patch_validator_contract.json"

PATCH_ROW_REQUIRED_FIELDS = [
    "operator_id",
    "operator_schema_version",
    "inputs",
    "outputs",
    "confidence_score",
    "failure_modes",
    "training_label_source",
    "metric",
    "detail_source_refs",
    "detail_hash",
    "no_raw_payload_proof_ref",
]

VALIDATION_RULES = [
    "operator_id_must_be_op001_to_op108",
    "operator_id_must_exist_in_stage9033_seed_catalog",
    "inputs_outputs_are_symbolic_lists",
    "confidence_score_is_named_bounded_or_enum",
    "failure_modes_are_reason_codes_not_trace_text",
    "training_label_source_is_approved_metadata_ref",
    "metric_is_named_and_bounded",
    "detail_source_refs_are_metadata_only",
    "detail_hash_present",
    "no_raw_payload_proof_present",
    "forbidden_raw_payload_fields_absent",
    "all_108_rows_present_before_training_ready",
]

FORBIDDEN_PATCH_FIELDS = [
    "raw_operator_body",
    "raw_codex_session_text",
    "raw_repository_source_body",
    "raw_row_body_text",
    "hidden_eval_payload",
    "clean_target_body",
    "generated_patch",
    "model_logits",
]

FUTURE_VALIDATOR_OUTPUTS = [
    "operator_detail_metadata_patch_validation_card.json",
    "operator_detail_field_coverage_card.json",
    "operator_detail_hash_audit.json",
    "operator_detail_no_raw_payload_proof_audit.json",
]

FORBIDDEN_OPERATIONS = [
    "VALIDATE_REAL_OPERATOR_DETAIL_PATCH_NOW",
    "MATERIALIZE_OPERATOR_DETAIL_PATCH_NOW",
    "RECOVER_OPERATOR_DETAILS_NOW",
    "READ_RAW_SESSION_TEXT",
    "READ_REPOSITORY_SOURCE_BODY",
    "READ_ROW_BODY_TEXT",
    "MATERIALIZE_TRAINING_ROWS_NOW",
    "RUN_ROW_SAMPLE_JUDGE_NOW",
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


def build_contract(registry: dict[str, Any]) -> dict[str, Any]:
    s9034 = load_json(SOURCE_9034_SUMMARY)
    s9035 = load_json(SOURCE_9035_SUMMARY)
    s9036 = load_json(SOURCE_9036_SUMMARY)
    checks = {
        "source_stage9034_present": SOURCE_9034_SUMMARY.exists(),
        "source_stage9034_passed": s9034.get("passed") is True,
        "source_stage9034_confirms_all_rows_blocked": (s9034.get("metrics") or {}).get("rows_missing_training_ready_fields") == 108,
        "source_stage9035_present": SOURCE_9035_SUMMARY.exists(),
        "source_stage9035_passed": s9035.get("passed") is True,
        "source_stage9036_present": SOURCE_9036_SUMMARY.exists(),
        "source_stage9036_passed": s9036.get("passed") is True,
        "patch_row_required_fields_recorded": len(PATCH_ROW_REQUIRED_FIELDS) >= 11,
        "validation_rules_recorded": len(VALIDATION_RULES) >= 12,
        "forbidden_patch_fields_recorded": len(FORBIDDEN_PATCH_FIELDS) >= 8,
        "future_outputs_recorded": len(FUTURE_VALIDATOR_OUTPUTS) >= 4,
        "forbidden_operations_recorded": len(FORBIDDEN_OPERATIONS) >= 17,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "OPERATOR_DETAIL_METADATA_PATCH_VALIDATOR_CONTRACT_NO_EXECUTION",
        "patch_row_required_fields": PATCH_ROW_REQUIRED_FIELDS,
        "validation_rules": VALIDATION_RULES,
        "forbidden_patch_fields": FORBIDDEN_PATCH_FIELDS,
        "future_validator_outputs": FUTURE_VALIDATOR_OUTPUTS,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "checks": checks,
        "metrics": {
            "patch_row_required_fields": len(PATCH_ROW_REQUIRED_FIELDS),
            "validation_rules": len(VALIDATION_RULES),
            "forbidden_patch_fields": len(FORBIDDEN_PATCH_FIELDS),
            "future_validator_outputs": len(FUTURE_VALIDATOR_OUTPUTS),
            "forbidden_operations": len(FORBIDDEN_OPERATIONS),
            "validator_contract_only": True,
            "real_operator_detail_patch_validated_now": False,
            "operator_detail_patch_materialized_now": False,
            "operator_details_recovered_now": False,
            "raw_session_text_read_now": False,
            "row_bodies_read_now": False,
            "repository_source_bodies_read_now": False,
            "training_rows_materialized_now": False,
            "judge_executed_now": False,
            "manifest_compile_authorized_now": False,
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
        "decision": "This stage defines the validator contract for a future operator-detail metadata patch only. It does not validate a real patch, recover details, read raw payloads, or train.",
    }


def validate_contract(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for field in ["operator_id", "inputs", "outputs", "confidence_score", "failure_modes", "training_label_source", "metric", "detail_hash"]:
        if field not in card.get("patch_row_required_fields", []):
            failures.append(f"missing_patch_field:{field}")
    for field in ["raw_codex_session_text", "raw_repository_source_body", "raw_row_body_text"]:
        if field not in card.get("forbidden_patch_fields", []):
            failures.append(f"missing_forbidden_patch_field:{field}")
    for key in [
        "real_operator_detail_patch_validated_now",
        "operator_detail_patch_materialized_now",
        "operator_details_recovered_now",
        "raw_session_text_read_now",
        "row_bodies_read_now",
        "repository_source_bodies_read_now",
        "training_rows_materialized_now",
        "judge_executed_now",
        "manifest_compile_authorized_now",
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
        "next_best_step": "Only after a metadata-only operator-detail patch exists, run this validator; keep raw payload reads, mining, and training closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9040 Operator Detail Metadata Patch Validator Contract",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage defines a future validator for operator-detail metadata patches. It does not validate a real patch, recover details, read raw sessions/source/row bodies, materialize training rows, run a judge, compile a manifest, train, mine, or write `/arxiv`.",
        "",
        f"Patch row required fields: `{summary['metrics']['patch_row_required_fields']}`",
        f"Validation rules: `{summary['metrics']['validation_rules']}`",
        f"Real patch validated now: `{summary['metrics']['real_operator_detail_patch_validated_now']}`",
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
