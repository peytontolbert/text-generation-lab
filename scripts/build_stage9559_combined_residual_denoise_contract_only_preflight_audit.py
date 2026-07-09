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
STAGE = 9559
NAME = "stage9559_combined_residual_denoise_contract_only_preflight_audit"
SOURCE = ROOT / "runs/summaries/stage9558_combined_residual_denoise_contract_only_preflight.json"
PREFLIGHT = ROOT / "runs/local/artifacts/stage9558_combined_residual_denoise_contract_only_preflight/combined_residual_denoise_contract_only_preflight.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "combined_residual_denoise_contract_only_preflight_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "COMBINED_RESIDUAL_DENOISE_CONTRACT_ONLY_PREFLIGHT_AUDIT_STAGE9559.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def update_registry(summary: dict) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE)
    preflight = load_json(PREFLIGHT)
    failures: list[str] = []
    if source.get("passed") is not True or preflight.get("passed") is not True:
        failures.append("stage9558_not_passed")
    if preflight.get("denoise_ce_rows_current") != 0 or preflight.get("decoder_ce_rows_current") != 0 or preflight.get("runtime_reward_rows_current") != 0:
        failures.append("current_loss_rows_open")
    if preflight.get("execution_authorized_for_next_stage") is not False or preflight.get("execution_command_emitted") is not False or preflight.get("model_execution_attempted") is not False:
        failures.append("execution_opened_or_attempted")
    if preflight.get("rows") != 44 or preflight.get("candidate_rows") != 41 or preflight.get("rare_holdout_rows") != 3:
        failures.append("row_partition_mismatch")
    if len(preflight.get("required_future_telemetry") or []) < 12:
        failures.append("future_telemetry_missing")
    passed = not failures
    audit = {"passed": passed, "failures": failures, "source_summary": str(SOURCE.relative_to(ROOT)), "preflight": str(PREFLIGHT.relative_to(ROOT)), "rows": preflight.get("rows"), "candidate_rows": preflight.get("candidate_rows"), "rare_holdout_rows": preflight.get("rare_holdout_rows"), "denoise_ce_rows_current": preflight.get("denoise_ce_rows_current"), "decoder_ce_rows_current": preflight.get("decoder_ce_rows_current"), "runtime_reward_rows_current": preflight.get("runtime_reward_rows_current"), "execution_authorized_for_next_stage": preflight.get("execution_authorized_for_next_stage"), "execution_command_emitted": preflight.get("execution_command_emitted"), "manifest_sha256": preflight.get("manifest_sha256"), "authority": dict(AUTHORITY_CLOSED), "model_execution_authorized_next": False, "decoder_ce_training_authorized_next": False, "denoise_ce_training_authorized_next": False, "runtime_authorized": False, "promotion_ready": False}
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    summary = {"stage": STAGE, "stage_name": NAME, "name": NAME, "passed": passed, "authority": dict(AUTHORITY_CLOSED), "metrics": {**dict(AUTHORITY_CLOSED), **audit}, "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))}, "decision": "Audited Stage9558 contract-only preflight: manifest is hash-locked, current CE losses are closed, and no execution is authorized.", "next_best_step": "If pursuing a tiny residual-denoise probe, build an explicit denoise-CE loss-mask reopen design and execution-authorization review; otherwise continue expanding repair data.", "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join(["# Stage9559 Combined Residual Denoise Contract-Only Preflight Audit", "", f"Passed: `{passed}`", f"Rows: `{preflight.get('rows')}`", f"Current denoise CE rows: `{preflight.get('denoise_ce_rows_current')}`", f"Execution authorized for next stage: `{preflight.get('execution_authorized_for_next_stage')}`", "", "No execution or CE reopen is authorized by this audit.", ""]))
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": passed, "rows": preflight.get("rows"), "denoise_ce_rows_current": preflight.get("denoise_ce_rows_current"), "failures": failures}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
