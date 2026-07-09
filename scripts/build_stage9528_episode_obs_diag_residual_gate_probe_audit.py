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
STAGE = 9528
NAME = "stage9528_episode_obs_diag_residual_gate_probe_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9527_episode_obs_diag_residual_gate_preflight_audit.json"
RUN_DIR = ROOT / "runs/local/artifacts/stage9528_episode_obs_diag_residual_gate_target_100m_probe"
EXECUTION = RUN_DIR / "execution_result.json"
BEST_STATE = RUN_DIR / "best_structured_state_selection.json"
LOGITS = RUN_DIR / "row_field_logits.jsonl"
AUDIT = RUN_DIR / "stage9528_episode_obs_diag_residual_gate_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_OBS_DIAG_RESIDUAL_GATE_PROBE_AUDIT_STAGE9528.md"
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
    best = load_json(BEST_STATE) or result.get("best_state_selection", {})
    logits = load_jsonl(LOGITS)
    safety_failures: list[str] = []
    quality_failures: list[str] = []
    if source.get("passed") is not True or not source.get("metrics", {}).get("execution_authorized_for_next_stage"):
        safety_failures.append("stage9527_not_authorized")
    impl = result.get("implementation") if isinstance(result.get("implementation"), dict) else {}
    if impl.get("probe_scale") != "target_100m":
        safety_failures.append("not_target_100m_execution")
    if result.get("runtime_executed") or result.get("gemma_executed") or result.get("harness_executed"):
        safety_failures.append("forbidden_external_execution")
    if result.get("final_checkpoint_exported"):
        safety_failures.append("final_checkpoint_exported")
    if result.get("required_artifacts_written") is not True:
        safety_failures.append("required_artifacts_missing")
    checkpoint_like = sorted(
        str(path.relative_to(RUN_DIR))
        for path in RUN_DIR.rglob("*")
        if path.is_file() and path.suffix in {".pt", ".pth", ".bin", ".safetensors", ".ckpt"}
    )
    if checkpoint_like:
        safety_failures.append("checkpoint_like_artifacts_written")
    final_eval = result.get("eval", {}).get("eval", {}) if isinstance(result.get("eval"), dict) else {}
    final_strict = result.get("eval", {}).get("strict_eval", {}) if isinstance(result.get("eval"), dict) else {}
    if final_eval.get("joint_proxy_exact") != 1.0:
        quality_failures.append("final_eval_not_exact")
    if final_strict.get("joint_proxy_exact") != 1.0:
        quality_failures.append("final_strict_not_exact")
    if best.get("restored") is not True:
        quality_failures.append("no_jointly_exact_best_state_to_restore")
    wrong_rows = [row for row in logits if row.get("correct") is False]
    high_conf_wrong = [row for row in wrong_rows if row.get("high_confidence_wrong")]
    failures = [*safety_failures, *quality_failures]
    audit = {
        "passed": not failures,
        "safety_passed": not safety_failures,
        "quality_passed": not quality_failures,
        "strict_residual_fixed": final_strict.get("joint_proxy_exact") == 1.0,
        "failures": failures,
        "safety_failures": safety_failures,
        "quality_failures": quality_failures,
        "source_stage": "stage9527_episode_obs_diag_residual_gate_preflight_audit",
        "probe_scale": impl.get("probe_scale"),
        "estimated_parameter_count": impl.get("estimated_parameter_count"),
        "mode": result.get("mode"),
        "fields": result.get("fields"),
        "train_rows": result.get("train_rows"),
        "eval_rows": result.get("eval_rows"),
        "strict_rows": result.get("strict_rows"),
        "final_eval_joint_proxy_exact": final_eval.get("joint_proxy_exact"),
        "final_strict_joint_proxy_exact": final_strict.get("joint_proxy_exact"),
        "field_exact_eval": final_eval.get("field_exact"),
        "field_exact_strict": final_strict.get("field_exact"),
        "field_loss_eval": final_eval.get("field_loss"),
        "field_loss_strict": final_strict.get("field_loss"),
        "best_state_selection": best,
        "wrong_rows": wrong_rows,
        "wrong_row_count": len(wrong_rows),
        "high_confidence_wrong_rows": high_conf_wrong,
        "high_confidence_wrong_count": len(high_conf_wrong),
        "checkpoint_like_artifacts": checkpoint_like,
        "comparison_to_stage9524": {
            "stage9524_eval_joint_proxy_exact": 0.9444444444444444,
            "stage9524_strict_joint_proxy_exact": 0.8333333333333334,
            "stage9524_wrong_rows": 4,
            "stage9524_high_confidence_wrong_rows": 2,
            "residual_gate_eval_delta": (final_eval.get("joint_proxy_exact") or 0.0) - 0.9444444444444444,
            "residual_gate_strict_delta": (final_strict.get("joint_proxy_exact") or 0.0) - 0.8333333333333334,
        },
        "diagnosis": "Safe partial quality recovery. Residual-gate features fixed strict residuals and removed the false-success high-confidence errors, but one eval boundary-miss failure-type row remains.",
        "next_repair_target": "Build a one-cell boundary-miss eval residual contrast patch focused on episode_failure_type only, without reopening decoder, denoise, runtime, or promotion.",
        "authority": dict(AUTHORITY_CLOSED),
        "model_execution_authorized_next": False,
        "decoder_ce_training_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
        "promotion_ready": False,
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
        "decision": "Residual-gate probe fixed strict residuals safely but failed final eval exactness; isolate the remaining boundary-miss failure-type cell next.",
        "next_best_step": "Build Stage9529 boundary-miss eval residual contrast manifest from the remaining Stage9528 wrong row, then audit before any further probe.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9528 Episode Observation Diagnosis Residual-Gate Probe Audit",
        "",
        f"Passed: `{audit['passed']}`",
        f"Safety passed: `{audit['safety_passed']}`",
        f"Quality passed: `{audit['quality_passed']}`",
        f"Strict residual fixed: `{audit['strict_residual_fixed']}`",
        f"Final eval exact: `{audit['final_eval_joint_proxy_exact']}`",
        f"Final strict exact: `{audit['final_strict_joint_proxy_exact']}`",
        f"Wrong rows: `{len(wrong_rows)}`",
        f"High-confidence wrong rows: `{len(high_conf_wrong)}`",
        "",
        audit["diagnosis"],
        "",
    ]))
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "safety_passed": audit["safety_passed"], "quality_passed": audit["quality_passed"], "final_eval": audit["final_eval_joint_proxy_exact"], "final_strict": audit["final_strict_joint_proxy_exact"], "wrong_rows": len(wrong_rows), "high_confidence_wrong_rows": len(high_conf_wrong), "failures": failures}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
