#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

from authority_ticket_schema_gate_audit import audit_ticket_rows
from model_output_packet_telemetry_contract_builder import AUTHORITY_CLOSED

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8842
NAME = "stage8842_authority_ticket_schema_gate_audit"
SOURCE = ROOT / "runs/local/artifacts/stage8840_authority_ticket_schema/authority_ticket_schema_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "AUTHORITY_TICKET_SCHEMA_GATE_AUDIT_STAGE8842.md"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines() if line.strip()]
    audit = audit_ticket_rows(rows)
    failures = [] if SOURCE.exists() else [f"missing:{SOURCE}"]
    passed = audit["passed"] and not failures
    metrics = {**AUTHORITY_CLOSED, **{k: v for k, v in audit.items() if k != "passed"}, "authority_rows": audit["authority_open_rows"], "source_failures": failures}
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": passed,
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "artifacts": {"source": str(SOURCE.relative_to(ROOT)), "audit_card": str((OUT_DIR / "authority_ticket_schema_gate_audit_card.json").relative_to(ROOT))},
        "decision": "Authority-ticket schema gate passed; all future execution operations remain denied by default." if passed else "Authority-ticket schema gate failed.",
        "next_best_step": "Reconcile registry/spine, then recover closed ticket-instance dry run. Do not run a model yet.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "authority_ticket_schema_gate_audit_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8842 Authority Ticket Schema Gate Audit",
        "",
        f"Passed: `{passed}`",
        "",
        f"Rows: `{metrics['rows']}`",
        f"Ticket gate pass rows: `{metrics['ticket_gate_pass_rows']}`",
        f"Allowed-operation rows: `{metrics['allowed_operation_rows']}`",
        f"Opening rows: `{metrics['opening_rows']}`",
        "",
        "This audit keeps model execution, decode, CE, runtime, Gemma, scoring, source/body emission, and promotion closed.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
