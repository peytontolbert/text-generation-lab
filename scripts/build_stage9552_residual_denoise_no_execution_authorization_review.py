#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9552
NAME = "stage9552_residual_denoise_no_execution_authorization_review"
SOURCE_AUDIT = ROOT / "runs/summaries/stage9551_residual_denoise_shortcut_balance_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REVIEW = OUT_DIR / "residual_denoise_no_execution_authorization_review_card.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "RESIDUAL_DENOISE_NO_EXECUTION_AUTHORIZATION_REVIEW_STAGE9552.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

REQUIRED_FUTURE_TELEMETRY = [
    "loss_by_step.jsonl",
    "eval_loss_by_checkpoint.jsonl",
    "row_field_logits.jsonl",
    "row_field_losses.jsonl",
    "row_token_loss.jsonl",
    "eos_length_audit.json",
    "short_output_probe.json",
    "repetition_probe.json",
    "internal_leak_probe.json",
    "sample_generation_audit.json",
    "feature_ablation_attribution.jsonl",
    "activation_patch_recovery.jsonl",
    "module_delta_norms.json",
    "failure_bucket_card.json",
    "cleanup_proof.json",
]
FORBIDDEN_NOW = [
    "model_execution",
    "decoder_ce_training",
    "denoise_ce_training",
    "runtime_verifier_execution",
    "source_body_emission",
    "gemma_execution",
    "harness_execution",
    "scoring",
    "checkpoint_export",
    "promotion",
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def update_registry(summary: dict) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_AUDIT)
    metrics = source.get("metrics") if isinstance(source.get("metrics"), dict) else {}
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9551_not_passed")
    if metrics.get("strongest_forbidden_single_feature_baseline", 1.0) >= 0.80:
        failures.append("shortcut_baseline_too_high")
    if metrics.get("enabled_losses") not in ({}, None):
        failures.append("stage9551_enabled_losses_present")
    if metrics.get("authority_rows") not in ([], None):
        failures.append("stage9551_authority_rows_present")
    if metrics.get("label_leak_rows") not in ([], None):
        failures.append("stage9551_label_leak_rows_present")

    review_items = [
        {"item": "stage9551_shortcut_balance_passed", "passed": source.get("passed") is True},
        {"item": "forbidden_shortcut_baseline_below_0_80", "passed": metrics.get("strongest_forbidden_single_feature_baseline", 1.0) < 0.80},
        {"item": "combined_residual_rows_present", "passed": metrics.get("rows") == 41},
        {"item": "all_losses_closed_in_source", "passed": metrics.get("enabled_losses") in ({}, None)},
        {"item": "source_authority_closed", "passed": metrics.get("authority_rows") in ([], None)},
        {"item": "source_label_leak_rows_empty", "passed": metrics.get("label_leak_rows") in ([], None)},
        {"item": "future_telemetry_requirements_enumerated", "passed": len(REQUIRED_FUTURE_TELEMETRY) >= 12},
        {"item": "same_stage_execution_closed", "passed": True},
    ]
    review_failures = [item for item in review_items if not item["passed"]]
    if review_failures:
        failures.append("review_items_failed")

    authorization_design = {
        "mode": "residual_denoise_probe",
        "review_only": True,
        "execution_command_emitted": False,
        "execution_authorized_now": False,
        "execution_authorized_for_next_stage": False,
        "same_stage_denoise_ce_authorized": False,
        "allowed_future_loss": "denoise_ce_only_after_separate_execution_ticket",
        "source_rows": "stage9545 real residual rows plus stage9549 design examples after Stage9551 shortcut audit",
        "future_probe_caps_recommended": {
            "max_train_rows": 24,
            "max_eval_rows": 8,
            "max_strict_rows": 8,
            "max_steps": 16,
            "probe_scale": "target_100m",
        },
        "required_before_any_denoise_ce": [
            "explicit_user_authorization_for_one_run_ticket",
            "contract_only_preflight_with_manifest_hash",
            "loss_mask_runtime_assertions",
            "denoise_ce_only_loss_assertion",
            "decoder_ce_zero_assertion",
            "runtime_and_gemma_closed_assertion",
            "safe_cleanup_marker_and_run_id",
            "no_final_checkpoint_export",
            "required_telemetry_artifacts_nonempty",
        ],
        "required_future_telemetry": REQUIRED_FUTURE_TELEMETRY,
        "forbidden_now": FORBIDDEN_NOW,
    }
    passed = not failures
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": passed,
        "failures": failures,
        "source_audit": str(SOURCE_AUDIT.relative_to(ROOT)),
        "review_items": review_items,
        "review_failures": review_failures,
        "authorization_design": authorization_design,
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "review_items": len(review_items),
            "review_failures": len(review_failures),
            "source_rows": metrics.get("rows"),
            "strongest_forbidden_single_feature_baseline": metrics.get("strongest_forbidden_single_feature_baseline"),
            "same_stage_execution_authorized": False,
            "same_stage_denoise_ce_authorized": False,
            "future_review_only": True,
            "execution_command_emitted": False,
            "execution_authorized_for_next_stage": False,
            "required_future_telemetry_count": len(REQUIRED_FUTURE_TELEMETRY),
            "model_execution_authorized_next": False,
            "decoder_ce_training_authorized_next": False,
            "denoise_ce_training_authorized_next": False,
            "runtime_authorized": False,
            "promotion_ready": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "No-execution residual-denoise authorization review passed. It defines prerequisites for a future one-run ticket but opens no denoise CE, runtime, model execution, or checkpoint export authority." if passed else "No-execution residual-denoise authorization review failed.",
        "next_best_step": "Build a contract-only residual-denoise one-run ticket/preflight only if explicit execution is still desired; otherwise continue residual repair data expansion. Do not execute from Stage9552.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    REVIEW.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": passed,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **card["metrics"], "failures": failures, "review_failures": len(review_failures)},
        "artifacts": {"review": str(REVIEW.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": card["next_best_step"],
        "created_at_utc": card["created_at_utc"],
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9552 Residual Denoise No-Execution Authorization Review",
        "",
        f"Passed: `{passed}`",
        f"Review failures: `{len(review_failures)}`",
        "Execution authorized now: `False`",
        "Denoise CE authorized now: `False`",
        "Execution authorized for next stage: `False`",
        "",
        "This is review/design only. It requires a separate one-run ticket and telemetry gate before any residual-denoise probe.",
        "",
    ]))
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": passed, "failures": failures, "execution_authorized_for_next_stage": False}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
