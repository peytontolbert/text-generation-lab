#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.curriculum_compiler import REQUIRED_RECOVERED_GATE_REFERENCES
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from curriculum_compiler import REQUIRED_RECOVERED_GATE_REFERENCES  # type: ignore
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9027
NAME = "stage9027_row_sample_judge_output_schema_validator_contract"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9023_SUMMARY = ROOT / "runs/summaries/stage9023_row_sample_judge_diagnostics_contract.json"
SOURCE_9023_CONTRACT = ROOT / "runs/local/artifacts/stage9023_row_sample_judge_diagnostics_contract/row_sample_judge_diagnostics_contract.json"
SOURCE_9026_SUMMARY = ROOT / "runs/summaries/stage9026_row_sample_judge_reason_code_taxonomy_contract.json"
SOURCE_9026_CONTRACT = ROOT / "runs/local/artifacts/stage9026_row_sample_judge_reason_code_taxonomy_contract/row_sample_judge_reason_code_taxonomy_contract.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ROW_SAMPLE_JUDGE_OUTPUT_SCHEMA_VALIDATOR_CONTRACT_STAGE9027.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT = OUT_DIR / "row_sample_judge_output_schema_validator_contract.json"

VALIDATOR_CHECKS = [
    "row_ids_unique_across_outputs",
    "accepted_and_rejected_ids_disjoint",
    "accepted_rows_have_no_reject_reason",
    "rejected_rows_have_known_taxonomy_reason",
    "quality_score_in_unit_interval",
    "confidence_in_unit_interval",
    "criteria_scores_in_unit_interval",
    "risk_reasons_are_lists",
    "loss_mask_candidates_structured_aux_only_or_blocked",
    "gate_status_has_all_recovered_keys",
    "gate_status_failed_rows_not_accepted",
    "source_metadata_refs_present_not_body_text",
    "forbidden_raw_fields_absent",
    "counts_match_report",
]

REQUIRED_FUTURE_INPUTS = [
    "row_sample_dataset_judge_report.json",
    "candidate_row_quality_scores.jsonl",
    "rejected_row_ids.jsonl",
    "accepted_row_ids_pending_manifest_compile.jsonl",
    "judge_to_compiler_gate_status.json",
]

FORBIDDEN_FIELDS = [
    "raw_row_body",
    "raw_encoder_text",
    "raw_decoder_text",
    "raw_repository_source_body",
    "clean_target_body",
    "hidden_eval_payload",
    "model_logits",
    "generated_patch",
]

FORBIDDEN_OPERATIONS = [
    "VALIDATE_REAL_JUDGE_OUTPUTS_NOW",
    "READ_ROW_BODY_TEXT",
    "READ_REPOSITORY_SOURCE_BODY",
    "MATERIALIZE_JUDGE_OUTPUTS_NOW",
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
    s9023 = load_json(SOURCE_9023_SUMMARY)
    c9023 = load_json(SOURCE_9023_CONTRACT)
    s9026 = load_json(SOURCE_9026_SUMMARY)
    c9026 = load_json(SOURCE_9026_CONTRACT)
    diagnostics_fields = set(c9023.get("required_row_score_fields") or [])
    taxonomy_codes = set((c9026.get("reason_code_taxonomy") or {}).keys())
    checks = {
        "source_stage9023_present": SOURCE_9023_SUMMARY.exists() and SOURCE_9023_CONTRACT.exists(),
        "source_stage9023_passed": s9023.get("passed") is True,
        "source_stage9026_present": SOURCE_9026_SUMMARY.exists() and SOURCE_9026_CONTRACT.exists(),
        "source_stage9026_passed": s9026.get("passed") is True,
        "diagnostic_fields_include_scores_and_gate": {"quality_score", "confidence", "criteria_scores", "gate_status", "loss_mask_candidates"}.issubset(diagnostics_fields),
        "taxonomy_codes_available": len(taxonomy_codes) >= 10,
        "validator_checks_recorded": len(VALIDATOR_CHECKS) >= 14,
        "future_inputs_recorded": len(REQUIRED_FUTURE_INPUTS) == 5,
        "forbidden_fields_recorded": len(FORBIDDEN_FIELDS) >= 8,
        "forbidden_operations_recorded": len(FORBIDDEN_OPERATIONS) >= 13,
        "recovered_gate_keys_available": len(REQUIRED_RECOVERED_GATE_REFERENCES) >= 1,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "ROW_SAMPLE_JUDGE_OUTPUT_SCHEMA_VALIDATOR_CONTRACT_NO_EXECUTION",
        "required_future_inputs": REQUIRED_FUTURE_INPUTS,
        "validator_checks": VALIDATOR_CHECKS,
        "known_reject_reason_codes": sorted(taxonomy_codes),
        "required_recovered_gate_references": list(REQUIRED_RECOVERED_GATE_REFERENCES),
        "forbidden_fields": FORBIDDEN_FIELDS,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "checks": checks,
        "metrics": {
            "required_future_inputs": len(REQUIRED_FUTURE_INPUTS),
            "validator_checks": len(VALIDATOR_CHECKS),
            "known_reject_reason_codes": len(taxonomy_codes),
            "required_recovered_gate_references": len(REQUIRED_RECOVERED_GATE_REFERENCES),
            "forbidden_fields": len(FORBIDDEN_FIELDS),
            "forbidden_operations": len(FORBIDDEN_OPERATIONS),
            "validator_contract_only": True,
            "real_judge_outputs_validated_now": False,
            "judge_executed_now": False,
            "judge_outputs_materialized_now": False,
            "row_bodies_read_now": False,
            "repository_source_bodies_read_now": False,
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
        "decision": "Future row-sample judge outputs must pass this schema validator before compiler handoff. This stage defines validation only and does not validate real outputs or compile a manifest.",
    }


def validate_contract(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for required in ["accepted_and_rejected_ids_disjoint", "rejected_rows_have_known_taxonomy_reason", "gate_status_has_all_recovered_keys", "forbidden_raw_fields_absent"]:
        if required not in card.get("validator_checks", []):
            failures.append(f"missing_validator_check:{required}")
    for forbidden in ["raw_row_body", "raw_repository_source_body", "model_logits", "generated_patch"]:
        if forbidden not in card.get("forbidden_fields", []):
            failures.append(f"missing_forbidden_field:{forbidden}")
    for key in [
        "real_judge_outputs_validated_now",
        "judge_executed_now",
        "judge_outputs_materialized_now",
        "row_bodies_read_now",
        "repository_source_bodies_read_now",
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
        "next_best_step": "After future judge outputs are materialized under a separate ticket, run this validator before any judge-to-compiler handoff or manifest compile.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9027 Row-Sample Judge Output Schema Validator Contract",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage defines the future validator for row-sample judge outputs. It does not validate real outputs, run the judge, read row/source bodies, compile a manifest, run trainer dry-run, train, mine, or write `/arxiv`.",
        "",
        f"Validator checks: `{summary['metrics']['validator_checks']}`",
        f"Known reject reason codes: `{summary['metrics']['known_reject_reason_codes']}`",
        f"Real judge outputs validated now: `{summary['metrics']['real_judge_outputs_validated_now']}`",
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
