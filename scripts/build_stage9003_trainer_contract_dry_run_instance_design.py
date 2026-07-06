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
STAGE = 9003
NAME = "stage9003_trainer_contract_dry_run_instance_design"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRAINER_CONTRACT_DRY_RUN_INSTANCE_DESIGN_STAGE9003.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
DESIGN = OUT_DIR / "trainer_contract_dry_run_instance_design.json"

SOURCE_SUMMARIES = {
    "stage8998": ROOT / "runs/summaries/stage8998_trainer_contract_only_dry_run_contract.json",
    "stage8999": ROOT / "runs/summaries/stage8999_trainer_contract_dry_run_contract.json",
    "stage9002": ROOT / "runs/summaries/stage9002_one_run_training_ticket_blocker_audit.json",
}
SOURCE_CONTRACTS = {
    "stage8998": ROOT / "runs/local/artifacts/stage8998_trainer_contract_only_dry_run_contract/trainer_contract_only_dry_run_contract.json",
    "stage8999": ROOT / "runs/local/artifacts/stage8999_trainer_contract_dry_run_contract/trainer_contract_dry_run_contract.json",
    "stage9002": ROOT / "runs/local/artifacts/stage9002_one_run_training_ticket_blocker_audit/one_run_training_ticket_blocker_audit.json",
}

FUTURE_INPUTS = [
    "locked_tiny_training_manifest.jsonl",
    "loss_mask_card.json",
    "manifest_schema_lock.json",
    "trainer_contract_dry_run_input.json",
    "contamination_and_leakage_proof.json",
]

DRY_RUN_FLAGS = [
    "--manifest",
    "--mode",
    "--max-train-rows",
    "--max-eval-rows",
    "--max-strict-rows",
    "--max-steps",
    "--structured-aux-weight",
    "--decoder-ce-weight",
    "--denoise-weight",
    "--require-loss-mask-enforcement-audit",
    "--no-final-checkpoint-export",
    "--cleanup-checkpoints-after-probe",
    "--output-dir",
]

DRY_RUN_VALUES = {
    "--mode": "bounded_decoder_ce_probe",
    "--max-train-rows": 32,
    "--max-eval-rows": 16,
    "--max-strict-rows": 16,
    "--max-steps": 0,
    "--structured-aux-weight": 0.0,
    "--decoder-ce-weight": 0.0,
    "--denoise-weight": 0.0,
    "--output-dir": "runs/local/artifacts/future_stage9xxx_trainer_contract_only_dry_run_execution",
}

REQUIRED_ASSERTIONS = [
    "trainer_cli_resolves",
    "manifest_schema_loads_metadata_only",
    "manifest_schema_hash_matches",
    "manifest_rows_subset_of_locked_manifest",
    "loss_masks_present_for_every_row",
    "loss_mask_card_allows_only_requested_losses",
    "forbidden_losses_zero_weight",
    "decoder_ce_disabled_unless_ticketed",
    "denoise_ce_disabled_unless_ticketed",
    "runtime_reward_disabled",
    "telemetry_paths_under_runs_local_artifacts",
    "output_dir_empty_or_new",
    "dry_run_stops_before_model_forward",
    "no_model_weights_loaded",
    "no_optimizer_created",
    "no_backward_called",
    "no_optimizer_step_called",
    "no_checkpoint_written",
    "no_final_checkpoint_export_path",
    "no_dataset_row_body_loaded",
    "no_repository_source_body_loaded",
    "authority_ticket_required_for_real_training",
]

REQUIRED_OUTPUTS = [
    "trainer_contract_dry_run_report.json",
    "dry_run_contract_report.json",
    "loss_mask_enforcement_audit.json",
    "loss_mask_route_table.json",
    "telemetry_artifact_plan.json",
    "telemetry_output_plan.json",
    "module_delta_expected_zero_card.json",
    "no_model_forward_proof.json",
    "no_training_execution_proof.json",
    "next_one_run_training_ticket_input.json",
]

