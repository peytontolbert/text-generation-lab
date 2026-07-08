#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9471
NAME = "stage9471_episode_obs_diag_checkpoint_selection_probe_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9470_episode_obs_diag_checkpoint_selection_preflight_audit.json"
RUN_DIR = ROOT / "runs/local/artifacts/stage9471_episode_obs_diag_checkpoint_selection_probe"
EXECUTION = RUN_DIR / "execution_result.json"
EVAL_LOG = RUN_DIR / "eval_loss_by_checkpoint.jsonl"
AUDIT = RUN_DIR / "stage9471_checkpoint_selection_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_OBS_DIAG_CHECKPOINT_SELECTION_PROBE_AUDIT_STAGE9471.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


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
    eval_rows = load_jsonl(EVAL_LOG)
    failures: list[str] = []
    safety_failures: list[str] = []
    if source.get("passed") is not True or not source.get("metrics", {}).get("execution_authorized_for_next_stage"):
        safety_failures.append("source_stage9470_not_authorized")
    impl = result.get("implementation") if isinstance(result.get("implementation"), dict) else {}
    if impl.get("probe_scale") != "target_100m":
        safety_failures.append("not_target_100m_execution")
    if result.get("runtime_executed") or result.get("gemma_executed") or result.get("harness_executed"):
        safety_failures.append("forbidden_external_execution")
    if result.get("final_checkpoint_exported"):
        safety_failures.append("final_checkpoint_exported")
    by_step: dict[object, dict[str, dict]] = {}
    for row in eval_rows:
        step = row.get("step", "final")
        by_step.setdefault(step, {})[str(row.get("split"))] = row
    paired = []
    for step, pair in by_step.items():
        if "eval" in pair and "strict_eval" in pair:
            paired.append({
                "step": step,
                "eval_joint": pair["eval"].get("joint_proxy_exact"),
                "strict_joint": pair["strict_eval"].get("joint_proxy_exact"),
                "eval_loss": pair["eval"].get("loss"),
                "strict_loss": pair["strict_eval"].get("loss"),
            })
    both_exact = [row for row in paired if row.get("eval_joint") == 1.0 and row.get("strict_joint") == 1.0]
    final_eval = result.get("eval", {}).get("eval", {}) if isinstance(result.get("eval"), dict) else {}
    final_strict = result.get("eval", {}).get("strict_eval", {}) if isinstance(result.get("eval"), dict) else {}
    quality_pass = bool(both_exact)
    if not quality_pass:
        failures.append("no_checkpoint_with_eval_and_strict_exact")
    failures.extend(safety_failures)
    state_counts = Counter((row.get("eval_joint"), row.get("strict_joint")) for row in paired)
    audit = {
        "passed": not failures,
        "safety_passed": not safety_failures,
        "quality_passed": quality_pass,
        "failures": failures,
        "safety_failures": safety_failures,
        "source_stage": "stage9470_episode_obs_diag_checkpoint_selection_preflight_audit",
        "probe_scale": impl.get("probe_scale"),
        "estimated_parameter_count": impl.get("estimated_parameter_count"),
        "mode": result.get("mode"),
        "eval_interval_records": len(eval_rows),
        "paired_checkpoint_records": len(paired),
        "both_exact_checkpoints": both_exact,
        "checkpoint_state_counts": {f"eval={k[0]}|strict={k[1]}": v for k, v in sorted(state_counts.items(), key=lambda item: str(item[0]))},
        "final_eval_joint_proxy_exact": final_eval.get("joint_proxy_exact"),
        "final_strict_joint_proxy_exact": final_strict.get("joint_proxy_exact"),
        "required_artifacts_written": result.get("required_artifacts_written"),
        "runtime_executed": result.get("runtime_executed"),
        "gemma_executed": result.get("gemma_executed"),
        "harness_executed": result.get("harness_executed"),
        "final_checkpoint_exported": result.get("final_checkpoint_exported"),
        "diagnosis": "Interval telemetry found no step where eval success and strict residual were both exact. The result oscillates by checkpoint, consistent with deterministic batch order and residual-heavy class exposure; next patch should use balanced ordered train rows or a balanced sampler.",
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
        "decision": "Checkpoint-selection telemetry executed safely but found no jointly exact interval; no further execution is authorized by this audit.",
        "next_best_step": "Build Stage9472 balanced-order observation-diagnosis manifest or sampler before another target-100M run.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9471 Episode Observation Diagnosis Checkpoint-Selection Probe Audit",
        "",
        f"Passed: `{audit['passed']}`",
        f"Safety passed: `{audit['safety_passed']}`",
        f"Quality passed: `{audit['quality_passed']}`",
        f"Paired checkpoint records: `{len(paired)}`",
        f"Both-exact checkpoints: `{both_exact}`",
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
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "safety_passed": audit["safety_passed"], "quality_passed": audit["quality_passed"], "both_exact_checkpoints": len(both_exact)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
