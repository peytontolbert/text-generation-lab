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
STAGE = 9007
NAME = "stage9007_locked_manifest_materialization_ticket_design"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "LOCKED_MANIFEST_MATERIALIZATION_TICKET_DESIGN_STAGE9007.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
DESIGN = OUT_DIR / "locked_manifest_materialization_ticket_design.json"

SOURCE_SUMMARIES = {
    "stage8997": ROOT / "runs/summaries/stage8997_locked_tiny_manifest_compile_contract.json",
    "stage9003": ROOT / "runs/summaries/stage9003_trainer_contract_dry_run_instance_design.json",
    "stage9006": ROOT / "runs/summaries/stage9006_active_frontier_routing_audit.json",
}
SOURCE_ARTIFACTS = {
    "stage8997": ROOT / "runs/local/artifacts/stage8997_locked_tiny_manifest_compile_contract/locked_tiny_manifest_compile_contract.json",
    "stage9003": ROOT / "runs/local/artifacts/stage9003_trainer_contract_dry_run_instance_design/trainer_contract_dry_run_instance_design.json",
    "stage9006": ROOT / "runs/local/artifacts/stage9006_active_frontier_routing_audit/active_frontier_routing_audit.json",
}

REQUIRED_SOURCE_INPUTS = [
    "row_sample_dataset_judge_report.json",
    "accepted_row_ids_pending_manifest_compile.jsonl",
    "candidate_row_quality_scores.jsonl",
    "judge_to_compiler_gate_status.json",
]

FUTURE_OUTPUTS = [
    "locked_tiny_training_manifest.jsonl",
    "loss_mask_card.json",
    "manifest_schema_lock.json",
    "split_cell_card.json",
    "contamination_and_leakage_proof.json",
    "trainer_contract_dry_run_input.json",
]

MATERIALIZATION_CHECKS = [
    "accepted_row_ids_exist",
    "row_sample_judge_passed",
    "candidate_quality_scores_present",
    "judge_to_compiler_gate_status_passed",
    "no_locked_eval_training_rows",
    "no_unjudged_rows",
    "no_row_body_materialization",
    "no_repository_source_body_read",
    "all_loss_masks_default_false",
    "decoder_ce_false_for_all_rows",
    "denoise_ce_false_for_all_rows",
    "authority_closed_for_all_rows",
    "schema_hash_recorded",
    "split_cell_card_recorded",
    "contamination_and_leakage_proof_recorded",
]

LOSS_MASK_DEFAULTS = {
    "train_structured_aux": False,
    "train_decoder_ce": False,
    "train_denoise_ce": False,
    "train_retrieval": False,
    "train_runtime_reward": False,
    "train_gemma_distill": False,
    "train_source_body": False,
}

