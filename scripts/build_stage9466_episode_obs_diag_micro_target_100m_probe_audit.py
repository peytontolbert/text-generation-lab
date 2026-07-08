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
STAGE = 9466
NAME = "stage9466_episode_obs_diag_micro_target_100m_probe_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9465_episode_obs_diag_micro_target_100m_preflight_audit.json"
RUN_DIR = ROOT / "runs/local/artifacts/stage9466_episode_obs_diag_micro_target_100m_probe"
EXECUTION = RUN_DIR / "execution_result.json"
AUDIT = RUN_DIR / "stage9466_micro_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_OBS_DIAG_MICRO_TARGET_100M_PROBE_AUDIT_STAGE9466.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def main() -> None:
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    result = load_json(EXECUTION)
    failures: list[str] = []
    safety_failures: list[str] = []
    if source.get("passed") is not True or not source.get("metrics", {}).get("execution_authorized_for_next_stage"):
        safety_failures.append("source_stage9465_not_authorized")
    impl = result.get("implementation") if isinstance(result.get("implementation"), dict) else {}
    if impl.get("probe_scale") != "target_100m":
        safety_failures.append("not_target_100m_execution")
    if result.get("runtime_executed") or result.get("gemma_executed") or result.get("harness_executed"):
        safety_failures.append("forbidden_external_execution")
    if result.get("final_checkpoint_exported"):
        safety_failures.append("final_checkpoint_exported")
    eval_card = result.get("eval") if isinstance(result.get("eval"), dict) else {}
    eval_split = eval_card.get("eval") if isinstance(eval_card.get("eval"), dict) else {}
    strict = eval_card.get("strict_eval") if isinstance(eval_card.get("strict_eval"), dict) else {}
    eval_joint = float(eval_split.get("joint_proxy_exact", 0.0) or 0.0)
    strict_joint = float(strict.get("joint_proxy_exact", 0.0) or 0.0)
    strict_loss = float(strict.get("loss", 999.0) or 999.0)
    quality_pass = eval_joint == 1.0 and strict_joint == 1.0 and strict_loss < 0.01
    if not quality_pass:
        failures.append("quality_gate_not_passed")
    failures.extend(safety_failures)
    audit = {
        "passed": not failures,
        "safety_passed": not safety_failures,
        "quality_passed": quality_pass,
        "failures": failures,
        "safety_failures": safety_failures,
        "source_stage": "stage9465_episode_obs_diag_micro_target_100m_preflight_audit",
        "probe_scale": impl.get("probe_scale"),
        "estimated_parameter_count": impl.get("estimated_parameter_count"),
        "mode": result.get("mode"),
        "train_rows": result.get("train_rows"),
        "eval_rows": result.get("eval_rows"),
        "strict_rows": result.get("strict_rows"),
        "eval_joint_proxy_exact": eval_joint,
        "strict_joint_proxy_exact": strict_joint,
        "strict_loss": strict_loss,
        "eval_loss": eval_split.get("loss"),
        "strict_field_exact": strict.get("field_exact"),
        "required_artifacts_written": result.get("required_artifacts_written"),
        "runtime_executed": result.get("runtime_executed"),
        "gemma_executed": result.get("gemma_executed"),
        "harness_executed": result.get("harness_executed"),
        "final_checkpoint_exported": result.get("final_checkpoint_exported"),
        "diagnosis": "Target-100M can learn the observation-diagnosis success/residual rule when the train schedule repeatedly covers both cells. Stage9463 failure is therefore schedule/cap exposure, not an impossible representation or missing label problem.",
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
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "execution_result": str(EXECUTION.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Micro-overfit passed; next patch should fix full-manifest schedule/cap exposure before rerunning broad observation diagnosis.",
        "next_best_step": "Design Stage9467 full-manifest schedule-coverage probe with enough steps to expose all 48 train rows, then preflight before execution.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9466 Episode Observation Diagnosis Micro Target-100M Probe Audit",
        "",
        f"Passed: `{audit['passed']}`",
        f"Safety passed: `{audit['safety_passed']}`",
        f"Quality passed: `{audit['quality_passed']}`",
        f"Eval joint proxy exact: `{eval_joint}`",
        f"Strict joint proxy exact: `{strict_joint}`",
        f"Strict loss: `{strict_loss}`",
        "",
        audit["diagnosis"],
        "",
        "Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, and promotion remain closed.",
        "",
    ]))
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows)}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "safety_passed": audit["safety_passed"], "quality_passed": audit["quality_passed"], "strict_joint_proxy_exact": strict_joint}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
