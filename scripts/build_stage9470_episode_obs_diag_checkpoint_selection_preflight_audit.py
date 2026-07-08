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
STAGE = 9470
NAME = "stage9470_episode_obs_diag_checkpoint_selection_preflight_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9469_episode_obs_diag_schedule_target_100m_probe_audit.json"
PREFLIGHT_DIR = ROOT / "runs/local/artifacts/stage9470_episode_obs_diag_checkpoint_selection_contract_preflight"
CONTRACT = PREFLIGHT_DIR / "probe_contract_audit.json"
AUDIT = PREFLIGHT_DIR / "stage9470_preflight_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_OBS_DIAG_CHECKPOINT_SELECTION_PREFLIGHT_AUDIT_STAGE9470.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
ENABLED = {"episode_failure_type_ce", "episode_repair_outcome_ce", "episode_step_value_mse"}
DISABLED = {"episode_boundary_match_ce", "episode_target_prefix_match_ce", "decoder_ce", "denoise_ce", "runtime_reward"}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def main() -> None:
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    contract = load_json(CONTRACT)
    failures: list[str] = []
    if source.get("passed") is not False or source.get("metrics", {}).get("safety_passed") is not True:
        failures.append("source_stage9469_expected_safe_quality_failure_not_present")
    if contract.get("passed") is not True:
        failures.append("target_100m_contract_preflight_not_passed")
    if contract.get("probe_scale") != "target_100m":
        failures.append("contract_not_target_100m")
    if contract.get("model_execution_attempted") is not False:
        failures.append("model_execution_attempted_in_preflight")
    weights = contract.get("weights") if isinstance(contract.get("weights"), dict) else {}
    if weights.get("eval_interval") != 8:
        failures.append("eval_interval_not_enabled")
    caps = contract.get("caps") if isinstance(contract.get("caps"), dict) else {}
    if caps.get("max_steps") != 96:
        failures.append("unexpected_max_steps")
    if contract.get("unsafe_loss_rows") != 0 or contract.get("authority_rows") != 0:
        failures.append("unsafe_or_authority_rows_present")
    tokenizer = contract.get("tokenizer_contract") if isinstance(contract.get("tokenizer_contract"), dict) else {}
    if tokenizer.get("byte_fallback_used_when_unset") is not False:
        failures.append("target_100m_tokenizer_not_locked")
    loss_counts = contract.get("loss_counts") if isinstance(contract.get("loss_counts"), dict) else {}
    for key in ENABLED:
        if loss_counts.get(key) != 50:
            failures.append(f"enabled_loss_count_mismatch:{key}")
    for key in DISABLED:
        if loss_counts.get(key, 0) != 0:
            failures.append(f"disabled_loss_open:{key}")
    next_authorized = not failures
    authority = {**dict(AUTHORITY_CLOSED), "model_execution_authorized_next": next_authorized}
    audit = {
        "passed": not failures,
        "failures": failures,
        "source_stage": "stage9469_episode_obs_diag_schedule_target_100m_probe_audit",
        "preflight_contract": str(CONTRACT.relative_to(ROOT)),
        "probe_scale": contract.get("probe_scale"),
        "mode": contract.get("mode"),
        "rows": contract.get("rows"),
        "caps": caps,
        "weights": weights,
        "manifest_sha256": contract.get("manifest_sha256"),
        "loss_counts": loss_counts,
        "tokenizer_contract": tokenizer,
        "checkpoint_selection_contract": {
            "eval_interval": 8,
            "expected_checkpoint_eval_records": 24,
            "selection_rule": "Pass only if any checkpoint or final state has eval_joint_proxy_exact == 1.0 and strict_joint_proxy_exact == 1.0 with no high-confidence wrong rows; no checkpoint is exported.",
        },
        "execution_authorized_for_next_stage": next_authorized,
        "model_execution_authorized_next": next_authorized,
        "decoder_ce_training_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
        "authority": authority,
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": authority,
        "metrics": {**authority, **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "contract": str(CONTRACT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Authorized only a 96-step target-100M observation-diagnosis run with eval-interval telemetry for checkpoint-selection diagnosis.",
        "next_best_step": "Run Stage9471 checkpoint-selection telemetry probe under trellis, then audit whether any interval has both eval and strict exact.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9470 Episode Observation Diagnosis Checkpoint-Selection Preflight Audit",
        "",
        f"Passed: `{audit['passed']}`",
        f"Execution authorized for next stage: `{next_authorized}`",
        f"Eval interval: `{weights.get('eval_interval')}`",
        f"Caps: `{caps}`",
        "",
        audit["checkpoint_selection_contract"]["selection_rule"],
        "",
        "Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, and promotion remain closed.",
        "",
    ]))
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": authority, "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows)}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "execution_authorized_for_next_stage": next_authorized, "failures": failures}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
