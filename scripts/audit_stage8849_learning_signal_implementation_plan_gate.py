#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

from learning_signal_implementation_plan_gate_audit import audit_plan_rows
from model_output_packet_telemetry_contract_builder import AUTHORITY_CLOSED

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8849
NAME = "stage8849_learning_signal_implementation_plan_gate_audit"
SOURCE = ROOT / "runs/local/artifacts/stage8847_learning_signal_implementation_plan/learning_signal_implementation_plan_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "LEARNING_SIGNAL_IMPLEMENTATION_PLAN_GATE_AUDIT_STAGE8849.md"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines() if line.strip()]
    audit = audit_plan_rows(rows)
    failures = [] if SOURCE.exists() else [f"missing:{SOURCE}"]
    passed = audit["passed"] and not failures
    metrics = {**AUTHORITY_CLOSED, **{k: v for k, v in audit.items() if k != "passed"}, "authority_rows": audit["authority_open_rows"], "source_failures": failures}
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": passed,
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "artifacts": {"source": str(SOURCE.relative_to(ROOT)), "audit_card": str((OUT_DIR / "learning_signal_implementation_plan_gate_audit_card.json").relative_to(ROOT))},
        "decision": "Learning-signal implementation plan gate passed. This validates plan completeness only; training remains closed." if passed else "Learning-signal implementation plan gate failed.",
        "next_best_step": "Reconcile registry/spine, then recover code-patch readiness checklist. Keep training and decoder CE closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "learning_signal_implementation_plan_gate_audit_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8849 Learning Signal Implementation Plan Gate Audit",
        "",
        f"Passed: `{passed}`",
        "",
        f"Rows: `{metrics['rows']}`",
        f"Plan gate pass rows: `{metrics['plan_gate_pass_rows']}`",
        f"Missing plan IDs: `{metrics['missing_plan_id_count']}`",
        f"Missing files: `{metrics['missing_file_count']}`",
        f"Authority rows: `{metrics['authority_rows']}`",
        "",
        "This is a plan gate only. It does not authorize code patches, training, decoder CE, runtime, Gemma, scoring, source/body emission, or promotion.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
