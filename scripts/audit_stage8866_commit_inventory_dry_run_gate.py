#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

from commit_inventory_dry_run_gate_audit import audit_inventory_design_rows
from model_output_packet_telemetry_contract_builder import AUTHORITY_CLOSED

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8866
NAME = "stage8866_commit_inventory_dry_run_gate_audit"
SOURCE = ROOT / "runs/local/artifacts/stage8865_commit_inventory_dry_run_design/commit_inventory_dry_run_design_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "COMMIT_INVENTORY_DRY_RUN_GATE_AUDIT_STAGE8866.md"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    failures = [] if SOURCE.exists() else [f"missing:{SOURCE}"]
    rows = [json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines() if line.strip()] if SOURCE.exists() else []
    audit = audit_inventory_design_rows(rows)
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
            "audit_card": str((OUT_DIR / "commit_inventory_dry_run_gate_audit_card.json").relative_to(ROOT)),
        },
        "decision": "Commit inventory dry-run gate passed. The design remains zero-walk, zero-commit-read, zero-training-row, and decoder-closed." if passed else "Commit inventory dry-run gate failed.",
        "next_best_step": "Reconcile registry/spine, then attach dry-run inventory design to graph or recover stale graph status reconciliation. Keep repository walking, training, and decoder CE closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "commit_inventory_dry_run_gate_audit_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8866 Commit Inventory Dry-Run Gate Audit",
        "",
        f"Passed: `{passed}`",
        "",
        f"Rows: `{metrics['rows']}`",
        f"Gate pass rows: `{metrics['gate_pass_rows']}`",
        f"Missing design IDs: `{metrics['missing_design_id_count']}`",
        f"Authority rows: `{metrics['authority_rows']}`",
        f"/arxiv repository walk authorized: `{metrics['arxiv_repository_walk_authorized']}`",
        f"Commit reads authorized: `{metrics['commit_reads_authorized']}`",
        f"Training authorized: `{metrics['training_authorized']}`",
        f"Decoder CE authorized: `{metrics['decoder_ce_authorized']}`",
        "",
        "This is a dry-run gate only. It does not authorize repository traversal, commit reads, mining, training, decoder CE, runtime, source/body emission, Gemma, scoring, or promotion.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
