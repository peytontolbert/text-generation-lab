#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
    from scripts.build_stage9096_trainer_runtime_assertion_inventory import REQUIRED_TELEMETRY_ARTIFACTS
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from build_stage9096_trainer_runtime_assertion_inventory import REQUIRED_TELEMETRY_ARTIFACTS  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9100
NAME = "stage9100_contract_only_artifact_schema_design"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9099 = ROOT / "runs/summaries/stage9099_current_frontier_reconciliation_after_runtime_assertion_graph.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CONTRACT_ONLY_ARTIFACT_SCHEMA_DESIGN_STAGE9100.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SCHEMA = OUT_DIR / "contract_only_artifact_schema_design.json"

CONTRACT_TELEMETRY_ARTIFACTS = list(dict.fromkeys([*REQUIRED_TELEMETRY_ARTIFACTS, "row_field_logits.jsonl", "row_field_losses.jsonl"]))

CONTRACT_ONLY_SCHEMA: dict[str, dict[str, Any]] = {
    "trainer_contract_dry_run_report.json": {
        "kind": "json",
        "required_keys": ["passed", "run_id", "mode", "manifest_hash", "row_caps", "loss_weights", "execution_authorized", "model_forward_attempted", "training_attempted"],
        "must_equal": {"execution_authorized": False, "model_forward_attempted": False, "training_attempted": False},
    },
    "loss_mask_enforcement_audit.json": {
        "kind": "json",
        "required_keys": ["passed", "rows_checked", "unsafe_loss_mask_rows", "forbidden_losses", "enabled_loss_counts"],
        "must_equal": {"unsafe_loss_mask_rows": 0},
    },
    "runtime_assertion_plan.json": {
        "kind": "json",
        "required_keys": ["passed", "assertion_families", "required_telemetry_artifacts", "forbidden_operations", "hard_stop_before_model_forward"],
        "must_equal": {"hard_stop_before_model_forward": True},
    },
    "telemetry_artifact_plan.json": {
        "kind": "json",
        "required_keys": ["passed", "required_artifacts", "jsonl_nonempty_policy", "empty_stub_policy", "artifact_root"],
        "contains_all": {"required_artifacts": CONTRACT_TELEMETRY_ARTIFACTS},
    },
    "no_model_forward_proof.json": {
        "kind": "json",
        "required_keys": ["passed", "model_forward_attempted", "model_weights_loaded", "optimizer_created", "backward_attempted"],
        "must_equal": {"model_forward_attempted": False, "model_weights_loaded": False, "optimizer_created": False, "backward_attempted": False},
    },
    "no_training_execution_proof.json": {
        "kind": "json",
        "required_keys": ["passed", "trainer_executed", "optimizer_step_attempted", "checkpoint_written", "final_checkpoint_exported"],
        "must_equal": {"trainer_executed": False, "optimizer_step_attempted": False, "checkpoint_written": False, "final_checkpoint_exported": False},
    },
    "module_delta_expected_zero_card.json": {
        "kind": "json",
        "required_keys": ["passed", "decoder_delta_norm", "encoder_delta_norm", "structured_head_delta_norm", "all_module_delta_zero"],
        "must_equal": {"decoder_delta_norm": 0.0, "encoder_delta_norm": 0.0, "structured_head_delta_norm": 0.0, "all_module_delta_zero": True},
    },
    "next_execution_authorization_input.json": {
        "kind": "json",
        "required_keys": ["passed", "required_upstream_stages", "required_review_card", "still_forbidden_operations", "next_step"],
    },
}

FORBIDDEN_OPERATIONS = [
    "TRAINER_INVOCATION",
    "CONTRACT_ONLY_INVOCATION_NOW",
    "MODEL_FORWARD",
    "MODEL_WEIGHT_LOAD",
    "OPTIMIZER_CREATE",
    "BACKWARD",
    "OPTIMIZER_STEP",
    "CHECKPOINT_WRITE",
    "FINAL_CHECKPOINT_EXPORT",
    "DATASET_ROW_BODY_LOAD",
    "REPOSITORY_SOURCE_BODY_READ",
    "ROUTE_TO_LOSS_TRANSLATION",
    "DECODER_CE_TRAINING",
    "DENOISE_CE_TRAINING",
    "RUNTIME_EXECUTION",
    "GEMMA_EXECUTION",
    "HARNESS_SCORING",
    "SOURCE_BODY_EMISSION",
    "BODY_EMISSION",
    "WRITE_TO_ARXIV",
    "CLEANUP_EXECUTION",
]

