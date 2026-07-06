#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8911
NAME = "stage8911_ticket_builder_contract_enforcement_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TICKET_BUILDER_CONTRACT_ENFORCEMENT_AUDIT_STAGE8911.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "ticket_builder_contract_enforcement_audit.json"

BUILDER_SURFACES = [
    {
        "path": "scripts/build_stage8886_stage8890_inactive_execution_ticket_design.py",
        "role": "historical_inactive_ticket_builder",
        "must_import_contract_now": False,
    },
    {
        "path": "scripts/build_stage8895_stage8890_live_authorization_checklist.py",
        "role": "historical_live_checklist_builder",
        "must_import_contract_now": False,
    },
    {
        "path": "scripts/build_stage8864_native_probe_preflight_gate.py",
        "role": "historical_probe_preflight_builder",
        "must_import_contract_now": False,
    },
    {
        "path": "scripts/diagnostic_ticket_contract.py",
        "role": "canonical_future_ticket_contract",
        "must_import_contract_now": True,
        "is_contract_module": True,
    },
]

FUTURE_BUILDER_REQUIREMENTS = [
    "import_or_call_apply_diagnostic_gate_fields",
    "call_audit_diagnostic_ticket_fields_before_write",
    "fail_closed_on_contract_failures",
    "write_no_live_command_until_explicit_ticket",
    "preserve_closed_authority_until_run_ticket",
    "block_metrics_interpretation_until_stage8902_passes",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def surface_status(surface: dict[str, Any]) -> dict[str, Any]:
    path = ROOT / str(surface["path"])
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    imports_contract = "diagnostic_ticket_contract" in text
    calls_apply = "apply_diagnostic_gate_fields" in text
    calls_audit = "audit_diagnostic_ticket_fields" in text
    if surface.get("is_contract_module"):
        compliant = path.exists() and calls_apply and calls_audit
    elif surface["must_import_contract_now"]:
        compliant = path.exists() and imports_contract and calls_apply and calls_audit
    else:
        compliant = path.exists()
    return {
        "path": surface["path"],
        "role": surface["role"],
        "exists": path.exists(),
        "historical_only": not surface["must_import_contract_now"],
        "imports_contract": imports_contract,
        "calls_apply_diagnostic_gate_fields": calls_apply,
        "calls_audit_diagnostic_ticket_fields": calls_audit,
        "contract_compliant_for_future_use": compliant if surface["must_import_contract_now"] or surface.get("is_contract_module") else False,
        "allowed_future_use": "canonical" if surface.get("is_contract_module") else "historical_reference_only",
    }


def build_audit(registry: dict[str, Any]) -> dict[str, Any]:
    statuses = [surface_status(surface) for surface in BUILDER_SURFACES]
    failures: list[str] = []
    for status in statuses:
        if not status["exists"]:
            failures.append(f"missing_surface:{status['path']}")
        if status["allowed_future_use"] == "canonical" and not status["contract_compliant_for_future_use"]:
            failures.append(f"canonical_contract_not_compliant:{status['path']}")
    legacy_future_usable = [s["path"] for s in statuses if s["allowed_future_use"] != "canonical" and s["contract_compliant_for_future_use"]]
    if legacy_future_usable:
        failures.append(f"legacy_builder_incorrectly_future_usable:{legacy_future_usable}")
    metrics = registry.get("metrics") or {}
    latest = int(metrics.get("latest_stage", -1))
    if latest not in {8908, 8909, 8910, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    authority_counts = metrics.get("authority_counts") or {}
    if any(int(authority_counts.get(key, 0)) != 0 for key in AUTHORITY_CLOSED):
        failures.append("registry_authority_counts_nonzero")
    return {
        "passed": not failures,
        "failures": failures,
        "surface_statuses": statuses,
        "future_builder_requirements": FUTURE_BUILDER_REQUIREMENTS,
        "decision_boundary": {
            "legacy_ticket_builders": "historical_reference_only_do_not_reuse_for_live_ticket_without_stage8907_contract_patch",
            "canonical_future_contract": "scripts/diagnostic_ticket_contract.py",
            "future_live_ticket_builder_status": "not_yet_built",
            "training_or_execution_authorized": False,
        },
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
            "builder_surfaces_checked": len(audit["surface_statuses"]),
            "future_builder_requirements": len(FUTURE_BUILDER_REQUIREMENTS),
            "future_live_ticket_builder_built": False,
            "legacy_builders_future_usable": False,
            "model_execution_authorized_now": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "data_mining_authorized": False,
        },
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT))},
        "decision": "Ticket builder enforcement boundary recorded: legacy builders are historical-only; future live ticket builders must import and pass scripts.diagnostic_ticket_contract." if audit["passed"] else "Ticket builder contract enforcement audit failed.",
        "next_best_step": "Build a new future live-ticket builder skeleton that imports Stage8907 contract and fails closed, but still emits only inactive/template tickets unless explicitly authorized.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8911 Ticket Builder Contract Enforcement Audit",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "This no-execution audit prevents drift from the recovered diagnostic ticket contract.",
        "",
        "Legacy ticket/preflight builders are treated as historical references only. Any future live-ticket builder must import `scripts.diagnostic_ticket_contract`, call `apply_diagnostic_gate_fields`, and reject tickets unless `audit_diagnostic_ticket_fields` passes.",
        "",
        "No execution, training, decoder CE, denoise CE, runtime, mining, source/body emission, scoring, controller merge, or promotion is authorized.",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": card["passed"], "path": str(SUMMARY), "authority": AUTHORITY_CLOSED, "next_best_step": card["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = card["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": card["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8911 Ticket Builder Contract Enforcement Audit"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8911 marks legacy ticket/preflight builders as historical-only and records the future-builder rule: import `scripts.diagnostic_ticket_contract`, apply diagnostic fields, and fail closed before any live probe ticket can be emitted.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