NO_EXECUTION_METRICS = {
    "trainer_dry_run_authorized_now": False,
    "trainer_dry_run_executed_now": False,
    "trainer_command_invoked_now": False,
    "model_forward_attempted": False,
    "model_weights_loaded": False,
    "optimizer_created": False,
    "backward_attempted": False,
    "backward_called": False,
    "optimizer_step_attempted": False,
    "optimizer_step_called": False,
    "checkpoint_written": False,
    "final_checkpoint_exported": False,
    "dataset_rows_loaded": False,
    "dataset_row_body_loaded": False,
    "repository_source_bodies_loaded": False,
    "row_sample_loaded": False,
    "manifest_materialized_now": False,
    "dry_run_artifacts_materialized_now": False,
    "next_one_run_training_ticket_input_materialized_now": False,
    "arxiv_write_authorized": False,
    "training_authorized": False,
    "data_mining_authorized": False,
    "model_execution_attempted": False,
    "runtime_authorized_flag": False,
    "gemma_execution_attempted": False,
    "harness_scoring_attempted": False,
    "promotion_authorized": False,
    "model_merge_authorized": False,
    "decoder_ce_authorized": False,
    "denoise_ce_authorized": False,
}

FORBIDDEN_OPERATIONS = [
    "INVOKE_TRAINER_NOW",
    "RUN_DRY_RUN_NOW",
    "TRAINER_MODEL_FORWARD",
    "MODEL_WEIGHT_LOAD",
    "OPTIMIZER_CREATE",
    "BACKWARD_CALL",
    "OPTIMIZER_STEP",
    "CHECKPOINT_WRITE",
    "FINAL_CHECKPOINT_EXPORT",
    "DATASET_ROW_BODY_LOAD",
    "DATASET_ROW_LOAD_OUTSIDE_MANIFEST",
    "REPOSITORY_SOURCE_BODY_READ",
    "RUNTIME_EXECUTION",
    "GEMMA_EXECUTION",
    "HARNESS_SCORING",
    "SOURCE_BODY_EMISSION",
    "BODY_EMISSION",
    "WRITE_TO_ARXIV",
    "AUTHORIZE_DECODER_CE",
    "AUTHORIZE_DENOISE_CE",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_design(registry: dict[str, Any]) -> dict[str, Any]:
    summaries = {key: load_json(path) for key, path in SOURCE_SUMMARIES.items()}
    contracts = {key: load_json(path) for key, path in SOURCE_CONTRACTS.items()}
    stage9002_metrics = summaries["stage9002"].get("metrics") or {}
    missing_from_9002 = stage9002_metrics.get("missing_future_artifacts")
    source8998_flags = set(contracts["stage8998"].get("required_flags") or [])
    source8998_outputs = set(contracts["stage8998"].get("required_telemetry_stubs") or [])
    source8999_outputs = set(contracts["stage8999"].get("required_telemetry_outputs") or [])
    checks = {
        "source_stage8998_present": SOURCE_SUMMARIES["stage8998"].exists() and SOURCE_CONTRACTS["stage8998"].exists(),
        "source_stage8998_passed": summaries["stage8998"].get("passed") is True,
        "source_stage8998_flags_covered": set(DRY_RUN_FLAGS).issubset(source8998_flags),
        "source_stage8998_outputs_covered": {"no_model_forward_proof.json", "no_training_execution_proof.json", "next_one_run_training_ticket_input.json"}.issubset(source8998_outputs),
        "source_stage8999_present": SOURCE_SUMMARIES["stage8999"].exists() and SOURCE_CONTRACTS["stage8999"].exists(),
        "source_stage8999_passed": summaries["stage8999"].get("passed") is True,
        "source_stage8999_outputs_covered": {"no_training_execution_proof.json", "next_one_run_training_ticket_input.json"}.issubset(source8999_outputs),
        "source_stage9002_present": SOURCE_SUMMARIES["stage9002"].exists() and SOURCE_CONTRACTS["stage9002"].exists(),
        "source_stage9002_passed": summaries["stage9002"].get("passed") is True,
        "source_stage9002_blocked_training_ticket": stage9002_metrics.get("ticket_instantiation_ready") is False,
        "source_stage9002_missing_dry_run_artifacts": isinstance(missing_from_9002, int) and missing_from_9002 > 0,
        "future_inputs_recorded": len(FUTURE_INPUTS) >= 5,
        "dry_run_flags_recorded": len(DRY_RUN_FLAGS) >= 13,
        "dry_run_values_keep_steps_zero": DRY_RUN_VALUES["--max-steps"] == 0,
        "required_assertions_recorded": len(REQUIRED_ASSERTIONS) >= 20,
        "required_outputs_recorded": len(REQUIRED_OUTPUTS) >= 10,
        "forbidden_operations_recorded": len(FORBIDDEN_OPERATIONS) >= 20,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "TRAINER_CONTRACT_DRY_RUN_INSTANCE_DESIGN_NO_EXECUTION",
        "source_stage_names": {key: value.get("stage_name") for key, value in summaries.items()},
        "future_required_inputs": FUTURE_INPUTS,
        "dry_run_flags": DRY_RUN_FLAGS,
        "dry_run_values": DRY_RUN_VALUES,
        "required_assertions": REQUIRED_ASSERTIONS,
        "required_outputs": REQUIRED_OUTPUTS,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "blocked_until": [
            "stage8997 locked manifest compile artifacts exist",
            "trainer_contract_dry_run_input.json exists",
            "loss_mask_card.json exists",
            "manifest_schema_lock.json exists",
            "contamination_and_leakage_proof.json exists",
            "explicit future dry-run execution authorization is granted",
        ],
        "checks": checks,
        "metrics": {
            "future_required_inputs": len(FUTURE_INPUTS),
            "dry_run_flags": len(DRY_RUN_FLAGS),
            "required_assertions": len(REQUIRED_ASSERTIONS),
            "required_outputs": len(REQUIRED_OUTPUTS),
            "forbidden_operations": len(FORBIDDEN_OPERATIONS),
            "dry_run_instance_designed": True,
            "dry_run_instance_ready_to_execute": False,
            "dry_run_command_materialized_now": False,
            **NO_EXECUTION_METRICS,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Trainer contract dry-run instance is designed but not authorized or executed. It remains blocked until locked manifest/loss-mask/schema/leakage inputs exist and a separate execution authorization stage passes.",
    }


def validate_design(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for required in ["--manifest", "--mode", "--require-loss-mask-enforcement-audit", "--no-final-checkpoint-export", "--cleanup-checkpoints-after-probe"]:
        if required not in card.get("dry_run_flags", []):
            failures.append(f"missing_flag:{required}")
    for required in ["no_model_forward_proof.json", "no_training_execution_proof.json", "next_one_run_training_ticket_input.json", "loss_mask_enforcement_audit.json"]:
        if required not in card.get("required_outputs", []):
            failures.append(f"missing_output:{required}")
    for required in ["dry_run_stops_before_model_forward", "no_model_weights_loaded", "no_optimizer_created", "no_backward_called", "no_dataset_row_body_loaded"]:
        if required not in card.get("required_assertions", []):
            failures.append(f"missing_assertion:{required}")
    for key in NO_EXECUTION_METRICS:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    if card["metrics"].get("dry_run_instance_ready_to_execute") is not False:
        failures.append("dry_run_instance_ready_to_execute")
    if card["metrics"].get("dry_run_command_materialized_now") is not False:
        failures.append("dry_run_command_materialized_now")
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_design(registry)
    failures = validate_design(card)
    DESIGN.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": 0, "failures": failures, **card["metrics"]},
        "artifacts": {"design": str(DESIGN.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "Materialize the locked tiny manifest/loss-mask/schema/leakage artifacts before any trainer dry-run execution. Keep training and model execution closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9003 Trainer Contract Dry-Run Instance Design",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage designs the exact future trainer contract-only dry-run instance needed by Stage9002. It does not invoke the trainer, load model weights, load dataset row bodies, run forward/backward, write checkpoints, train, mine data, or authorize decoder/denoise CE.",
        "",
        f"Dry-run instance ready to execute: `{summary['metrics']['dry_run_instance_ready_to_execute']}`",
        f"Required inputs: `{summary['metrics']['future_required_inputs']}`",
        f"Required outputs: `{summary['metrics']['required_outputs']}`",
        "",
        "The instance remains blocked until locked manifest, loss-mask, schema, and contamination/leakage proof artifacts exist and a separate execution authorization stage passes.",
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
    marker = "## Stage9003 Trainer Contract Dry-Run Instance Design"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "- Designs the future trainer contract-only dry-run instance that Stage9002 requires before one-run training tickets can be instantiated.",
            "- Keeps dry-run execution, model forward/backward, row-body loading, checkpoint writes, decoder CE, denoise CE, runtime, Gemma, harness scoring, and /arxiv writes closed.",
            "- Blocks execution until locked manifest, loss-mask, schema, and contamination/leakage proof artifacts exist and a separate authorization stage passes.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
