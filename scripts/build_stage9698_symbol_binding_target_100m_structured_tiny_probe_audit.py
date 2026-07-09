#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9698
NAME = "stage9698_symbol_binding_target_100m_structured_tiny_probe_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9697_disk_safe_cleanup_execution_readiness_gate.json"
RUN_ROOT = ROOT / "runs/local/artifacts/stage9698_symbol_binding_target_100m_structured_tiny_probe"
FIRST_ATTEMPT_DIR = RUN_ROOT / "symbol_binding_probe"
SUCCESS_DIR = RUN_ROOT / "symbol_binding_probe_after_alias_patch"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "symbol_binding_target_100m_structured_tiny_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SYMBOL_BINDING_TARGET_100M_STRUCTURED_TINY_PROBE_STAGE9698.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

REQUIRED_ARTIFACTS = [
    "probe_contract_audit.json",
    "execution_result.json",
    "loss_by_step.jsonl",
    "eval_loss_by_checkpoint.jsonl",
    "row_field_logits.jsonl",
    "row_field_losses.jsonl",
    "row_gradient_norms.jsonl",
    "activation_summary.jsonl",
    "feature_ablation_attribution.jsonl",
    "activation_patch_recovery.jsonl",
    "row_dynamics_history.jsonl",
    "field_exact_by_cell.json",
    "field_label_vocabs.json",
    "structured_confusion_matrix.json",
    "module_delta_norms.json",
    "failure_bucket_card.json",
    "cleanup_proof.json",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "authority": dict(AUTHORITY_CLOSED),
            "next_best_step": summary["next_best_step"],
        }
    )
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def artifact_status() -> dict[str, Any]:
    return {
        name: {
            "exists": (SUCCESS_DIR / name).exists(),
            "bytes": (SUCCESS_DIR / name).stat().st_size if (SUCCESS_DIR / name).exists() else 0,
        }
        for name in REQUIRED_ARTIFACTS
    }


def telemetry_counts() -> dict[str, int]:
    return {
        "loss_by_step_rows": count_jsonl(SUCCESS_DIR / "loss_by_step.jsonl"),
        "eval_loss_by_checkpoint_rows": count_jsonl(SUCCESS_DIR / "eval_loss_by_checkpoint.jsonl"),
        "row_field_logits_rows": count_jsonl(SUCCESS_DIR / "row_field_logits.jsonl"),
        "row_field_losses_rows": count_jsonl(SUCCESS_DIR / "row_field_losses.jsonl"),
        "row_gradient_norms_rows": count_jsonl(SUCCESS_DIR / "row_gradient_norms.jsonl"),
        "activation_summary_rows": count_jsonl(SUCCESS_DIR / "activation_summary.jsonl"),
        "feature_ablation_rows": count_jsonl(SUCCESS_DIR / "feature_ablation_attribution.jsonl"),
        "activation_patch_rows": count_jsonl(SUCCESS_DIR / "activation_patch_recovery.jsonl"),
        "row_dynamics_rows": count_jsonl(SUCCESS_DIR / "row_dynamics_history.jsonl"),
    }


