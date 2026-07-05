#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

from learning_signal_code_patch_readiness_gate_audit import audit_readiness_rows
from model_output_packet_telemetry_contract_builder import AUTHORITY_CLOSED

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8853
NAME = "stage8853_learning_signal_code_patch_readiness_gate_audit"
SOURCE = ROOT / "runs/local/artifacts/stage8851_learning_signal_code_patch_readiness/learning_signal_code_patch_readiness_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "LEARNING_SIGNAL_CODE_PATCH_READINESS_GATE_AUDIT_STAGE8853.md"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    failures = [] if SOURCE.exists() else [f"missing:{SOURCE}"]
    rows = [json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines() if line.strip()] if SOURCE.exists() else []
    audit = audit_readiness_rows(rows)
    passed = audit["passed"] and not failures
    metrics = {
        **AUTHORITY_CLOSED,
        **{k: v for k, v in audit.items() if k != "passed"},
        "authority_rows": len(audit["authority_open_rows"]),
        "source_failures": failures,
    }
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": passed,
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "artifacts": {
            "source": str(SOURCE.relative_to(ROOT)),
            "audit_card": str((OUT_DIR / "learning_signal_code_patch_readiness_gate_audit_card.json").relative_to(ROOT)),
        },
        "decision": "Learning-signal code-patch readiness gate passed. This validates patch preconditions only; code changes, training, and decoder CE remain closed." if passed else "Learning-signal code-patch readiness gate failed.",
        "next_best_step": "Reconcile registry/spine, then recover tests-only patch plan for learning-signal implementation. Keep training and decoder CE closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "learning_signal_code_patch_readiness_gate_audit_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8853 Learning Signal Code Patch Readiness Gate Audit",
        "",
        f"Passed: `{passed}`",
        "",
        f"Rows: `{metrics['rows']}`",
        f"Readiness gate pass rows: `{metrics['readiness_gate_pass_rows']}`",
        f"Missing plan IDs: `{metrics['missing_plan_id_count']}`",
        f"Missing files: `{metrics['missing_file_count']}`",
        f"Authority rows: `{metrics['authority_rows']}`",
        f"Code patch authorized: `{metrics['code_patch_authorized']}`",
        f"Training authorized: `{metrics['training_authorized']}`",
        f"Decoder CE authorized: `{metrics['decoder_ce_authorized']}`",
        "",
        "This is a readiness gate only. It does not authorize code patches, training, decoder CE, runtime, Gemma, scoring, source/body emission, or promotion.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
