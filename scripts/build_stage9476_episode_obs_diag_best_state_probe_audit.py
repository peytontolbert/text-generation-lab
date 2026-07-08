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
STAGE = 9476
NAME = "stage9476_episode_obs_diag_best_state_probe_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9475_episode_obs_diag_best_state_preflight_audit.json"
RUN_DIR = ROOT / "runs/local/artifacts/stage9476_episode_obs_diag_best_state_target_100m_probe"
EXECUTION = RUN_DIR / "execution_result.json"
BEST_STATE = RUN_DIR / "best_structured_state_selection.json"
AUDIT = RUN_DIR / "stage9476_best_state_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_OBS_DIAG_BEST_STATE_PROBE_AUDIT_STAGE9476.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def main() -> None:
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    result = load_json(EXECUTION)
    best = load_json(BEST_STATE)
    failures: list[str] = []
    safety_failures: list[str] = []

    if source.get("passed") is not True or not source.get("metrics", {}).get("execution_authorized_for_next_stage"):
        safety_failures.append("source_stage9475_not_authorized")
    impl = result.get("implementation") if isinstance(result.get("implementation"), dict) else {}
    if impl.get("probe_scale") != "target_100m":
        safety_failures.append("not_target_100m_execution")
    if result.get("runtime_executed") or result.get("gemma_executed") or result.get("harness_executed"):
        safety_failures.append("forbidden_external_execution")
    if result.get("final_checkpoint_exported"):
        safety_failures.append("final_checkpoint_exported")
    if not result.get("required_artifacts_written"):
        safety_failures.append("required_artifacts_missing")

    final_eval = result.get("eval", {}).get("eval", {}) if isinstance(result.get("eval"), dict) else {}
    final_strict = result.get("eval", {}).get("strict_eval", {}) if isinstance(result.get("eval"), dict) else {}
    if final_eval.get("joint_proxy_exact") != 1.0:
        failures.append("final_eval_not_joint_exact")
    if final_strict.get("joint_proxy_exact") != 1.0:
        failures.append("final_strict_not_joint_exact")
    if best.get("enabled") is not True or best.get("restored") is not True:
        failures.append("best_state_not_restored")
    if best.get("eval_joint_proxy_exact") != 1.0 or best.get("strict_joint_proxy_exact") != 1.0:
        failures.append("selected_state_not_joint_exact")
    if best.get("checkpoint_exported") is not False or best.get("promotion_ready") is not False:
        safety_failures.append("best_state_export_or_promotion_open")
    if result.get("best_state_selection") != best:
        failures.append("best_state_sidecar_mismatch")

    checkpoint_like = sorted(
        str(path.relative_to(RUN_DIR))
        for path in RUN_DIR.rglob("*")
        if path.is_file() and path.suffix in {".pt", ".pth", ".bin", ".safetensors", ".ckpt"}
    )
    if checkpoint_like:
        safety_failures.append("checkpoint_like_artifacts_written")

    failures.extend(safety_failures)
    quality_passed = not [failure for failure in failures if failure not in safety_failures]
    audit = {
        "passed": not failures,
        "safety_passed": not safety_failures,
        "quality_passed": quality_passed,
        "failures": failures,
        "safety_failures": safety_failures,
        "source_stage": "stage9475_episode_obs_diag_best_state_preflight_audit",
        "probe_scale": impl.get("probe_scale"),
        "estimated_parameter_count": impl.get("estimated_parameter_count"),
        "mode": result.get("mode"),
        "train_rows": result.get("train_rows"),
        "eval_rows": result.get("eval_rows"),
        "strict_rows": result.get("strict_rows"),
        "final_eval_joint_proxy_exact": final_eval.get("joint_proxy_exact"),
        "final_strict_joint_proxy_exact": final_strict.get("joint_proxy_exact"),
        "final_eval_loss": final_eval.get("loss"),
        "final_strict_loss": final_strict.get("loss"),
        "best_state_selection": best,
        "checkpoint_like_artifacts": checkpoint_like,
        "required_artifacts_written": result.get("required_artifacts_written"),
        "final_checkpoint_exported": result.get("final_checkpoint_exported"),
        "runtime_executed": result.get("runtime_executed"),
        "gemma_executed": result.get("gemma_executed"),
        "harness_executed": result.get("harness_executed"),
        "diagnosis": "In-memory best-state restore converts the balanced-order target-100M episode observation diagnosis probe from final-weight drift to final eval/strict joint exact. This remains a tiny structured-head result, not decoder readiness.",
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
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "execution_result": str(EXECUTION.relative_to(ROOT)), "best_state_selection": str(BEST_STATE.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Best-state restore passed the tiny balanced-order target-100M structured probe; next work should widen the episode diagnosis manifest under the same safety contract before reopening any decoder path.",
        "next_best_step": "Build Stage9477 wider episode observation-diagnosis best-state preflight with per-cell eval/strict coverage and no decoder/runtime/checkpoint authority.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9476 Episode Observation Diagnosis Best-State Probe Audit",
        "",
        f"Passed: `{audit['passed']}`",
        f"Safety passed: `{audit['safety_passed']}`",
        f"Quality passed: `{audit['quality_passed']}`",
        f"Final eval joint: `{audit['final_eval_joint_proxy_exact']}`",
        f"Final strict joint: `{audit['final_strict_joint_proxy_exact']}`",
        f"Best state selection: `{best}`",
        f"Checkpoint-like artifacts: `{checkpoint_like}`",
        "",
        audit["diagnosis"],
        "",
        "Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, and promotion remain closed.",
        "",
    ]))
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    reg_rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    reg_rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    reg_rows = sorted(reg_rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = reg_rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(reg_rows)}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "failures": failures, "best_state_selection": best}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