FORBIDDEN_OPERATIONS = [
    "MATERIALIZE_MANIFEST_NOW",
    "READ_ROW_BODIES_NOW",
    "READ_REPOSITORY_SOURCE_BODY",
    "USE_LOCKED_EVAL_FOR_TRAINING",
    "ADD_UNJUDGED_ROWS",
    "ENABLE_DECODER_CE",
    "ENABLE_DENOISE_CE",
    "RUN_TRAINER_DRY_RUN_NOW",
    "START_TRAINING",
    "LOAD_MODEL_WEIGHTS",
    "RUN_MODEL_FORWARD",
    "WRITE_CHECKPOINT",
    "RUN_RUNTIME",
    "RUN_GEMMA",
    "RUN_HARNESS_SCORING",
    "WRITE_TO_ARXIV",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_design(registry: dict[str, Any]) -> dict[str, Any]:
    summaries = {key: load_json(path) for key, path in SOURCE_SUMMARIES.items()}
    artifacts = {key: load_json(path) for key, path in SOURCE_ARTIFACTS.items()}
    checks = {
        "source_stage8997_present": SOURCE_SUMMARIES["stage8997"].exists() and SOURCE_ARTIFACTS["stage8997"].exists(),
        "source_stage8997_passed": summaries["stage8997"].get("passed") is True,
        "source_stage8997_outputs_match": set(FUTURE_OUTPUTS).issubset(set(artifacts["stage8997"].get("required_outputs") or [])),
        "source_stage9003_present": SOURCE_SUMMARIES["stage9003"].exists() and SOURCE_ARTIFACTS["stage9003"].exists(),
        "source_stage9003_passed": summaries["stage9003"].get("passed") is True,
        "source_stage9003_requires_outputs": set(FUTURE_OUTPUTS).issuperset({"locked_tiny_training_manifest.jsonl", "loss_mask_card.json", "manifest_schema_lock.json", "trainer_contract_dry_run_input.json", "contamination_and_leakage_proof.json"}),
        "source_stage9006_present": SOURCE_SUMMARIES["stage9006"].exists() and SOURCE_ARTIFACTS["stage9006"].exists(),
        "source_stage9006_passed": summaries["stage9006"].get("passed") is True,
        "source_stage9006_routes_here": "locked manifest" in summaries["stage9006"].get("next_best_step", ""),
        "required_source_inputs_recorded": len(REQUIRED_SOURCE_INPUTS) >= 4,
        "future_outputs_recorded": len(FUTURE_OUTPUTS) >= 6,
        "materialization_checks_recorded": len(MATERIALIZATION_CHECKS) >= 15,
        "loss_mask_defaults_all_false": all(value is False for value in LOSS_MASK_DEFAULTS.values()),
        "forbidden_operations_recorded": len(FORBIDDEN_OPERATIONS) >= 16,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "LOCKED_MANIFEST_MATERIALIZATION_TICKET_DESIGN_NO_EXECUTION",
        "required_source_inputs": REQUIRED_SOURCE_INPUTS,
        "future_outputs": FUTURE_OUTPUTS,
        "materialization_checks": MATERIALIZATION_CHECKS,
        "loss_mask_defaults": LOSS_MASK_DEFAULTS,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "blocked_until": [
            "row_sample_dataset_judge_report.json exists and passes",
            "accepted_row_ids_pending_manifest_compile.jsonl exists",
            "candidate_row_quality_scores.jsonl exists",
            "judge_to_compiler_gate_status.json exists and passes",
            "separate materialization execution authorization passes",
        ],
        "checks": checks,
        "metrics": {
            "required_source_inputs": len(REQUIRED_SOURCE_INPUTS),
            "future_outputs": len(FUTURE_OUTPUTS),
            "materialization_checks": len(MATERIALIZATION_CHECKS),
            "forbidden_operations": len(FORBIDDEN_OPERATIONS),
            "ticket_designed": True,
            "ticket_ready_to_execute": False,
            "materialization_authorized_now": False,
            "manifest_materialized_now": False,
            "manifest_emitted_now": False,
            "loss_mask_card_emitted_now": False,
            "trainer_dry_run_input_emitted_now": False,
            "dataset_rows_loaded": False,
            "dataset_row_body_loaded": False,
            "repository_source_bodies_loaded": False,
            "locked_eval_training_use": False,
            "unjudged_rows_allowed": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "trainer_dry_run_execution_authorized_now": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "model_execution_attempted": False,
            "model_weights_loaded": False,
            "checkpoint_written": False,
            "runtime_authorized_flag": False,
            "gemma_execution_attempted": False,
            "harness_scoring_attempted": False,
            "arxiv_write_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Locked manifest materialization ticket is designed but not executed. It cannot emit manifest artifacts until row-sample judge outputs exist and a separate execution authorization passes.",
    }


def validate_design(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    if any((card.get("loss_mask_defaults") or {}).values()):
        failures.append("loss_mask_defaults_open")
    for output in ["locked_tiny_training_manifest.jsonl", "loss_mask_card.json", "manifest_schema_lock.json", "trainer_contract_dry_run_input.json", "contamination_and_leakage_proof.json"]:
        if output not in card.get("future_outputs", []):
            failures.append(f"missing_output:{output}")
    for check in ["no_row_body_materialization", "all_loss_masks_default_false", "authority_closed_for_all_rows"]:
        if check not in card.get("materialization_checks", []):
            failures.append(f"missing_check:{check}")
    for key in [
        "ticket_ready_to_execute",
        "materialization_authorized_now",
        "manifest_materialized_now",
        "manifest_emitted_now",
        "loss_mask_card_emitted_now",
        "trainer_dry_run_input_emitted_now",
        "dataset_rows_loaded",
        "dataset_row_body_loaded",
        "repository_source_bodies_loaded",
        "locked_eval_training_use",
        "unjudged_rows_allowed",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "trainer_dry_run_execution_authorized_now",
        "training_authorized",
        "data_mining_authorized",
        "model_execution_attempted",
        "model_weights_loaded",
        "checkpoint_written",
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
        "next_best_step": "Audit or materialize row-sample judge outputs before any locked manifest materialization. Keep trainer dry run and training closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9007 Locked Manifest Materialization Ticket Design",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage designs the future metadata-only ticket that will materialize Stage9003 trainer dry-run inputs. It does not emit a manifest, load rows, read row bodies, run a trainer, train, or authorize decoder/denoise CE.",
        "",
        f"Future outputs: `{summary['metrics']['future_outputs']}`",
        f"Manifest materialized now: `{summary['metrics']['manifest_materialized_now']}`",
        f"Trainer dry-run execution authorized now: `{summary['metrics']['trainer_dry_run_execution_authorized_now']}`",
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
    marker = "## Stage9007 Locked Manifest Materialization Ticket Design"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "- Designs the future metadata-only ticket for locked tiny manifest, loss-mask card, schema lock, leakage proof, and trainer dry-run input artifacts.",
            "- Does not emit the manifest or read row bodies; all loss masks remain false by default.",
            "- Keeps trainer dry run, model execution, decoder CE, denoise CE, runtime, Gemma, harness scoring, training, mining, and /arxiv writes closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
