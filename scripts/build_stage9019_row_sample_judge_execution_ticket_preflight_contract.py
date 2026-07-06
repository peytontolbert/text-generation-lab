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
STAGE = 9019
NAME = "stage9019_row_sample_judge_execution_ticket_preflight_contract"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9017_SUMMARY = ROOT / "runs/summaries/stage9017_row_sample_judge_output_materialization_contract.json"
SOURCE_9018_SUMMARY = ROOT / "runs/summaries/stage9018_row_sample_judge_output_materialization_blocker_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ROW_SAMPLE_JUDGE_EXECUTION_TICKET_PREFLIGHT_CONTRACT_STAGE9019.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT = OUT_DIR / "row_sample_judge_execution_ticket_preflight_contract.json"

REQUIRED_TICKET_FIELDS = [
    "ticket_id",
    "ticket_stage",
    "source_contract_stage",
    "source_blocker_stage",
    "scope",
    "input_artifacts",
    "output_artifacts",
    "allowed_operations",
    "forbidden_operations",
    "locked_eval_exclusion_proof",
    "row_body_access_policy",
    "source_body_access_policy",
    "decoder_loss_policy",
    "denoise_loss_policy",
    "trainer_policy",
    "authority",
    "diagnostic_closure_required",
]

REQUIRED_INPUT_ARTIFACTS = [
    "row_sample_ticket_authorization_card.json",
    "row_sample_manifest_metadata.jsonl",
    "row_sample_access_audit_card.json",
    "no_locked_eval_sample_proof.json",
]

REQUIRED_OUTPUT_ARTIFACTS = [
    "row_sample_dataset_judge_report.json",
    "candidate_row_quality_scores.jsonl",
    "rejected_row_ids.jsonl",
    "accepted_row_ids_pending_manifest_compile.jsonl",
    "judge_to_compiler_gate_status.json",
]

ALLOWED_OPERATIONS_FUTURE_ONLY = [
    "READ_AUTHORIZED_METADATA_ROWS_ONLY",
    "SCORE_ROW_METADATA_WITH_STATIC_JUDGE_ONLY",
    "WRITE_ROW_IDS_AND_QUALITY_SCORES_ONLY",
    "WRITE_ACCEPT_REJECT_ID_LISTS_ONLY",
    "WRITE_COMPILER_GATE_STATUS_ONLY",
]

FORBIDDEN_OPERATIONS = [
    "READ_ROW_BODY_TEXT",
    "READ_REPOSITORY_SOURCE_BODY",
    "OPEN_UNLISTED_DATASET_FILES",
    "USE_LOCKED_OR_HIDDEN_EVAL_ROWS",
    "MATERIALIZE_TRAINING_MANIFEST",
    "RUN_TRAINER_DRY_RUN",
    "START_TRAINING",
    "RUN_MODEL",
    "RUN_RUNTIME",
    "RUN_GEMMA",
    "RUN_HARNESS_SCORING",
    "WRITE_TO_ARXIV",
    "AUTHORIZE_DECODER_CE",
    "AUTHORIZE_DENOISE_CE",
]

