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
STAGE = 8998
NAME = "stage8998_trainer_contract_only_dry_run_contract"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRAINER_CONTRACT_ONLY_DRY_RUN_CONTRACT_STAGE8998.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT = OUT_DIR / "trainer_contract_only_dry_run_contract.json"

SOURCE_SUMMARY = ROOT / "runs/summaries/stage8997_locked_tiny_manifest_compile_contract.json"
SOURCE_CONTRACT = ROOT / "runs/local/artifacts/stage8997_locked_tiny_manifest_compile_contract/locked_tiny_manifest_compile_contract.json"

REQUIRED_INPUTS = [
    "locked_tiny_training_manifest.jsonl",
    "loss_mask_card.json",
    "manifest_schema_lock.json",
    "trainer_contract_dry_run_input.json",
]

REQUIRED_FLAGS = [
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

ALLOWED_MODES = [
    "structured_policy_probe",
    "repo_graph_probe",
    "symbol_binding_probe",
    "edit_localization_probe",
    "patch_operator_probe",
    "verifier_repair_probe",
    "bounded_decoder_ce_probe",
]

REQUIRED_ASSERTIONS = [
    "manifest_schema_hash_matches",
    "manifest_rows_subset_of_locked_manifest",
    "loss_masks_present_for_every_row",
    "forbidden_losses_zero_weight",
    "decoder_ce_disabled_unless_row_loss_mask_allows",
    "denoise_ce_disabled_unless_row_loss_mask_allows",
    "runtime_reward_disabled",
    "no_final_checkpoint_export_path",
    "telemetry_output_paths_under_runs_local_artifacts",
    "dry_run_stops_before_model_forward",
    "no_model_weights_loaded",
    "no_optimizer_created",
    "no_backward_called",
    "no_dataset_row_body_loaded",
    "no_repository_source_body_loaded",
    "authority_ticket_required_for_real_training",
]

REQUIRED_TELEMETRY_STUBS = [
    "trainer_contract_dry_run_report.json",
    "loss_mask_enforcement_audit.json",
    "telemetry_artifact_plan.json",
    "module_delta_expected_zero_card.json",
    "no_model_forward_proof.json",
    "no_training_execution_proof.json",
    "next_one_run_training_ticket_input.json",
]

FORBIDDEN_OPERATIONS = [
    "TRAINER_MODEL_FORWARD",
    "TRAINER_BACKWARD",
    "MODEL_WEIGHT_LOAD",
    "OPTIMIZER_CREATE",
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
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_contract(registry: dict[str, Any]) -> dict[str, Any]:
    source_summary = load_json(SOURCE_SUMMARY)
    source_contract = load_json(SOURCE_CONTRACT)
    checks = {
        "source_stage8997_present": SOURCE_SUMMARY.exists() and SOURCE_CONTRACT.exists(),
        "source_stage8997_passed": source_summary.get("passed") is True,
        "source_stage8997_manifest_compile_closed": (source_summary.get("metrics") or {}).get("manifest_emitted_now") is False,
        "source_stage8997_has_loss_mask_card_output": "loss_mask_card.json" in (source_contract.get("required_outputs") or []),
        "required_inputs_recorded": len(REQUIRED_INPUTS) >= 4,
        "required_flags_recorded": len(REQUIRED_FLAGS) >= 13,
        "allowed_modes_recorded": len(ALLOWED_MODES) >= 7,
        "required_assertions_recorded": len(REQUIRED_ASSERTIONS) >= 16,
        "telemetry_stubs_recorded": len(REQUIRED_TELEMETRY_STUBS) >= 7,
        "forbidden_operations_recorded": len(FORBIDDEN_OPERATIONS) >= 16,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "TRAINER_CONTRACT_ONLY_DRY_RUN_CONTRACT_NO_EXECUTION",
        "required_inputs": REQUIRED_INPUTS,
        "required_flags": REQUIRED_FLAGS,
        "allowed_modes": ALLOWED_MODES,
        "required_assertions": REQUIRED_ASSERTIONS,
        "required_telemetry_stubs": REQUIRED_TELEMETRY_STUBS,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "checks": checks,
        "metrics": {
            "required_inputs": len(REQUIRED_INPUTS),
            "required_flags": len(REQUIRED_FLAGS),
            "allowed_modes": len(ALLOWED_MODES),
            "required_assertions": len(REQUIRED_ASSERTIONS),
            "required_telemetry_stubs": len(REQUIRED_TELEMETRY_STUBS),
            "forbidden_operations": len(FORBIDDEN_OPERATIONS),
            "trainer_dry_run_authorized_now": False,
            "trainer_dry_run_executed_now": False,
            "model_forward_attempted": False,
            "model_weights_loaded": False,
            "backward_attempted": False,
            "optimizer_created": False,
            "optimizer_step_attempted": False,
            "checkpoint_written": False,
            "final_checkpoint_exported": False,
            "dataset_rows_loaded": False,
            "dataset_row_body_loaded": False,
            "repository_source_bodies_loaded": False,
            "arxiv_write_authorized": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "model_execution_attempted": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "gemma_execution_attempted": False,
            "harness_scoring_attempted": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Trainer contract-only dry run is specified as a future contract. It validates CLI flags, loss-mask enforcement, telemetry paths, and dry-run stop conditions, but this stage does not run the trainer or load rows.",
    }


def validate_contract(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for required in ["--manifest", "--mode", "--require-loss-mask-enforcement-audit", "--no-final-checkpoint-export"]:
        if required not in card.get("required_flags", []):
            failures.append(f"missing_flag:{required}")
    for required in ["dry_run_stops_before_model_forward", "loss_masks_present_for_every_row", "forbidden_losses_zero_weight", "no_model_weights_loaded", "no_optimizer_created", "authority_ticket_required_for_real_training"]:
        if required not in card.get("required_assertions", []):
            failures.append(f"missing_assertion:{required}")
    for key in [
        "trainer_dry_run_authorized_now",
        "trainer_dry_run_executed_now",
        "model_forward_attempted",
        "model_weights_loaded",
        "backward_attempted",
        "optimizer_created",
        "optimizer_step_attempted",
        "checkpoint_written",
        "final_checkpoint_exported",
        "dataset_rows_loaded",
        "dataset_row_body_loaded",
        "repository_source_bodies_loaded",
        "arxiv_write_authorized",
        "training_authorized",
        "data_mining_authorized",
        "model_execution_attempted",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
        "gemma_execution_attempted",
        "harness_scoring_attempted",
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
        "next_best_step": "After a future locked manifest compile ticket emits trainer dry-run input, design a trainer contract-only dry-run instance. Do not run the trainer from this contract stage.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8998 Trainer Contract-Only Dry Run Contract",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage defines the future trainer contract-only dry-run contract. It does not run the trainer, load rows, execute model forward/backward, write checkpoints, train, score, or authorize decoder/denoise CE.",
        "",
        f"Required flags: `{summary['metrics']['required_flags']}`",
        f"Required assertions: `{summary['metrics']['required_assertions']}`",
        f"Trainer dry run authorized now: `{summary['metrics']['trainer_dry_run_authorized_now']}`",
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
    marker = "## Stage8998 Trainer Contract-Only Dry Run Contract"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8998 defines the future trainer contract-only dry-run contract: CLI flags, loss-mask enforcement, telemetry path checks, and a hard stop before model forward. Trainer execution remains closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
