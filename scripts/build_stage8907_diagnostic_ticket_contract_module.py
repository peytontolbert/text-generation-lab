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
STAGE = 8907
NAME = "stage8907_diagnostic_ticket_contract_module"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "DIAGNOSTIC_TICKET_CONTRACT_MODULE_STAGE8907.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "diagnostic_ticket_contract_module_audit.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_sample_future_ticket() -> dict[str, Any]:
    base = {
        "ticket_status": "TEMPLATE_ONLY_INACTIVE",
        "execution_authorized_now": False,
        "allowed_operations_now": [],
        "authority": AUTHORITY_CLOSED,
    }
    return apply_diagnostic_gate_fields(base)


def build_audit(registry: dict[str, Any]) -> dict[str, Any]:
    ticket = build_sample_future_ticket()
    clean_failures = audit_diagnostic_ticket_fields(ticket)
    negative_ticket = dict(ticket)
    negative_ticket.pop("post_run_diagnostic_gate_required")
    negative_failures = audit_diagnostic_ticket_fields(negative_ticket)
    failures: list[str] = []
    if clean_failures:
        failures.append(f"valid_template_failed:{clean_failures}")
    if "missing:post_run_diagnostic_gate_required" not in negative_failures:
        failures.append("negative_missing_gate_requirement_not_detected")
    metrics = registry.get("metrics") or {}
    latest = int(metrics.get("latest_stage", -1))
    if latest not in {8906, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    authority_counts = metrics.get("authority_counts") or {}
    if any(int(authority_counts.get(key, 0)) != 0 for key in AUTHORITY_CLOSED):
        failures.append("registry_authority_counts_nonzero")
    return {
        "passed": not failures,
        "failures": failures,
        "valid_template_failures": clean_failures,
        "negative_template_failures": negative_failures,
        "sample_future_ticket": ticket,
        "registry_latest_stage_observed": latest,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    audit = build_audit(registry)
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
            "valid_template_failures": len(audit["valid_template_failures"]),
            "negative_template_failures": len(audit["negative_template_failures"]),
            "model_execution_authorized_now": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "data_mining_authorized": False,
        },
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "contract_module": "scripts/diagnostic_ticket_contract.py"},
        "decision": "Reusable diagnostic ticket contract module is available for future ticket/probe builders; valid template passes and missing-gate negative is rejected." if audit["passed"] else "Diagnostic ticket contract module audit failed.",
        "next_best_step": "Use scripts.diagnostic_ticket_contract.apply_diagnostic_gate_fields in any future live probe ticket builder; reject builders that omit audit_diagnostic_ticket_fields.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8907 Diagnostic Ticket Contract Module",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "This stage adds `scripts/diagnostic_ticket_contract.py`, a reusable no-execution contract for future live probe ticket builders.",
        "",
        "Future builders should call `apply_diagnostic_gate_fields(ticket)` and then reject the result unless `audit_diagnostic_ticket_fields(ticket)` returns no failures.",
        "",
        "This opens no model execution, training, decoder CE, denoise CE, runtime, mining, source/body emission, Gemma, harness, scoring, controller merge, or promotion.",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": card["passed"], "path": str(SUMMARY), "authority": AUTHORITY_CLOSED, "next_best_step": card["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = card["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": card["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8907 Diagnostic Ticket Contract Module"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8907 turns the diagnostic gate into a reusable builder contract: future probe tickets should import `scripts.diagnostic_ticket_contract`, apply the gate fields, and reject tickets that fail `audit_diagnostic_ticket_fields`.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
