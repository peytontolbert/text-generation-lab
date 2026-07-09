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
STAGE = 9507
NAME = "stage9507_episode_obs_diag_overlay_probe_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9506_episode_obs_diag_overlay_preflight_audit.json"
RUN_DIR = ROOT / "runs/local/artifacts/stage9507_episode_obs_diag_overlay_target_100m_probe"
EXECUTION = RUN_DIR / "execution_result.json"
BEST_STATE = RUN_DIR / "best_structured_state_selection.json"
LOGITS = RUN_DIR / "row_field_logits.jsonl"
AUDIT = RUN_DIR / "stage9507_episode_obs_diag_overlay_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_OBS_DIAG_OVERLAY_PROBE_AUDIT_STAGE9507.md"
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
    best = load_json(BEST_STATE)
    logits = load_jsonl(LOGITS)
    failures: list[str] = []
    warnings: list[str] = []
    if source.get("passed") is not True or not source.get("metrics", {}).get("execution_authorized_for_next_stage"):
        failures.append("stage9506_not_authorized")
    impl = result.get("implementation") if isinstance(result.get("implementation"), dict) else {}
    if impl.get("probe_scale") != "target_100m":
        failures.append("not_target_100m_execution")
    if result.get("runtime_executed") or result.get("gemma_executed") or result.get("harness_executed"):
        failures.append("forbidden_external_execution")
    if result.get("final_checkpoint_exported"):
        failures.append("final_checkpoint_exported")
    checkpoint_like = sorted(
        str(path.relative_to(RUN_DIR))
        for path in RUN_DIR.rglob("*")
        if path.is_file() and path.suffix in {".pt", ".pth", ".bin", ".safetensors", ".ckpt"}
    )
    if checkpoint_like:
        failures.append("checkpoint_like_artifacts_written")

    final_eval = result.get("eval", {}).get("eval", {}) if isinstance(result.get("eval"), dict) else {}
    final_strict = result.get("eval", {}).get("strict_eval", {}) if isinstance(result.get("eval"), dict) else {}
    if final_eval.get("joint_proxy_exact") != 1.0:
        failures.append("final_eval_not_exact")
    if final_strict.get("joint_proxy_exact") != 1.0:
        failures.append("final_strict_not_exact")
    if best.get("restored") is not True:
        failures.append("best_state_not_restored")
    if best.get("eval_joint_proxy_exact") != 1.0 or best.get("strict_joint_proxy_exact") != 1.0:
        failures.append("best_state_not_jointly_exact")
    if result.get("eval_rows") == 1 and result.get("strict_rows") == 1:
        warnings.append("minimal_eval_strict_coverage_not_promotion_signal")

    wrong_rows = [row for row in logits if row.get("correct") is False]
    high_conf_wrong = [row for row in wrong_rows if row.get("high_confidence_wrong")]
    audit = {
        "passed": not failures,
        "safety_passed": not any(failure in failures for failure in ["forbidden_external_execution", "final_checkpoint_exported", "checkpoint_like_artifacts_written"]),
        "quality_passed": not failures,
        "failures": failures,
        "warnings": warnings,
        "source_stage": "stage9506_episode_obs_diag_overlay_preflight_audit",
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
        "best_state_selection": best,
        "wrong_rows": wrong_rows,
        "high_confidence_wrong_rows": high_conf_wrong,
        "checkpoint_like_artifacts": checkpoint_like,
        "decision": "Target-100M observation-diagnosis overlay probe passed as a tiny diagnostic with restored jointly exact best state. Promotion remains closed because eval/strict coverage is one row each.",
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
        "decision": audit["decision"],
        "next_best_step": "Widen the observation-diagnosis overlay eval/strict coverage before any broader execution, decoder reconnect, or promotion.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")

    DOC.write_text("\n".join([
        "# Stage9507 Episode Observation Diagnosis Overlay Probe Audit",
        "",
        f"Passed: `{audit['passed']}`",
        f"Final eval exact: `{audit['final_eval_joint_proxy_exact']}`",
        f"Final strict exact: `{audit['final_strict_joint_proxy_exact']}`",
        f"Best state restored: `{best.get('restored')}`",
        f"Selected step: `{best.get('selected_step')}`",
        f"Wrong rows: `{len(wrong_rows)}`",
        f"Warnings: `{warnings}`",
        "",
        audit["decision"],
        "",
    ]))

    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    reg_rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    reg_rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(reg_rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")

    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "final_eval": audit["final_eval_joint_proxy_exact"], "final_strict": audit["final_strict_joint_proxy_exact"], "best_restored": best.get("restored"), "warnings": warnings, "failures": failures}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