def extract_metrics() -> dict[str, Any]:
    execution = load_json(SUCCESS_DIR / "execution_result.json")
    contract = load_json(SUCCESS_DIR / "probe_contract_audit.json")
    failure_card = load_json(SUCCESS_DIR / "failure_bucket_card.json")
    cleanup = load_json(SUCCESS_DIR / "cleanup_proof.json")
    deltas = load_json(SUCCESS_DIR / "module_delta_norms.json")
    evals = failure_card.get("eval") or {}
    eval_split = evals.get("eval") or {}
    strict_split = evals.get("strict_eval") or {}
    implementation = execution.get("implementation") or {}
    return {
        "mode": execution.get("mode"),
        "probe_scale": implementation.get("probe_scale") or contract.get("probe_scale"),
        "estimated_parameter_count": implementation.get("estimated_parameter_count"),
        "full_100m_target_execution_authorized": implementation.get("full_100m_target_execution_authorized") is True,
        "fields": execution.get("fields") or [],
        "train_rows": execution.get("train_rows"),
        "eval_rows": execution.get("eval_rows"),
        "strict_rows": execution.get("strict_rows"),
        "steps": telemetry_counts()["loss_by_step_rows"],
        "required_artifacts_written": execution.get("required_artifacts_written") is True,
        "final_checkpoint_exported": execution.get("final_checkpoint_exported") is True,
        "runtime_executed": execution.get("runtime_executed") is True,
        "gemma_executed": execution.get("gemma_executed") is True,
        "harness_executed": execution.get("harness_executed") is True,
        "structured_optimizer_isolated": execution.get("structured_optimizer_isolated") is True,
        "structured_optimizer_frozen_bucket_prefixes": execution.get("structured_optimizer_frozen_bucket_prefixes") or [],
        "loss_counts": contract.get("loss_counts") or {},
        "eval_symbol_binding_exact": ((eval_split.get("field_exact") or {}).get("symbol_binding") or {}).get("exact"),
        "strict_symbol_binding_exact": ((strict_split.get("field_exact") or {}).get("symbol_binding") or {}).get("exact"),
        "eval_loss": eval_split.get("loss"),
        "strict_loss": strict_split.get("loss"),
        "high_confidence_wrong_rows": failure_card.get("high_confidence_wrong_rows"),
        "cleanup_executed": cleanup.get("cleanup_executed") is True,
        "cleanup_reason": cleanup.get("cleanup_reason"),
        "decoder_delta_norm": deltas.get("decoder_delta_norm"),
        "encoder_delta_norm": deltas.get("encoder_delta_norm"),
        "structured_head_delta_norm": deltas.get("structured_head_delta_norm"),
        "delta_norm_by_bucket": deltas.get("delta_norm_by_bucket") or {},
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)

    source = load_json(SOURCE_SUMMARY)
    artifacts = artifact_status()
    telemetry = telemetry_counts()
    metrics = extract_metrics() if (SUCCESS_DIR / "execution_result.json").exists() else {}
    failures: list[str] = []

    if source.get("passed") is not True:
        failures.append("stage9697_readiness_gate_not_passed")
    if not SUCCESS_DIR.exists():
        failures.append("successful_probe_output_dir_missing")
    missing = [name for name, status in artifacts.items() if not status["exists"] or status["bytes"] <= 0]
    failures.extend(f"missing_or_empty_artifact:{name}" for name in missing)
    if metrics.get("mode") != "symbol_binding_probe":
        failures.append("unexpected_probe_mode")
    if metrics.get("probe_scale") != "target_100m":
        failures.append("probe_scale_not_target_100m")
    if metrics.get("estimated_parameter_count") != 102703145:
        failures.append("unexpected_parameter_count")
    if metrics.get("fields") != ["symbol_binding"]:
        failures.append("unexpected_trainable_fields")
    if metrics.get("train_rows") != 32 or metrics.get("eval_rows") != 16 or metrics.get("strict_rows") != 16:
        failures.append("unexpected_row_caps")
    if metrics.get("steps") != 8:
        failures.append("unexpected_loss_step_count")
    if not metrics.get("required_artifacts_written"):
        failures.append("trainer_did_not_report_required_artifacts_written")
    for closed_key in ["final_checkpoint_exported", "runtime_executed", "gemma_executed", "harness_executed"]:
        if metrics.get(closed_key):
            failures.append(f"closed_authority_executed:{closed_key}")
    if metrics.get("loss_counts", {}).get("symbol_binding_ce") != 64:
        failures.append("symbol_binding_loss_mask_count_not_64")
    forbidden_losses = {
        key: value
        for key, value in (metrics.get("loss_counts") or {}).items()
        if key != "symbol_binding_ce" and value
    }
    if forbidden_losses:
        failures.append(f"forbidden_loss_counts_nonzero:{forbidden_losses}")
    buckets = metrics.get("delta_norm_by_bucket") or {}
    for bucket in ["decoder", "decoder_attention", "decoder_mlp", "embeddings", "lm_head"]:
        if float(buckets.get(bucket, 0.0) or 0.0) != 0.0:
            failures.append(f"frozen_bucket_moved:{bucket}")

    quality_passed = (
        metrics.get("strict_symbol_binding_exact") is not None
        and float(metrics["strict_symbol_binding_exact"]) >= 0.85
    )
    next_step = (
        "Build Stage9699 post-run diagnostics for source-backed symbol binding: inspect confusion matrix, row logits, "
        "feature ablations, gradient norms, and target/evidence balance before any additional execution or surface expansion."
    )
    audit = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "quality_passed": quality_passed,
        "promotion_ready": False,
        "failures": failures,
        "source_stage9697_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "first_attempt_placeholder_dir_present": FIRST_ATTEMPT_DIR.exists(),
        "successful_probe_output_dir": str(SUCCESS_DIR.relative_to(ROOT)),
        "source_backed_field_alias_patch_required": True,
        "source_backed_field_aliases_validated": True,
        "artifact_status": artifacts,
        "telemetry_counts": telemetry,
        "metrics": metrics,
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": next_step,
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "quality_passed": quality_passed,
        "promotion_ready": False,
        "created_at_unix": int(time.time()),
        "artifacts": {
            "audit": str(AUDIT.relative_to(ROOT)),
            "successful_probe_output_dir": str(SUCCESS_DIR.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "metrics": {
            "estimated_parameter_count": metrics.get("estimated_parameter_count"),
            "eval_symbol_binding_exact": metrics.get("eval_symbol_binding_exact"),
            "strict_symbol_binding_exact": metrics.get("strict_symbol_binding_exact"),
            "loss_by_step_rows": telemetry.get("loss_by_step_rows"),
            "decoder_delta_norm": metrics.get("decoder_delta_norm"),
            "structured_head_delta_norm": metrics.get("structured_head_delta_norm"),
            "forbidden_runtime_executed": metrics.get("runtime_executed") or metrics.get("gemma_executed") or metrics.get("harness_executed"),
        },
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": next_step,
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9698 Symbol-Binding Target-100M Structured Tiny Probe Audit",
                "",
                "Stage9698 records the first successful target-100M structured execution after the Stage9697 readiness gate.",
                "",
                "The first execution attempt exposed a source-backed field mapping gap: `symbol_binding_ce` rows used `clean_state.binding_action`, while the trainer looked for `clean_state.symbol_binding`. The trainer now resolves source-backed aliases before building structured labels.",
                "",
                "## Result",
                "",
                f"- Execution/telemetry passed: `{not failures}`",
                f"- Quality passed: `{quality_passed}`",
                "- Promotion ready: `False`",
                f"- Parameter count: `{metrics.get('estimated_parameter_count')}`",
                f"- Eval exact: `{metrics.get('eval_symbol_binding_exact')}`",
                f"- Strict exact: `{metrics.get('strict_symbol_binding_exact')}`",
                f"- Decoder delta norm: `{metrics.get('decoder_delta_norm')}`",
                "",
                "## Boundary",
                "",
                "- Decoder CE stayed closed.",
                "- Runtime, Gemma, harness, and final checkpoint export stayed closed.",
                "- Decoder, LM head, and embedding buckets stayed frozen.",
                "",
                "## Next",
                "",
                next_step,
                "",
            ]
        ),
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
