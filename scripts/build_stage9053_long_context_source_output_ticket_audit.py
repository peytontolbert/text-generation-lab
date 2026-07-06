#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
    from scripts.build_stage9052_long_context_source_output_ticket_design import (
        DENIED_OPERATIONS,
        REQUIRED_CAPS,
        audit_ticket,
    )
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from build_stage9052_long_context_source_output_ticket_design import (  # type: ignore
        DENIED_OPERATIONS,
        REQUIRED_CAPS,
        audit_ticket,
    )

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9053
NAME = "stage9053_long_context_source_output_ticket_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9052 = ROOT / "runs/summaries/stage9052_long_context_source_output_ticket_design.json"
TICKET_9052 = ROOT / "runs/local/artifacts/stage9052_long_context_source_output_ticket_design/long_context_source_output_ticket_template_inactive.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "LONG_CONTEXT_SOURCE_OUTPUT_TICKET_AUDIT_STAGE9053.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_CARD = OUT_DIR / "long_context_source_output_ticket_audit.json"

NEGATIVE_EXPECTATIONS = {
    "opened_allowed_operation": "allowed_operations_now_not_empty",
    "granted_ticket": "ticket_granted_now_not_false",
    "materialized_command": "command_materialized_not_false",
    "missing_arxiv_denial": "missing_denial:scan_arxiv",
    "nonzero_candidate_cap": "cap_mismatch:max_candidates",
    "enabled_hf_upload": "cap_mismatch:hf_upload",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def registry_stub(registry: dict[str, Any]) -> dict[str, Any]:
    return {"metrics": {"latest_stage": int((registry.get("metrics") or {}).get("latest_stage", STAGE)), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def run_negative_checks(ticket: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    results: dict[str, Any] = {}
    cases: dict[str, dict[str, Any]] = {}
    opened = copy.deepcopy(ticket)
    opened["allowed_operations_now"] = ["run_candidate_mining"]
    cases["opened_allowed_operation"] = opened
    granted = copy.deepcopy(ticket)
    granted["ticket_granted_now"] = True
    cases["granted_ticket"] = granted
    command = copy.deepcopy(ticket)
    command["command_materialized"] = True
    cases["materialized_command"] = command
    missing_denial = copy.deepcopy(ticket)
    missing_denial["denied_operations"] = [item for item in missing_denial.get("denied_operations", []) if item != "scan_arxiv"]
    cases["missing_arxiv_denial"] = missing_denial
    nonzero_cap = copy.deepcopy(ticket)
    nonzero_cap["required_caps"]["max_candidates"] = 1
    cases["nonzero_candidate_cap"] = nonzero_cap
    hf = copy.deepcopy(ticket)
    hf["required_caps"]["hf_upload"] = True
    cases["enabled_hf_upload"] = hf
    for name, mutated in cases.items():
        audit = audit_ticket(mutated, registry_stub(registry))
        expected = NEGATIVE_EXPECTATIONS[name]
        results[name] = {"passed": audit["passed"], "expected_failure": expected, "observed": expected in audit["failures"]}
    return results


def build_card() -> dict[str, Any]:
    registry = load_json(REGISTRY) or {"metrics": {}}
    source = load_json(SOURCE_9052)
    ticket = load_json(TICKET_9052)
    base_audit = audit_ticket(ticket, registry_stub(registry))
    negatives = run_negative_checks(ticket, registry)
    checks = {
        "source_stage9052_present": SOURCE_9052.exists(),
        "source_stage9052_passed": source.get("passed") is True,
        "ticket_artifact_present": TICKET_9052.exists(),
        "base_ticket_audit_passed": base_audit["passed"] is True,
        "all_negative_mutations_rejected": all(item["observed"] and item["passed"] is False for item in negatives.values()),
        "denies_all_real_data_ops": set(DENIED_OPERATIONS).issubset(set(ticket.get("denied_operations") or [])),
        "required_caps_zero_or_false": ticket.get("required_caps") == REQUIRED_CAPS,
        "ticket_not_granted_now": ticket.get("ticket_granted_now") is False,
        "command_not_materialized": ticket.get("command_materialized") is False,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    failures = [key for key, value in checks.items() if value is not True]
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "checks": checks,
        "failures": failures,
        "base_audit": base_audit,
        "negative_checks": negatives,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "negative_mutation_checks": len(negatives),
            "denied_operations": len(ticket.get("denied_operations") or []),
            "required_caps": len(ticket.get("required_caps") or {}),
            "ticket_audit_only": True,
            "corpus_scan_authorized_now": False,
            "candidate_mining_authorized_now": False,
            "arxiv_write_authorized": False,
            "hf_upload_authorized_now": False,
            "training_authorized": False,
            "model_execution_attempted": False,
        },
        "decision": "Stage9052 inactive source/output ticket passes independent audit and rejects unsafe mutations; no source read or candidate mining is opened.",
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_card()
    AUDIT_CARD.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": card["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": 0, "failures": card["failures"], **card["metrics"]},
        "artifacts": {"audit": str(AUDIT_CARD.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "Continue no-data pipeline recovery: attach long-context candidate ticket controls to the central compiler graph, or audit candidate quality/routing on synthetic fixtures only.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9053 Long Context Source/Output Ticket Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage independently audits the inactive Stage9052 ticket and rejects unsafe mutations. It opens no source reads, corpus scans, candidate mining, `/arxiv` writes, HF upload, model execution, or training.",
        "",
        f"Negative mutation checks: `{card['metrics']['negative_mutation_checks']}`",
        "",
        f"Next: {summary['next_best_step']}",
        "",
    ]) + "\n", encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))),
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
