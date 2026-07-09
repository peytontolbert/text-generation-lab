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
STAGE = 9555
NAME = "stage9555_residual_denoise_one_run_ticket_preflight_design_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9554_residual_denoise_one_run_ticket_preflight_design.json"
TICKET = ROOT / "runs/local/artifacts/stage9554_residual_denoise_one_run_ticket_preflight_design/residual_denoise_one_run_ticket_preflight_design.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "residual_denoise_one_run_ticket_preflight_design_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "RESIDUAL_DENOISE_ONE_RUN_TICKET_PREFLIGHT_DESIGN_AUDIT_STAGE9555.md"
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
    source = load_json(SOURCE_SUMMARY)
    ticket = load_json(TICKET)
    failures: list[str] = []
    if source.get("passed") is not True or ticket.get("passed") is not True:
        failures.append("stage9554_not_passed")
    if ticket.get("execution_command_emitted") is not False:
        failures.append("execution_command_emitted")
    if ticket.get("execution_authorized_now") is not False or ticket.get("execution_authorized_for_next_stage") is not False:
        failures.append("execution_authority_opened")
    if ticket.get("denoise_ce_authorized_now") is not False or ticket.get("decoder_ce_authorized_now") is not False:
        failures.append("ce_authority_opened")
    if any("<future_" in str(part) for part in ticket.get("command_template_not_runnable_until_materialized", [])) is not True:
        failures.append("command_template_missing_placeholders")
    if len(ticket.get("required_future_telemetry") or []) < 12:
        failures.append("telemetry_requirements_missing")
    if "explicit_execution_authorization_review_passed" not in (ticket.get("blocked_until") or []):
        failures.append("explicit_authorization_blocker_missing")
    for key, value in (ticket.get("authority") or {}).items():
        if value is not False:
            failures.append(f"authority_open::{key}")

    passed = not failures
    audit = {
        "passed": passed,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "ticket": str(TICKET.relative_to(ROOT)),
        "execution_command_emitted": ticket.get("execution_command_emitted"),
        "execution_authorized_now": ticket.get("execution_authorized_now"),
        "execution_authorized_for_next_stage": ticket.get("execution_authorized_for_next_stage"),
        "denoise_ce_authorized_now": ticket.get("denoise_ce_authorized_now"),
        "decoder_ce_authorized_now": ticket.get("decoder_ce_authorized_now"),
        "required_future_telemetry_count": len(ticket.get("required_future_telemetry") or []),
        "required_prefight_checks": len(ticket.get("required_prefight_checks") or []),
        "authority": dict(AUTHORITY_CLOSED),
        "model_execution_authorized_next": False,
        "decoder_ce_training_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
        "runtime_authorized": False,
        "promotion_ready": False,
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": passed,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Audited Stage9554: the residual-denoise one-run ticket is contract-only and cannot authorize or run a probe by itself.",
        "next_best_step": "Materialize a combined residual-denoise manifest from Stage9545 and Stage9549, then run contract-only manifest preflight with denoise CE still closed until explicit authorization.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9555 Residual Denoise One-Run Ticket Preflight Design Audit",
        "",
        f"Passed: `{passed}`",
        f"Execution command emitted: `{ticket.get('execution_command_emitted')}`",
        f"Execution authorized for next stage: `{ticket.get('execution_authorized_for_next_stage')}`",
        f"Denoise CE authorized now: `{ticket.get('denoise_ce_authorized_now')}`",
        "",
        "The ticket is a non-runnable contract shell. A future manifest preflight and explicit execution authorization remain required.",
        "",
    ]))
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": passed, "failures": failures, "execution_authorized_for_next_stage": False}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
