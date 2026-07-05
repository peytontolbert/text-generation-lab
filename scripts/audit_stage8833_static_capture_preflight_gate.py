#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

from capture_preflight_gate_audit import audit_preflight_rows
from model_output_packet_telemetry_contract_builder import AUTHORITY_CLOSED

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8833
NAME = "stage8833_static_capture_preflight_gate_audit"
SOURCE = ROOT / "runs/local/artifacts/stage8831_model_output_capture_preflight_design/model_output_capture_preflight_design_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "STATIC_CAPTURE_PREFLIGHT_GATE_AUDIT_STAGE8833.md"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines() if line.strip()]
    audit = audit_preflight_rows(rows)
    failures = [] if SOURCE.exists() else [f"missing:{SOURCE}"]
    passed = audit["passed"] and not failures
    metrics = {
        **AUTHORITY_CLOSED,
        **{k: v for k, v in audit.items() if k != "passed"},
        "authority_rows": audit["authority_open_rows"],
        "source_failures": failures,
        "ready_for_model_execution": False,
        "ready_for_decoder_ce": False,
    }
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": passed,
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "artifacts": {"source": str(SOURCE.relative_to(ROOT)), "audit_card": str((OUT_DIR / "static_capture_preflight_gate_audit_card.json").relative_to(ROOT))},
        "decision": "Static capture preflight gate passed. This validates closed preflight design only; model execution remains closed." if passed else "Static capture preflight gate failed.",
        "next_best_step": "Reconcile registry/spine, then decide whether to recover an authority-ticket schema for future model-output capture. Do not run a model yet.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "static_capture_preflight_gate_audit_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8833 Static Capture Preflight Gate Audit",
        "",
        f"Passed: `{passed}`",
        "",
        f"Rows: `{metrics['rows']}`",
        f"Static gate pass rows: `{metrics['static_gate_pass_rows']}`",
        f"Authority rows: `{metrics['authority_rows']}`",
        f"Probe-ready rows: `{metrics['probe_ready_rows']}`",
        f"Model execution ready rows: `{metrics['model_execution_ready_rows']}`",
        "",
        "This is still a no-execution gate. It does not authorize model execution, decoder CE, denoise CE, runtime, Gemma, scoring, source/body emission, or promotion.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