JSONL_ARTIFACT_REQUIREMENTS = {
    "loss_by_step.jsonl": ["step", "loss", "grad_norm"],
    "eval_loss_by_checkpoint.jsonl": ["split", "rows"],
    "row_field_logits.jsonl": ["row_id", "field", "target", "pred", "confidence", "entropy", "top_k", "high_confidence_wrong"],
    "row_field_losses.jsonl": ["row_id", "field", "loss", "exact"],
    "row_token_loss.jsonl": ["row_id", "positions", "mean_loss", "token_count"],
    "row_gradient_norms.jsonl": ["row_id", "total_grad_norm", "grad_norm_by_bucket", "gradient_scope"],
    "activation_summary.jsonl": ["row_id", "layers", "activation_cache_present"],
    "feature_ablation_attribution.jsonl": ["row_id", "field", "feature_attribution", "top_feature_group"],
    "activation_patch_recovery.jsonl": ["row_id", "field", "patched_layer", "logit_recovery_fraction"],
    "row_dynamics_history.jsonl": ["row_id", "forgetting_events", "prediction_flip_count"],
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_schema(registry: dict[str, Any]) -> dict[str, Any]:
    s9099 = load_json(SOURCE_9099)
    schema_artifacts = set(CONTRACT_ONLY_SCHEMA)
    required_jsonl = set(JSONL_ARTIFACT_REQUIREMENTS)
    telemetry = set(CONTRACT_TELEMETRY_ARTIFACTS)
    checks = {
        "source_stage9099_passed": s9099.get("passed") is True,
        "schema_artifacts_recorded": len(CONTRACT_ONLY_SCHEMA) >= 8,
        "forbidden_operations_recorded": len(FORBIDDEN_OPERATIONS) >= 20,
        "telemetry_artifacts_included": telemetry.issubset(set(CONTRACT_ONLY_SCHEMA["telemetry_artifact_plan.json"]["contains_all"]["required_artifacts"])),
        "jsonl_artifact_requirements_included": required_jsonl.issubset(telemetry),
        "no_contract_only_invocation_now": True,
        "registry_frontier_stage9099": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9099,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "CONTRACT_ONLY_ARTIFACT_SCHEMA_DESIGN_NO_INVOCATION",
        "contract_only_schema": copy.deepcopy(CONTRACT_ONLY_SCHEMA),
        "jsonl_artifact_requirements": copy.deepcopy(JSONL_ARTIFACT_REQUIREMENTS),
        "forbidden_operations": list(FORBIDDEN_OPERATIONS),
        "checks": checks,
        "metrics": {
            "schema_artifacts": len(schema_artifacts),
            "required_telemetry_artifacts": len(CONTRACT_TELEMETRY_ARTIFACTS),
            "jsonl_artifact_requirements": len(JSONL_ARTIFACT_REQUIREMENTS),
            "forbidden_operations": len(FORBIDDEN_OPERATIONS),
            "trainer_executed_now": False,
            "contract_only_invoked_now": False,
            "runtime_assertions_executed_now": False,
            "route_to_loss_translation_ready_now": False,
            "model_input_rows_now": 0,
            "candidate_rows_materialized": 0,
            "model_forward_attempted": False,
            "model_weights_loaded": False,
            "optimizer_created": False,
            "backward_attempted": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "arxiv_read_authorized_for_compiler": False,
            "arxiv_write_authorized": False,
            "cleanup_authorized_now": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Designed the future contract-only artifact schema without invoking trainer contract-only mode. The schema records required proof files, telemetry plans, runtime assertion plans, zero-delta module proof, and next authorization input while keeping trainer invocation, row loading, route-to-loss translation, model forward, decoder CE, denoise CE, runtime, /arxiv IO, cleanup, and training closed.",
    }


def validate_schema(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9099, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for artifact in [
        "trainer_contract_dry_run_report.json",
        "loss_mask_enforcement_audit.json",
        "runtime_assertion_plan.json",
        "telemetry_artifact_plan.json",
        "no_model_forward_proof.json",
        "no_training_execution_proof.json",
        "module_delta_expected_zero_card.json",
        "next_execution_authorization_input.json",
    ]:
        if artifact not in card.get("contract_only_schema", {}):
            failures.append(f"missing_schema_artifact:{artifact}")
    for artifact in CONTRACT_TELEMETRY_ARTIFACTS:
        required = card.get("contract_only_schema", {}).get("telemetry_artifact_plan.json", {}).get("contains_all", {}).get("required_artifacts", [])
        if artifact not in required:
            failures.append(f"missing_required_telemetry_artifact:{artifact}")
    for operation in FORBIDDEN_OPERATIONS:
        if operation not in card.get("forbidden_operations", []):
            failures.append(f"missing_forbidden_operation:{operation}")
    for key in [
        "trainer_executed_now",
        "contract_only_invoked_now",
        "runtime_assertions_executed_now",
        "route_to_loss_translation_ready_now",
        "model_forward_attempted",
        "model_weights_loaded",
        "optimizer_created",
        "backward_attempted",
        "training_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
        "arxiv_read_authorized_for_compiler",
        "arxiv_write_authorized",
        "cleanup_authorized_now",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    for key in ["model_input_rows_now", "candidate_rows_materialized"]:
        if card["metrics"].get(key) != 0:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    schema = build_schema(registry)
    failures = validate_schema(schema, registry)
    SCHEMA.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "failures": failures, **schema["metrics"]},
        "artifacts": {"schema": str(SCHEMA.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": schema["decision"] if not failures else "Contract-only artifact schema design failed.",
        "next_best_step": "Audit contract-only artifact schema negative cases without invoking trainer or loading rows.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9100 Contract-Only Artifact Schema Design",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Defines the future trainer contract-only artifact schema. This stage does not invoke trainer contract-only mode, load rows, translate route cards, execute runtime assertions, run model forward, train, clean, or touch /arxiv.",
        "",
        f"Schema artifacts: `{schema['metrics']['schema_artifacts']}`",
        f"Required telemetry artifacts: `{schema['metrics']['required_telemetry_artifacts']}`",
        f"Forbidden operations: `{schema['metrics']['forbidden_operations']}`",
        "",
        f"Next: {summary['next_best_step']}",
    ]) + "\n", encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))), "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
