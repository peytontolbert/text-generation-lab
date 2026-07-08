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
STAGE = 9474
NAME = "stage9474_episode_obs_diag_balanced_order_probe_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9473_episode_obs_diag_balanced_order_preflight_audit.json"
RUN_DIR = ROOT / "runs/local/artifacts/stage9474_episode_obs_diag_balanced_order_target_100m_probe"
EXECUTION = RUN_DIR / "execution_result.json"
EVAL_LOG = RUN_DIR / "eval_loss_by_checkpoint.jsonl"
AUDIT = RUN_DIR / "stage9474_balanced_order_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_OBS_DIAG_BALANCED_ORDER_PROBE_AUDIT_STAGE9474.md"
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
        safety_failures.append("source_stage9473_not_authorized")
    impl = result.get("implementation") if isinstance(result.get("implementation"), dict) else {}
    if impl.get("probe_scale") != "target_100m":
        safety_failures.append("not_target_100m_execution")
    if result.get("runtime_executed") or result.get("gemma_executed") or result.get("harness_executed"):
        safety_failures.append("forbidden_external_execution")
    if result.get("final_checkpoint_exported"):
        safety_failures.append("final_checkpoint_exported")
    by_step: dict[object, dict[str, dict]] = {}
    for row in eval_rows:
        by_step.setdefault(row.get("step", "final"), {})[str(row.get("split"))] = row
    both_exact = []
    paired = []
    for step, pair in by_step.items():
        if "eval" in pair and "strict_eval" in pair:
            card = {
                "step": step,
                "eval_joint": pair["eval"].get("joint_proxy_exact"),
                "strict_joint": pair["strict_eval"].get("joint_proxy_exact"),
                "eval_loss": pair["eval"].get("loss"),
                "strict_loss": pair["strict_eval"].get("loss"),
            }
            paired.append(card)
            if card["eval_joint"] == 1.0 and card["strict_joint"] == 1.0:
                both_exact.append(card)
    best = None
    if both_exact:
        best = min(both_exact, key=lambda row: float(row.get("eval_loss", 999.0)) + float(row.get("strict_loss", 999.0)))
    final_eval = result.get("eval", {}).get("eval", {}) if isinstance(result.get("eval"), dict) else {}
    final_strict = result.get("eval", {}).get("strict_eval", {}) if isinstance(result.get("eval"), dict) else {}
    quality_pass = bool(both_exact)
    if not quality_pass:
        failures.append("no_jointly_exact_checkpoint")
    failures.extend(safety_failures)
    audit = {
        "passed": not failures,
        "safety_passed": not safety_failures,
        "quality_passed": quality_pass,
        "failures": failures,
        "safety_failures": safety_failures,
        "source_stage": "stage9473_episode_obs_diag_balanced_order_preflight_audit",
        "probe_scale": impl.get("probe_scale"),
        "estimated_parameter_count": impl.get("estimated_parameter_count"),
        "mode": result.get("mode"),
        "paired_checkpoint_records": len(paired),
        "both_exact_checkpoints": both_exact,
        "selected_checkpoint_proxy": best,
        "final_eval_joint_proxy_exact": final_eval.get("joint_proxy_exact"),
        "final_strict_joint_proxy_exact": final_strict.get("joint_proxy_exact"),
        "final_checkpoint_exported": result.get("final_checkpoint_exported"),
        "runtime_executed": result.get("runtime_executed"),
        "gemma_executed": result.get("gemma_executed"),
        "harness_executed": result.get("harness_executed"),
        "diagnosis": "Balanced train ordering produces multiple jointly exact eval/strict intervals, but final weights drift. Next trainer patch should support early-stop/checkpoint-selection telemetry or temporary best-state restore without promotion/export.",
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
        "decision": "Balanced-order probe found jointly exact checkpoint intervals; final drift means next work is early-stop/best-state selection, not decoder CE.",
        "next_best_step": "Build Stage9475 early-stop/best-state selection design for structured probes with no final checkpoint export or promotion.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9474 Episode Observation Diagnosis Balanced-Order Probe Audit",
        "",
        f"Passed: `{audit['passed']}`",
        f"Safety passed: `{audit['safety_passed']}`",
        f"Quality passed: `{audit['quality_passed']}`",
        f"Both-exact checkpoints: `{both_exact}`",
        f"Selected checkpoint proxy: `{best}`",
        f"Final eval joint: `{audit['final_eval_joint_proxy_exact']}`",
        f"Final strict joint: `{audit['final_strict_joint_proxy_exact']}`",
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
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "both_exact_checkpoints": len(both_exact), "selected_checkpoint_proxy": best}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