TICKET_TEMPLATE = {
    "ticket_id": "future_stage9xxx_row_sample_judge_execution_ticket",
    "ticket_stage": "future_stage9xxx",
    "source_contract_stage": "stage9017_row_sample_judge_output_materialization_contract",
    "source_blocker_stage": "stage9018_row_sample_judge_output_materialization_blocker_audit",
    "scope": "row_sample_judge_output_materialization_metadata_only",
    "input_artifacts": REQUIRED_INPUT_ARTIFACTS,
    "output_artifacts": REQUIRED_OUTPUT_ARTIFACTS,
    "allowed_operations": ALLOWED_OPERATIONS_FUTURE_ONLY,
    "forbidden_operations": FORBIDDEN_OPERATIONS,
    "locked_eval_exclusion_proof": {"required": True, "artifact": "no_locked_eval_sample_proof.json"},
    "row_body_access_policy": {"read_row_bodies": False, "read_raw_decoder_text": False, "read_raw_encoder_text": False},
    "source_body_access_policy": {"read_repository_source_bodies": False, "read_source_body_spans": False},
    "decoder_loss_policy": {"decoder_ce_authorized": False, "raw_decoder_targets_authorized": False},
    "denoise_loss_policy": {"denoise_ce_authorized": False, "masked_text_targets_authorized": False},
    "trainer_policy": {"trainer_dry_run_authorized": False, "training_authorized": False},
    "authority": dict(AUTHORITY_CLOSED),
    "diagnostic_closure_required": True,
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_contract(registry: dict[str, Any]) -> dict[str, Any]:
    s9017 = load_json(SOURCE_9017_SUMMARY)
    s9018 = load_json(SOURCE_9018_SUMMARY)
    checks = {
        "source_stage9017_present": SOURCE_9017_SUMMARY.exists(),
        "source_stage9017_passed": s9017.get("passed") is True,
        "source_stage9018_present": SOURCE_9018_SUMMARY.exists(),
        "source_stage9018_passed": s9018.get("passed") is True,
        "source_stage9018_blocks_materialization": (s9018.get("metrics") or {}).get("materialization_authorized_now") is False,
        "required_ticket_fields_recorded": len(REQUIRED_TICKET_FIELDS) >= 17,
        "required_inputs_recorded": len(REQUIRED_INPUT_ARTIFACTS) == 4,
        "required_outputs_recorded": len(REQUIRED_OUTPUT_ARTIFACTS) == 5,
        "future_allowed_operations_are_metadata_only": all("BODY" not in op and "TRAIN" not in op for op in ALLOWED_OPERATIONS_FUTURE_ONLY),
        "forbidden_operations_recorded": len(FORBIDDEN_OPERATIONS) >= 14,
        "template_authority_closed": not any(TICKET_TEMPLATE["authority"].values()),
        "template_blocks_row_body_access": TICKET_TEMPLATE["row_body_access_policy"]["read_row_bodies"] is False,
        "template_blocks_source_body_access": TICKET_TEMPLATE["source_body_access_policy"]["read_repository_source_bodies"] is False,
        "template_blocks_decoder_and_denoise": TICKET_TEMPLATE["decoder_loss_policy"]["decoder_ce_authorized"] is False and TICKET_TEMPLATE["denoise_loss_policy"]["denoise_ce_authorized"] is False,
        "template_blocks_trainer": TICKET_TEMPLATE["trainer_policy"]["trainer_dry_run_authorized"] is False and TICKET_TEMPLATE["trainer_policy"]["training_authorized"] is False,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "ROW_SAMPLE_JUDGE_EXECUTION_TICKET_PREFLIGHT_CONTRACT_NO_EXECUTION",
        "required_ticket_fields": REQUIRED_TICKET_FIELDS,
        "ticket_template": TICKET_TEMPLATE,
        "checks": checks,
        "metrics": {
            "required_ticket_fields": len(REQUIRED_TICKET_FIELDS),
            "required_input_artifacts": len(REQUIRED_INPUT_ARTIFACTS),
            "required_output_artifacts": len(REQUIRED_OUTPUT_ARTIFACTS),
            "allowed_operations_future_only": len(ALLOWED_OPERATIONS_FUTURE_ONLY),
            "forbidden_operations": len(FORBIDDEN_OPERATIONS),
            "execution_ticket_instantiated_now": False,
            "row_sample_judge_executed_now": False,
            "judge_outputs_materialized_now": False,
            "row_bodies_read_now": False,
            "repository_source_bodies_read_now": False,
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
        "decision": "This stage defines the future execution-ticket preflight schema only. It does not instantiate a ticket, materialize judge outputs, read row/source bodies, materialize a manifest, run trainer dry-run, train, or mine.",
    }


def validate_contract(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    template = card.get("ticket_template") or {}
    for field in REQUIRED_TICKET_FIELDS:
        if field not in template:
            failures.append(f"missing_ticket_field:{field}")
    if any((template.get("authority") or {}).values()):
        failures.append("template_authority_open")
    for key in [
        "execution_ticket_instantiated_now",
        "row_sample_judge_executed_now",
        "judge_outputs_materialized_now",
        "row_bodies_read_now",
        "repository_source_bodies_read_now",
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
        "next_best_step": "Only after real upstream row-sample artifacts exist, instantiate a separate execution ticket from this schema and audit it before any judge-output materialization.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9019 Row-Sample Judge Execution Ticket Preflight Contract",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage defines the schema for a future row-sample judge execution ticket. It does not instantiate that ticket, run a judge, read row/source bodies, materialize judge outputs, materialize a manifest, run trainer dry-run, train, mine, or write `/arxiv`.",
        "",
        f"Required ticket fields: `{summary['metrics']['required_ticket_fields']}`",
        f"Execution ticket instantiated now: `{summary['metrics']['execution_ticket_instantiated_now']}`",
        f"Judge outputs materialized now: `{summary['metrics']['judge_outputs_materialized_now']}`",
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
