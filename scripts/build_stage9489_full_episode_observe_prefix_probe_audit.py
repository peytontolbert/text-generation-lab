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
STAGE = 9489
NAME = "stage9489_full_episode_observe_prefix_probe_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9488_full_episode_observe_prefix_preflight_audit.json"
RUN_DIR = ROOT / "runs/local/artifacts/stage9489_full_episode_observe_prefix_target_100m_probe"
EXECUTION = RUN_DIR / "execution_result.json"
BEST_STATE = RUN_DIR / "best_structured_state_selection.json"
LOGITS = RUN_DIR / "row_field_logits.jsonl"
EVAL_HISTORY = RUN_DIR / "eval_loss_by_checkpoint.jsonl"
AUDIT = RUN_DIR / "stage9489_full_episode_observe_prefix_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "FULL_EPISODE_OBSERVE_PREFIX_PROBE_AUDIT_STAGE9489.md"
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
    eval_history = load_jsonl(EVAL_HISTORY)
    module_delta = load_json(RUN_DIR / "module_delta_norms.json")

    failures: list[str] = []
    safety_failures: list[str] = []
    missing = [name for name in REQUIRED_ARTIFACTS if not (RUN_DIR / name).is_file()]
    if missing:
        safety_failures.append("missing_required_artifacts")
    if source.get("passed") is not True or not source.get("metrics", {}).get("execution_authorized_for_next_stage"):
        safety_failures.append("source_stage9488_not_authorized")

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
    if final_eval.get("joint_proxy_exact") != 1.0:
        failures.append("final_eval_not_exact")
    if final_strict.get("joint_proxy_exact") != 1.0:
        failures.append("final_strict_not_exact")
    if best.get("restored") is not True:
        failures.append("no_jointly_exact_best_state_to_restore")

    wrong_rows = [row for row in logits if row.get("correct") is False]
    high_conf_wrong = [row for row in wrong_rows if row.get("high_confidence_wrong")]
    by_field_split: dict[str, int] = {}
    for row in wrong_rows:
        key = f"{row.get('split')}::{row.get('field')}::{row.get('target')}=>{row.get('pred')}"
        by_field_split[key] = by_field_split.get(key, 0) + 1

    near_exact_checkpoints: list[dict] = []
    for idx in range(0, len(eval_history) - 1, 2):
        eval_row = eval_history[idx]
        strict_row = eval_history[idx + 1]
        if not eval_row.get("checkpoint_eval") or not strict_row.get("checkpoint_eval"):
            continue
        if float(eval_row.get("joint_proxy_exact", 0.0)) >= 0.8 or float(strict_row.get("joint_proxy_exact", 0.0)) >= 0.8:
            near_exact_checkpoints.append({
                "step": eval_row.get("step"),
                "eval_joint": eval_row.get("joint_proxy_exact"),
                "strict_joint": strict_row.get("joint_proxy_exact"),
                "eval_loss": eval_row.get("loss"),
                "strict_loss": strict_row.get("loss"),
                "eval_field_exact": eval_row.get("field_exact"),
                "strict_field_exact": strict_row.get("field_exact"),
            })

    failures.extend(safety_failures)
    audit = {
        "passed": not failures,
        "safety_passed": not safety_failures,
        "quality_passed": not [failure for failure in failures if failure not in safety_failures],
        "failures": failures,
        "safety_failures": safety_failures,
        "missing_required_artifacts": missing,
        "source_stage": "stage9488_full_episode_observe_prefix_preflight_audit",
        "probe_scale": impl.get("probe_scale"),
        "estimated_parameter_count": impl.get("estimated_parameter_count"),
        "mode": result.get("mode"),
        "fields": result.get("fields"),
        "train_rows": result.get("train_rows"),
        "eval_rows": result.get("eval_rows"),
        "strict_rows": result.get("strict_rows"),
        "final_eval_joint_proxy_exact": final_eval.get("joint_proxy_exact"),
        "final_strict_joint_proxy_exact": final_strict.get("joint_proxy_exact"),
        "final_eval_field_exact": final_eval.get("field_exact"),
        "final_strict_field_exact": final_strict.get("field_exact"),
        "wrong_rows": wrong_rows,
        "wrong_by_field_split": by_field_split,
        "high_confidence_wrong_rows": high_conf_wrong,
        "near_exact_checkpoints": near_exact_checkpoints,
        "best_state_selection": best,
        "checkpoint_like_artifacts": checkpoint_like,
        "module_delta_norms": {
            "decoder_delta_norm": module_delta.get("decoder_delta_norm"),
            "encoder_delta_norm": module_delta.get("encoder_delta_norm"),
            "delta_norm_by_bucket": delta_buckets,
        },
        "diagnosis": "Safe quality failure. Moving target-prefix to observe-phase helped during interval evaluation, but the jointly exact restore gate never opened because verifier-derived failure_type/outcome/value are still being trained as pre-action targets. The next patch should make episode verifier fields phase-aware instead of treating all five heads as one policy surface.",
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
        "decision": "Full observe-prefix rejoin probe failed quality safely; keep decoder closed and split verifier-derived fields into observe-phase supervision.",
        "next_best_step": "Build Stage9490 phase-aware episode verifier manifest: move failure_type, repair_outcome, step_value, and target_prefix_match to observe/verifier-phase rows with visible observation evidence; keep boundary/action policy separate.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9489 Full Episode Observe-Prefix Probe Audit",
        "",
        f"Passed: `{audit['passed']}`",
        f"Safety passed: `{audit['safety_passed']}`",
        f"Quality passed: `{audit['quality_passed']}`",
        f"Final eval joint: `{audit['final_eval_joint_proxy_exact']}`",
        f"Final strict joint: `{audit['final_strict_joint_proxy_exact']}`",
        f"Wrong rows: `{len(wrong_rows)}`",
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
        "safety_passed": audit["safety_passed"],
        "final_eval_joint_proxy_exact": final_eval.get("joint_proxy_exact"),
        "final_strict_joint_proxy_exact": final_strict.get("joint_proxy_exact"),
        "wrong_rows": len(wrong_rows),
        "failures": failures,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
