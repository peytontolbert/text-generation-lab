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
STAGE = 9486
NAME = "stage9486_target_prefix_observe_phase_probe_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9485_target_prefix_observe_phase_preflight_audit.json"
RUN_DIR = ROOT / "runs/local/artifacts/stage9486_target_prefix_observe_phase_target_100m_probe"
EXECUTION = RUN_DIR / "execution_result.json"
BEST_STATE = RUN_DIR / "best_structured_state_selection.json"
LOGITS = RUN_DIR / "row_field_logits.jsonl"
AUDIT = RUN_DIR / "stage9486_target_prefix_observe_phase_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TARGET_PREFIX_OBSERVE_PHASE_PROBE_AUDIT_STAGE9486.md"
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
    "best_structured_state_selection.json",
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main() -> None:
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    result = load_json(EXECUTION)
    best = load_json(BEST_STATE)
    logits = load_jsonl(LOGITS)
    module_delta = load_json(RUN_DIR / "module_delta_norms.json")

    failures: list[str] = []
    safety_failures: list[str] = []
    missing = [name for name in REQUIRED_ARTIFACTS if not (RUN_DIR / name).is_file()]
    if missing:
        safety_failures.append("missing_required_artifacts")
    if source.get("passed") is not True or not source.get("metrics", {}).get("execution_authorized_for_next_stage"):
        safety_failures.append("source_stage9485_not_authorized")

    impl = result.get("implementation") if isinstance(result.get("implementation"), dict) else {}
    if impl.get("probe_scale") != "target_100m":
        safety_failures.append("not_target_100m_execution")
    if result.get("runtime_executed") or result.get("gemma_executed") or result.get("harness_executed"):
        safety_failures.append("forbidden_external_execution")
    if result.get("final_checkpoint_exported"):
        safety_failures.append("final_checkpoint_exported")
    if best.get("checkpoint_exported") is not False or best.get("promotion_ready") is not False:
        safety_failures.append("best_state_export_or_promotion_open")

    checkpoint_like = sorted(
        str(path.relative_to(RUN_DIR))
        for path in RUN_DIR.rglob("*")
        if path.is_file() and path.suffix in {".pt", ".pth", ".bin", ".safetensors", ".ckpt"}
    )
    if checkpoint_like:
        safety_failures.append("checkpoint_like_artifacts_written")

    delta_buckets = module_delta.get("delta_norm_by_bucket") if isinstance(module_delta.get("delta_norm_by_bucket"), dict) else {}
    if any(delta_buckets.get(key, 0.0) for key in ["decoder", "decoder_attention", "decoder_mlp"]):
        safety_failures.append("decoder_bucket_weights_changed")

    final_eval = result.get("eval", {}).get("eval", {}) if isinstance(result.get("eval"), dict) else {}
    final_strict = result.get("eval", {}).get("strict_eval", {}) if isinstance(result.get("eval"), dict) else {}
    eval_field = final_eval.get("field_exact", {}).get("episode_target_prefix_match", {}) if isinstance(final_eval.get("field_exact"), dict) else {}
    strict_field = final_strict.get("field_exact", {}).get("episode_target_prefix_match", {}) if isinstance(final_strict.get("field_exact"), dict) else {}

    if result.get("fields") != ["episode_target_prefix_match"]:
        failures.append("unexpected_trainable_fields")
    if result.get("train_rows") != 54 or result.get("eval_rows") != 6 or result.get("strict_rows") != 6:
        failures.append("unexpected_row_caps")
    if final_eval.get("joint_proxy_exact") != 1.0:
        failures.append("final_eval_not_exact")
    if final_strict.get("joint_proxy_exact") != 1.0:
        failures.append("final_strict_not_exact")
    if eval_field.get("exact") != 1.0 or strict_field.get("exact") != 1.0:
        failures.append("target_prefix_field_not_exact")
    if best.get("restored") is not True:
        failures.append("best_state_not_restored")
    if best.get("selected_step") != 72:
        failures.append("unexpected_best_state_step")

    wrong_rows = [row for row in logits if row.get("correct") is False]
    high_conf_wrong = [row for row in wrong_rows if row.get("high_confidence_wrong")]
    if wrong_rows:
        failures.append("row_field_logits_have_wrong_rows")
    if high_conf_wrong:
        failures.append("high_confidence_wrong_rows_present")

    failures.extend(safety_failures)
    audit = {
        "passed": not failures,
        "safety_passed": not safety_failures,
        "quality_passed": not [failure for failure in failures if failure not in safety_failures],
        "failures": failures,
        "safety_failures": safety_failures,
        "missing_required_artifacts": missing,
        "source_stage": "stage9485_target_prefix_observe_phase_preflight_audit",
        "probe_scale": impl.get("probe_scale"),
        "estimated_parameter_count": impl.get("estimated_parameter_count"),
        "mode": result.get("mode"),
        "fields": result.get("fields"),
        "train_rows": result.get("train_rows"),
        "eval_rows": result.get("eval_rows"),
        "strict_rows": result.get("strict_rows"),
        "final_eval_joint_proxy_exact": final_eval.get("joint_proxy_exact"),
        "final_strict_joint_proxy_exact": final_strict.get("joint_proxy_exact"),
        "final_eval_loss": final_eval.get("loss"),
        "final_strict_loss": final_strict.get("loss"),
        "row_field_logits_rows": len(logits),
        "wrong_rows": wrong_rows,
        "high_confidence_wrong_rows": high_conf_wrong,
        "best_state_selection": best,
        "module_delta_norms": {
            "decoder_delta_norm": module_delta.get("decoder_delta_norm"),
            "encoder_delta_norm": module_delta.get("encoder_delta_norm"),
            "delta_norm_by_bucket": delta_buckets,
        },
        "checkpoint_like_artifacts": checkpoint_like,
        "diagnosis": "Observe-phase target-prefix verifier objective is learnable when generated/reference evidence is visible and the target-prefix label remains hidden. This validates moving target-prefix out of pre-action policy and back into observation/verifier-phase supervision.",
        "authority": dict(AUTHORITY_CLOSED),
        "model_execution_authorized_next": False,
        "decoder_ce_training_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {
            "audit": str(AUDIT.relative_to(ROOT)),
            "execution_result": str(EXECUTION.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Target-prefix observe-phase target-100M probe passed safely; keep decoder closed and reconnect this verifier-phase target into the full episode-step curriculum.",
        "next_best_step": "Build Stage9487 full episode-step manifest patch that replaces pre-action target-prefix supervision with observe-phase verifier target-prefix rows, then run contract-only preflight.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9486 Target-Prefix Observe-Phase Probe Audit",
        "",
        f"Passed: `{audit['passed']}`",
        f"Safety passed: `{audit['safety_passed']}`",
        f"Quality passed: `{audit['quality_passed']}`",
        f"Final eval joint: `{audit['final_eval_joint_proxy_exact']}`",
        f"Final strict joint: `{audit['final_strict_joint_proxy_exact']}`",
        f"Best state restored: `{best.get('restored')}` at step `{best.get('selected_step')}`",
        f"High-confidence wrong rows: `{len(high_conf_wrong)}`",
        "",
        audit["diagnosis"],
        "",
        "Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, and promotion remain closed.",
        "",
    ]))

    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    reg_rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    reg_rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": summary["passed"],
        "path": str(SUMMARY),
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": summary["next_best_step"],
    })
    reg_rows = sorted(reg_rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = reg_rows
    registry["passed"] = bool(reg_rows)
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(reg_rows),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "stage": STAGE,
        "passed": summary["passed"],
        "failures": failures,
        "final_eval_joint_proxy_exact": final_eval.get("joint_proxy_exact"),
        "final_strict_joint_proxy_exact": final_strict.get("joint_proxy_exact"),
        "high_confidence_wrong_rows": len(high_conf_wrong),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
