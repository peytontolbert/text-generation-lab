#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

from authority_ticket_schema_builder import build_authority_ticket_schema_rows, build_card
from model_output_packet_telemetry_contract_builder import AUTHORITY_CLOSED

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8840
NAME = "stage8840_authority_ticket_schema"
SOURCE = ROOT / "runs/local/artifacts/stage8837_model_output_capture_runner_static_design/model_output_capture_runner_static_design_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "AUTHORITY_TICKET_SCHEMA_STAGE8840.md"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    runner_rows = [json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = build_authority_ticket_schema_rows(runner_rows)
    manifest = OUT_DIR / "authority_ticket_schema_manifest.jsonl"
    manifest.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    metrics = {**AUTHORITY_CLOSED, **build_card(rows), "source_rows": len(runner_rows), "source_failures": [] if SOURCE.exists() else [f"missing:{SOURCE}"]}
    passed = (
        metrics["source_failures"] == []
        and metrics["passed"] is True
        and metrics["authority_open_rows"] == 0
        and metrics["loss_open_rows"] == 0
        and metrics["opening_rows"] == 0
        and metrics["allowed_operation_rows"] == 0
    )
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": passed,
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "artifacts": {"manifest": str(manifest.relative_to(ROOT)), "source": str(SOURCE.relative_to(ROOT))},
        "decision": "Recovered authority-ticket schema with all gated operations denied by default." if passed else "Authority-ticket schema failed.",
        "next_best_step": "Attach authority-ticket schema to graph, then audit ticket schema gates. Do not run a model yet.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "authority_ticket_schema_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8840 Authority Ticket Schema",
        "",
        f"Passed: `{passed}`",
        "",
        f"Rows: `{metrics['rows']}`",
        f"Authority ticket schema ready rows: `{metrics['authority_ticket_schema_ready_rows']}`",
        f"Allowed-operation rows: `{metrics['allowed_operation_rows']}`",
        f"Opening rows: `{metrics['opening_rows']}`",
        "",
        "The schema defines explicit authority fields and denies checkpoint load, forward, decode, artifact write, CE, runtime, Gemma, scoring, source/body emission, and promotion by default.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
