#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

from curriculum_compiler import AUTHORITY_CLOSED, REQUIRED_RECOVERED_GATE_REFERENCES
from gate_status_contract import default_gate_status, gate_status_card, passed_gate_status

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8762
NAME = "stage8762_gate_status_contract_readiness"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "GATE_STATUS_CONTRACT_READINESS_STAGE8762.md"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = [
        {"row_id": "all_pass", "gate_status": passed_gate_status()},
        {"row_id": "all_pending", "gate_status": default_gate_status()},
        {"row_id": "schema_failed", "gate_status": passed_gate_status(schema_drift_detector=False)},
        {"row_id": "missing"},
    ]
    card = gate_status_card(rows)
    failures: list[str] = []
    if set(card["required_recovered_gate_references"]) != set(REQUIRED_RECOVERED_GATE_REFERENCES):
        failures.append("required gate references drifted")
    if card["complete_gate_status_rows"] != 3:
        failures.append("complete gate row count mismatch")
    if card["failed_gate_counts"].get("schema_drift_detector") != 3:
        failures.append("schema failed/missing count mismatch")
    sample_path = OUT_DIR / "gate_status_contract_sample_rows.jsonl"
    sample_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    card_path = OUT_DIR / "gate_status_contract_card.json"
    card_path.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "required_gate_count": len(REQUIRED_RECOVERED_GATE_REFERENCES),
            "sample_rows": len(rows),
            "complete_gate_status_rows": card["complete_gate_status_rows"],
            "incomplete_gate_status_rows": card["incomplete_gate_status_rows"],
            "failures": failures,
        },
        "artifacts": {
            "sample_rows": str(sample_path.relative_to(ROOT)),
            "gate_status_card": str(card_path.relative_to(ROOT)),
            "module": "scripts/gate_status_contract.py",
            "tests": "tests/test_gate_status_contract.py",
        },
        "decision": "Recovered a shared complete gate_status contract for builders and compiler preflights." if not failures else "Gate status contract readiness failed.",
        "next_best_step": "Run no-training scale-readiness preflight through curriculum compiler with --require-recovered-gates.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8762 Gate Status Contract Readiness",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Recovered one shared complete `gate_status` card contract for source-backed builders and compiler preflights.",
        "",
        "The contract imports the compiler required gate list so builders cannot drift from compiler enforcement.",
        "",
        "Authority remains closed.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
