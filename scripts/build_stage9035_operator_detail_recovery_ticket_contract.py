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
STAGE = 9035
NAME = "stage9035_operator_detail_recovery_ticket_contract"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9034_SUMMARY = ROOT / "runs/summaries/stage9034_operator_detail_seed_gap_matrix.json"
SOURCE_9034_MATRIX = ROOT / "runs/local/artifacts/stage9034_operator_detail_seed_gap_matrix/operator_detail_seed_gap_matrix.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "OPERATOR_DETAIL_RECOVERY_TICKET_CONTRACT_STAGE9035.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT = OUT_DIR / "operator_detail_recovery_ticket_contract.json"

RECOVERY_FIELDS = [
    "inputs",
    "outputs",
    "confidence_score",
    "failure_modes",
    "training_label_source",
    "metric",
]

ALLOWED_METADATA_SOURCES = [
    "stage8703_low_level_training_concept_session_grep_artifacts",
    "stage9033_operator_detail_seed_catalog",
    "stage8718_operator_inventory",
    "existing_docs_no_raw_session_payload",
    "human_authored_metadata_patch",
]

TICKET_REQUIRED_FIELDS = [
    "ticket_id",
    "source_seed_stage",
    "source_gap_stage",
    "operator_ids",
    "recovery_fields",
    "allowed_metadata_sources",
    "forbidden_sources",
    "output_artifacts",
    "validation_requirements",
    "authority",
]

FUTURE_OUTPUT_ARTIFACTS = [
    "operator_detail_metadata_patch.jsonl",
    "operator_detail_field_coverage_card.json",
    "operator_detail_hash_audit.json",
    "operator_detail_no_raw_payload_proof.json",
]

VALIDATION_REQUIREMENTS = [
    "all_108_operator_ids_preserved",
    "all_recovery_fields_present_or_explicitly_blocked",
    "inputs_outputs_are_symbolic_metadata_not_source_body",
    "confidence_score_semantics_documented",
    "failure_modes_are_reason_codes_not_raw_trace",
    "training_label_source_is_stage_or_human_patch_ref",
    "metric_is_named_and_bounded",
    "detail_hash_present_for_recovered_rows",
    "no_raw_session_or_source_payload_fields",
]

FORBIDDEN_SOURCES = [
    "raw_codex_session_text",
    "raw_repository_source_body",
    "raw_row_body_text",
    "hidden_or_locked_eval_payload",
    "model_generated_operator_detail_without_audit",
]

FORBIDDEN_OPERATIONS = [
    "RECOVER_OPERATOR_DETAILS_NOW",
    "READ_RAW_SESSION_TEXT",
    "READ_REPOSITORY_SOURCE_BODY",
    "READ_ROW_BODY_TEXT",
    "MATERIALIZE_OPERATOR_DETAIL_PATCH_NOW",
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
    m9034 = load_json(SOURCE_9034_MATRIX)
    field_counts = m9034.get("field_missing_counts") or {}
    checks = {
        "source_stage9034_present": SOURCE_9034_SUMMARY.exists() and SOURCE_9034_MATRIX.exists(),
        "source_stage9034_passed": s9034.get("passed") is True,
        "source_stage9034_confirms_108_blocked_rows": (s9034.get("metrics") or {}).get("rows_missing_training_ready_fields") == 108,
        "all_recovery_fields_match_gap_matrix": set(RECOVERY_FIELDS) == set(field_counts),
        "all_recovery_fields_missing_for_108_rows": all(field_counts.get(field) == 108 for field in RECOVERY_FIELDS),
        "ticket_required_fields_recorded": len(TICKET_REQUIRED_FIELDS) >= 10,
        "future_outputs_recorded": len(FUTURE_OUTPUT_ARTIFACTS) >= 4,
        "validation_requirements_recorded": len(VALIDATION_REQUIREMENTS) >= 9,
        "forbidden_sources_recorded": len(FORBIDDEN_SOURCES) >= 5,
        "forbidden_operations_recorded": len(FORBIDDEN_OPERATIONS) >= 16,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "OPERATOR_DETAIL_RECOVERY_TICKET_CONTRACT_NO_EXECUTION",
        "ticket_template": {
            "ticket_id": "future_operator_detail_recovery_ticket",
            "source_seed_stage": "stage9033_operator_detail_seed_catalog",
            "source_gap_stage": "stage9034_operator_detail_seed_gap_matrix",
            "operator_ids": "OP001-OP108",
            "recovery_fields": RECOVERY_FIELDS,
            "allowed_metadata_sources": ALLOWED_METADATA_SOURCES,
            "forbidden_sources": FORBIDDEN_SOURCES,
            "output_artifacts": FUTURE_OUTPUT_ARTIFACTS,
            "validation_requirements": VALIDATION_REQUIREMENTS,
            "authority": dict(AUTHORITY_CLOSED),
        },
        "recovery_fields": RECOVERY_FIELDS,
        "allowed_metadata_sources": ALLOWED_METADATA_SOURCES,
        "forbidden_sources": FORBIDDEN_SOURCES,
        "future_output_artifacts": FUTURE_OUTPUT_ARTIFACTS,
        "validation_requirements": VALIDATION_REQUIREMENTS,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "checks": checks,
        "metrics": {
            "recovery_fields": len(RECOVERY_FIELDS),
            "operator_rows_to_recover": 108,
            "future_output_artifacts": len(FUTURE_OUTPUT_ARTIFACTS),
            "validation_requirements": len(VALIDATION_REQUIREMENTS),
            "forbidden_sources": len(FORBIDDEN_SOURCES),
            "forbidden_operations": len(FORBIDDEN_OPERATIONS),
            "ticket_contract_only": True,
            "operator_details_recovered_now": False,
            "operator_detail_patch_materialized_now": False,
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
        "decision": "This stage defines the future operator-detail recovery ticket only. It does not recover details, read raw payloads, materialize patches, mine, or train.",
    }


def validate_contract(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    ticket = card.get("ticket_template") or {}
    if any((ticket.get("authority") or {}).values()):
        failures.append("ticket_authority_open")
    for field in RECOVERY_FIELDS:
        if field not in ticket.get("recovery_fields", []):
            failures.append(f"missing_recovery_field:{field}")
    for forbidden in ["raw_codex_session_text", "raw_repository_source_body", "raw_row_body_text"]:
        if forbidden not in card.get("forbidden_sources", []):
            failures.append(f"missing_forbidden_source:{forbidden}")
    for key in [
        "operator_details_recovered_now",
        "operator_detail_patch_materialized_now",
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
        "next_best_step": "Instantiate this ticket only after agreeing metadata-only sources; do not read raw sessions/source/rows or train.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9035 Operator Detail Recovery Ticket Contract",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage defines a future metadata-only ticket for recovering missing operator detail fields. It does not recover details, read raw sessions/source/row bodies, materialize patches, run a judge, compile a manifest, train, mine, or write `/arxiv`.",
        "",
        f"Recovery fields: `{summary['metrics']['recovery_fields']}`",
        f"Operator rows to recover: `{summary['metrics']['operator_rows_to_recover']}`",
        f"Operator details recovered now: `{summary['metrics']['operator_details_recovered_now']}`",
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
