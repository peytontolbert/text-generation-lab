#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9864
NAME = "stage9864_edit_localization_target_100m_structured_tiny_probe_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9863_validity_weighted_multilingual_surface_truthfulness_audit.json"
SUCCESS_DIR = ROOT / "runs/local/artifacts/stage9864_edit_localization_target_100m_structured_tiny_probe/edit_localization_probe"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "edit_localization_target_100m_structured_tiny_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EDIT_LOCALIZATION_TARGET_100M_STRUCTURED_TINY_PROBE_STAGE9864.md"
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


def collapse_metrics() -> dict[str, Any]:
    matrix = load_json(SUCCESS_DIR / "structured_confusion_matrix.json")
    edit = matrix.get("edit_localization") or {}
    pred_counts = Counter()
    total = 0
    for gold, preds in edit.items():
        if not isinstance(preds, dict):
            continue
        for pred, count in preds.items():
            pred_counts[str(pred)] += int(count or 0)
            total += int(count or 0)
    dominant_label = None
    dominant_share = 0.0
    if pred_counts and total > 0:
        dominant_label, dominant_count = pred_counts.most_common(1)[0]
        dominant_share = dominant_count / total
    return {
        "pred_counts": dict(sorted(pred_counts.items())),
        "dominant_label": dominant_label,
        "dominant_share": dominant_share,
        "collapsed_to_single_label": bool(dominant_label is not None and dominant_share >= 0.95),
    }


def extract_metrics() -> dict[str, Any]:
    execution = load_json(SUCCESS_DIR / "execution_result.json")
    contract = load_json(SUCCESS_DIR / "probe_contract_audit.json")
    deltas = load_json(SUCCESS_DIR / "module_delta_norms.json")
    per_cell = load_json(SUCCESS_DIR / "field_exact_by_cell.json")
    evals = execution.get("eval") or {}
    eval_split = evals.get("eval") or {}
    strict_split = evals.get("strict_eval") or {}
    implementation = execution.get("implementation") or {}
    collapse = collapse_metrics()
    return {
        "mode": execution.get("mode"),
        "probe_scale": implementation.get("probe_scale") or contract.get("probe_scale"),
        "estimated_parameter_count": implementation.get("estimated_parameter_count"),
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
        "loss_counts": contract.get("loss_counts") or {},
        "eval_edit_localization_exact": ((eval_split.get("field_exact") or {}).get("edit_localization") or {}).get("exact"),
        "strict_edit_localization_exact": ((strict_split.get("field_exact") or {}).get("edit_localization") or {}).get("exact"),
        "multilingual_surface_readiness_passed": ((contract.get("multilingual_surface_readiness") or {}).get("passed") is True),
        "per_cell": per_cell.get("edit_localization") or {},
        "decoder_delta_norm": deltas.get("decoder_delta_norm"),
        "structured_head_delta_norm": deltas.get("structured_head_delta_norm"),
        "delta_norm_by_bucket": deltas.get("delta_norm_by_bucket") or {},
        "collapse": collapse,
    }


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
        failures.append("stage9863_truthfulness_audit_not_passed")
    if not SUCCESS_DIR.exists():
        failures.append("probe_output_dir_missing")
    missing = [name for name, status in artifacts.items() if not status["exists"] or status["bytes"] <= 0]
    failures.extend(f"missing_or_empty_artifact:{name}" for name in missing)
    if metrics.get("mode") != "edit_localization_probe":
        failures.append("unexpected_probe_mode")
    if metrics.get("probe_scale") != "target_100m":
        failures.append("probe_scale_not_target_100m")
    if metrics.get("estimated_parameter_count") != 102717225:
        failures.append("unexpected_parameter_count")
    if metrics.get("fields") != ["edit_localization"]:
        failures.append("unexpected_trainable_fields")
    if metrics.get("train_rows") != 20 or metrics.get("eval_rows") != 16 or metrics.get("strict_rows") != 16:
        failures.append("unexpected_row_caps")
    if metrics.get("steps") != 16:
        failures.append("unexpected_loss_step_count")
    if not metrics.get("required_artifacts_written"):
        failures.append("trainer_did_not_report_required_artifacts_written")
    if not metrics.get("runtime_executed"):
        failures.append("model_execution_not_recorded")
    if not metrics.get("multilingual_surface_readiness_passed"):
        failures.append("multilingual_surface_readiness_failed")
    for closed_key in ["final_checkpoint_exported", "gemma_executed", "harness_executed"]:
        if metrics.get(closed_key):
            failures.append(f"closed_authority_executed:{closed_key}")
    if metrics.get("loss_counts", {}).get("edit_localization_ce") != 52:
        failures.append("edit_localization_loss_mask_count_not_52")
    forbidden_losses = {
        key: value
        for key, value in (metrics.get("loss_counts") or {}).items()
        if key != "edit_localization_ce" and value
    }
    if forbidden_losses:
        failures.append(f"forbidden_loss_counts_nonzero:{forbidden_losses}")
    buckets = metrics.get("delta_norm_by_bucket") or {}
    for bucket in ["decoder", "decoder_attention", "decoder_mlp", "embeddings", "lm_head"]:
        if float(buckets.get(bucket, 0.0) or 0.0) != 0.0:
            failures.append(f"frozen_bucket_moved:{bucket}")

    quality_passed = (
        metrics.get("strict_edit_localization_exact") is not None
        and float(metrics["strict_edit_localization_exact"]) >= 0.3
        and not metrics.get("collapse", {}).get("collapsed_to_single_label")
    )
    next_step = (
        "Build Stage9865 edit-localization collapse diagnostics and remediation plan: inspect row logits, option-token priors, class balance, "
        "and target serialization so the 100M model stops defaulting to label A on the first truthful multilingual execution surface."
    )
    audit = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "quality_passed": quality_passed,
        "promotion_ready": False,
        "failures": failures,
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
            "eval_edit_localization_exact": metrics.get("eval_edit_localization_exact"),
            "strict_edit_localization_exact": metrics.get("strict_edit_localization_exact"),
            "loss_by_step_rows": telemetry.get("loss_by_step_rows"),
            "runtime_executed": metrics.get("runtime_executed"),
            "multilingual_surface_readiness_passed": metrics.get("multilingual_surface_readiness_passed"),
            "collapsed_to_single_label": metrics.get("collapse", {}).get("collapsed_to_single_label"),
            "dominant_predicted_label": metrics.get("collapse", {}).get("dominant_label"),
        },
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": next_step,
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9864 Edit-Localization Target-100M Structured Tiny Probe Audit",
                "",
                "Stage9864 records the first truthful multilingual target-100M structured execution on the v2.7 edit-localization tiny surface.",
                "",
                f"Passed: `{summary['passed']}`",
                f"Quality passed: `{summary['quality_passed']}`",
                f"Eval exact: `{metrics.get('eval_edit_localization_exact')}`",
                f"Strict exact: `{metrics.get('strict_edit_localization_exact')}`",
                f"Collapsed to single label: `{metrics.get('collapse', {}).get('collapsed_to_single_label')}`",
                "",
                f"Next: {next_step}",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "quality_passed": quality_passed, "collapsed_to_single_label": metrics.get("collapse", {}).get("collapsed_to_single_label")}, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
