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
STAGE = 9468
NAME = "stage9468_episode_obs_diag_schedule_target_100m_preflight_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9467_episode_obs_diag_schedule_coverage_design.json"
PREFLIGHT_DIR = ROOT / "runs/local/artifacts/stage9468_episode_obs_diag_schedule_target_100m_contract_preflight"
CONTRACT = PREFLIGHT_DIR / "probe_contract_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_OBS_DIAG_SCHEDULE_TARGET_100M_PREFLIGHT_AUDIT_STAGE9468.md"
AUDIT = PREFLIGHT_DIR / "stage9468_preflight_audit.json"
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
    if source.get("passed") is not True:
        failures.append("source_stage9467_not_passed")
    if contract.get("passed") is not True:
        failures.append("target_100m_contract_preflight_not_passed")
    if contract.get("probe_scale") != "target_100m":
        failures.append("contract_not_target_100m")
    if contract.get("rows") != 50:
        failures.append("unexpected_row_count")
    if contract.get("caps", {}).get("max_steps") != 96:
        failures.append("unexpected_max_steps")
    if contract.get("model_execution_attempted") is not False:
        failures.append("model_execution_attempted_in_preflight")
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
    audit = {
        "passed": not failures,
        "failures": failures,
        "source_stage": "stage9467_episode_obs_diag_schedule_coverage_design",
        "preflight_contract": str(CONTRACT.relative_to(ROOT)),
        "probe_scale": contract.get("probe_scale"),
        "mode": contract.get("mode"),
        "rows": contract.get("rows"),
        "caps": contract.get("caps"),
        "manifest_sha256": contract.get("manifest_sha256"),
        "loss_counts": loss_counts,
        "tokenizer_contract": tokenizer,
        "execution_authorized_for_next_stage": next_authorized,
        "model_execution_authorized_next": next_authorized,
        "decoder_ce_training_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
        "authority": {**dict(AUTHORITY_CLOSED), "model_execution_authorized_next": next_authorized},
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    authority = {**dict(AUTHORITY_CLOSED), "model_execution_authorized_next": next_authorized}
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": authority,
        "metrics": {**authority, **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "contract": str(CONTRACT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Authorized only the next 96-step target-100M full observation-diagnosis schedule-coverage probe if this preflight passes.",
        "next_best_step": "Run Stage9469 96-step full-manifest observation-diagnosis probe under trellis, then audit strict exactness and loss.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9468 Episode Observation Diagnosis Schedule Target-100M Preflight Audit",
        "",
        f"Passed: `{audit['passed']}`",
        f"Execution authorized for next stage: `{next_authorized}`",
        f"Rows: `{audit['rows']}`",
        f"Caps: `{audit['caps']}`",
        "",
        "Only Stage9469 schedule-coverage structured execution is authorized. Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, controller merge, checkpoint export, and promotion remain closed.",
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
