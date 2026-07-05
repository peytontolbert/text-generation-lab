#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

from commit_learning_signal_no_mining_gate_audit import audit_commit_contract_rows
from model_output_packet_telemetry_contract_builder import AUTHORITY_CLOSED

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8860
NAME = "stage8860_commit_learning_signal_no_mining_gate_audit"
SOURCE = ROOT / "runs/local/artifacts/stage8855_commit_learning_signal_contract/commit_learning_signal_contract_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "COMMIT_LEARNING_SIGNAL_NO_MINING_GATE_AUDIT_STAGE8860.md"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    failures = [] if SOURCE.exists() else [f"missing:{SOURCE}"]
    rows = [json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines() if line.strip()] if SOURCE.exists() else []
    audit = audit_commit_contract_rows(rows)
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
            "audit_card": str((OUT_DIR / "commit_learning_signal_no_mining_gate_audit_card.json").relative_to(ROOT)),
        },
        "decision": "Commit-learning-signal no-mining gate passed. This validates only the closed contract; /arxiv repo walking, training, and decoder CE remain closed." if passed else "Commit-learning-signal no-mining gate failed.",
        "next_best_step": "Reconcile registry/spine, then recover a dry-run commit inventory design without walking /arxiv repositories. Keep training and decoder CE closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "commit_learning_signal_no_mining_gate_audit_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8860 Commit Learning Signal No-Mining Gate Audit",
        "",
        f"Passed: `{passed}`",
        "",
        f"Rows: `{metrics['rows']}`",
        f"Gate pass rows: `{metrics['gate_pass_rows']}`",
        f"Missing contract IDs: `{metrics['missing_contract_id_count']}`",
        f"Authority rows: `{metrics['authority_rows']}`",
        f"Commit mining authorized: `{metrics['commit_mining_authorized']}`",
        f"Training authorized: `{metrics['training_authorized']}`",
        f"Decoder CE authorized: `{metrics['decoder_ce_authorized']}`",
        "",
        "This is a no-mining gate only. It does not authorize repository traversal, training, decoder CE, runtime, source/body emission, Gemma, scoring, or promotion.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
