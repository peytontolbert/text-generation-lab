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
STAGE = 8999
NAME = "stage8999_trainer_contract_dry_run_contract"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRAINER_CONTRACT_DRY_RUN_CONTRACT_STAGE8999.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT = OUT_DIR / "trainer_contract_dry_run_contract.json"

SOURCE_SUMMARY = ROOT / "runs/summaries/stage8997_locked_tiny_manifest_compile_contract.json"
SOURCE_CONTRACT = ROOT / "runs/local/artifacts/stage8997_locked_tiny_manifest_compile_contract/locked_tiny_manifest_compile_contract.json"

REQUIRED_INPUTS = [
    "trainer_contract_dry_run_input.json",
    "locked_tiny_training_manifest.jsonl",
    "loss_mask_card.json",
    "manifest_schema_lock.json",
    "contamination_and_leakage_proof.json",
]

REQUIRED_DRY_RUN_CHECKS = [
    "trainer_cli_resolves",
    "manifest_schema_loads_metadata_only",
    "loss_mask_card_allows_only_requested_losses",
    "decoder_ce_disabled_unless_ticketed",
    "denoise_ce_disabled_unless_ticketed",
    "no_model_weights_loaded",
    "no_optimizer_created",
    "no_backward_called",
    "no_dataset_row_body_loaded",
    "no_repository_source_body_loaded",
    "telemetry_paths_under_runs_local_artifacts",
    "output_dir_empty_or_new",
    "authority_ticket_required_for_real_training",
]

REQUIRED_TELEMETRY_OUTPUTS = [
    "dry_run_contract_report.json",
    "loss_mask_route_table.json",
    "telemetry_output_plan.json",
    "no_training_execution_proof.json",
    "next_one_run_training_ticket_input.json",
]

FORBIDDEN_OPERATIONS = [
    "TRAINER_DRY_RUN_EXECUTION_NOW",
    "MODEL_WEIGHT_LOAD",
    "OPTIMIZER_CREATE",
    "BACKWARD_CALL",
    "OPTIMIZER_STEP",
    "DATASET_ROW_BODY_LOAD",
    "REPOSITORY_SOURCE_BODY_READ",
    "RUNTIME_EXECUTION",
    "GEMMA_EXECUTION",
    "WRITE_TO_ARXIV",
    "START_TRAINING",
    "AUTHORIZE_DECODER_CE",
    "AUTHORIZE_DENOISE_CE",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_contract(registry: dict[str, Any]) -> dict[str, Any]:
    source_summary = load_json(SOURCE_SUMMARY)
    source_contract = load_json(SOURCE_CONTRACT)
    checks = {
        "source_stage8997_present": SOURCE_SUMMARY.exists() and SOURCE_CONTRACT.exists(),
        "source_stage8997_passed": source_summary.get("passed") is True,
        "source_stage8997_keeps_manifest_closed": (source_summary.get("metrics") or {}).get("manifest_compile_authorized_now") is False,
        "source_stage8997_emits_trainer_dry_run_input": "trainer_contract_dry_run_input.json" in (source_contract.get("required_outputs") or []),
        "required_inputs_recorded": len(REQUIRED_INPUTS) >= 5,
        "required_dry_run_checks_recorded": len(REQUIRED_DRY_RUN_CHECKS) >= 13,
        "required_telemetry_outputs_recorded": len(REQUIRED_TELEMETRY_OUTPUTS) >= 5,
        "forbidden_operations_recorded": len(FORBIDDEN_OPERATIONS) >= 13,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "TRAINER_CONTRACT_DRY_RUN_CONTRACT_NO_EXECUTION",
        "required_inputs": REQUIRED_INPUTS,
        "required_dry_run_checks": REQUIRED_DRY_RUN_CHECKS,
        "required_telemetry_outputs": REQUIRED_TELEMETRY_OUTPUTS,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "checks": checks,
        "metrics": {
            "required_inputs": len(REQUIRED_INPUTS),
            "required_dry_run_checks": len(REQUIRED_DRY_RUN_CHECKS),
            "required_telemetry_outputs": len(REQUIRED_TELEMETRY_OUTPUTS),
            "forbidden_operations": len(FORBIDDEN_OPERATIONS),
            "trainer_dry_run_authorized_now": False,
            "trainer_dry_run_executed_now": False,
            "model_weights_loaded": False,
            "optimizer_created": False,
            "backward_called": False,
            "optimizer_step_called": False,
            "dataset_rows_loaded": False,
            "repository_source_bodies_loaded": False,
            "arxiv_write_authorized": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "model_execution_attempted": False,
            "runtime_authorized_flag": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Trainer dry-run is specified as a future contract only. It must validate CLI/config/loss-mask/telemetry paths without loading model weights, creating an optimizer, reading row bodies, or training.",
    }


def validate_contract(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for required in [
        "no_model_weights_loaded",
        "no_optimizer_created",
        "no_backward_called",
        "authority_ticket_required_for_real_training",
    ]:
        if required not in card.get("required_dry_run_checks", []):
            failures.append(f"missing_check:{required}")
    for key in [
        "trainer_dry_run_authorized_now",
        "trainer_dry_run_executed_now",
        "model_weights_loaded",
        "optimizer_created",
        "backward_called",
        "optimizer_step_called",
        "dataset_rows_loaded",
        "repository_source_bodies_loaded",
        "arxiv_write_authorized",
        "training_authorized",
        "data_mining_authorized",
        "model_execution_attempted",
        "runtime_authorized_flag",
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
        "next_best_step": "After a future locked manifest compile ticket passes, instantiate a trainer contract-only dry run. Do not run trainer from this contract stage.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8999 Trainer Contract Dry Run Contract",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage defines the future trainer contract-only dry run. It does not run the trainer, load model weights, create an optimizer, read row bodies, train, execute runtime, or authorize decoder/denoise CE.",
        "",
        f"Dry-run checks: `{summary['metrics']['required_dry_run_checks']}`",
        f"Telemetry outputs: `{summary['metrics']['required_telemetry_outputs']}`",
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
