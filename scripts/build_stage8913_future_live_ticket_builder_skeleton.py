#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import (
        AUTHORITY_CLOSED,
        apply_diagnostic_gate_fields,
        audit_diagnostic_ticket_fields,
    )
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import (  # type: ignore
        AUTHORITY_CLOSED,
        apply_diagnostic_gate_fields,
        audit_diagnostic_ticket_fields,
    )

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8913
NAME = "stage8913_future_live_ticket_builder_skeleton"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "FUTURE_LIVE_TICKET_BUILDER_SKELETON_STAGE8913.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
TICKET = OUT_DIR / "future_stage8890_live_ticket_template_inactive.json"
AUDIT = OUT_DIR / "future_live_ticket_builder_skeleton_audit.json"

REQUIRED_LIMITS = {
    "mode": "structured_policy_probe",
    "max_train_rows": 32,
    "max_eval_rows": 16,
    "max_strict_rows": 16,
    "max_steps": 8,
    "batch_size": 2,
    "max_encoder_tokens": 256,
    "max_decoder_tokens": 64,
    "structured_aux_weight": 1.0,
    "decoder_ce_weight": 0.0,
    "denoise_weight": 0.0,
    "runtime": False,
}

DENIED_OPERATIONS = [
    "load_checkpoint",
    "run_forward",
    "decode_tokens",
    "write_model_output_artifact",
    "compute_decoder_ce",
    "compute_denoise_ce",
    "run_runtime",
    "call_gemma",
    "score_output",
    "emit_source_body",
    "export_checkpoint",
    "promote_model",
    "walk_arxiv",
    "mine_repositories",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_inactive_future_ticket() -> dict[str, Any]:
    ticket = {
        "ticket_id": "future_stage8890_structured_probe_template__inactive_stage8913",
        "ticket_status": "TEMPLATE_ONLY_INACTIVE",
        "requested_stage": 8890,
        "requested_stage_name": "stage8890_tiny_structured_policy_probe_candidate",
        "requires_explicit_user_authorization": True,
        "requires_fresh_pre_execution_audit": True,
        "command_materialized": False,
        "execution_authorized_now": False,
        "allowed_operations_now": [],
        "denied_operations": list(DENIED_OPERATIONS),
        "required_limits": dict(REQUIRED_LIMITS),
        "authority": AUTHORITY_CLOSED,
    }
    return apply_diagnostic_gate_fields(ticket)


def audit_ticket(ticket: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    failures = audit_diagnostic_ticket_fields(ticket)
    if ticket.get("ticket_status") != "TEMPLATE_ONLY_INACTIVE":
        failures.append("ticket_not_template_only_inactive")
    if ticket.get("execution_authorized_now") is not False:
        failures.append("execution_authorized_now_not_false")
    if ticket.get("allowed_operations_now") != []:
        failures.append("allowed_operations_now_not_empty")
    if ticket.get("command_materialized") is not False:
        failures.append("command_materialized_not_false")
    limits = ticket.get("required_limits") or {}
    for key, value in REQUIRED_LIMITS.items():
        if limits.get(key) != value:
            failures.append(f"limit_mismatch:{key}")
    if "run_forward" not in set(ticket.get("denied_operations") or []):
        failures.append("run_forward_not_denied")
    metrics = registry.get("metrics") or {}
    latest = int(metrics.get("latest_stage", -1))
    if latest not in {8911, 8912, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    authority_counts = metrics.get("authority_counts") or {}
    if any(int(authority_counts.get(key, 0)) != 0 for key in AUTHORITY_CLOSED):
        failures.append("registry_authority_counts_nonzero")
    return {
        "passed": not failures,
        "failures": failures,
        "ticket_contract_failures": audit_diagnostic_ticket_fields(ticket),
        "denied_operations": len(ticket.get("denied_operations") or []),
        "limits_checked": len(REQUIRED_LIMITS),
        "registry_latest_stage_observed": latest,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    ticket = build_inactive_future_ticket()
    audit = audit_ticket(ticket, registry)
    TICKET.write_text(json.dumps(ticket, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": audit["passed"],
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "failures": audit["failures"],
            "ticket_contract_failures": len(audit["ticket_contract_failures"]),
            "denied_operations": audit["denied_operations"],
            "limits_checked": audit["limits_checked"],
            "command_materialized": False,
            "execution_authorized_now": False,
            "model_execution_authorized_now": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "data_mining_authorized": False,
        },
        "artifacts": {"ticket": str(TICKET.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT))},
        "decision": "Future live-ticket builder skeleton emits only an inactive/template ticket and passes the Stage8907 diagnostic contract. No execution is opened." if audit["passed"] else "Future live-ticket builder skeleton failed.",
        "next_best_step": "If the user later explicitly authorizes a one-run probe, derive the live ticket from this skeleton, preserve diagnostics, and run the pre-execution audit first. Otherwise continue no-execution recovery.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8913 Future Live Ticket Builder Skeleton",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "This stage creates a reusable inactive/template future ticket skeleton that imports the Stage8907 diagnostic ticket contract.",
        "",
        "It materializes no command and opens no model execution, training, decoder CE, denoise CE, runtime, mining, source/body emission, scoring, controller merge, or promotion.",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": card["passed"], "path": str(SUMMARY), "authority": AUTHORITY_CLOSED, "next_best_step": card["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = card["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": card["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8913 Future Live Ticket Builder Skeleton"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8913 adds a reusable inactive/template future live-ticket builder skeleton that imports Stage8907 diagnostics, denies execution operations, and keeps all authority closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
