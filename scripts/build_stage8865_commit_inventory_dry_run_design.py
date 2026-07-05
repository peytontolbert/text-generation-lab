#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

from commit_inventory_dry_run_design_builder import build_card, build_inventory_design_rows
from model_output_packet_telemetry_contract_builder import AUTHORITY_CLOSED

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8865
NAME = "stage8865_commit_inventory_dry_run_design"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "COMMIT_INVENTORY_DRY_RUN_DESIGN_STAGE8865.md"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = build_inventory_design_rows()
    card_metrics = build_card(rows)
    manifest = OUT_DIR / "commit_inventory_dry_run_design_manifest.jsonl"
    card_path = OUT_DIR / "commit_inventory_dry_run_design_card.json"
    manifest.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    metrics = {**AUTHORITY_CLOSED, **card_metrics, "authority_rows": card_metrics["authority_open_rows"]}
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": card_metrics["passed"],
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "artifacts": {
            "manifest": str(manifest.relative_to(ROOT)),
            "card": str(card_path.relative_to(ROOT)),
        },
        "decision": "Recovered dry-run commit inventory design. It defines future inventory schema/caps but does not walk /arxiv repositories, read commits, mine rows, train, or open decoder CE.",
        "next_best_step": "Audit dry-run commit inventory design gates. Keep repository walking, training, and decoder CE closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    card_path.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8865 Commit Inventory Dry-Run Design",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "This stage defines a future commit inventory schema and caps only. It does not inspect `/arxiv/repositories`.",
        "",
        f"Rows: `{metrics['rows']}`",
        f"Ready rows: `{metrics['dry_run_design_ready_rows']}`",
        f"/arxiv repository walk authorized: `{metrics['arxiv_repository_walk_authorized']}`",
        f"Commit reads authorized: `{metrics['commit_reads_authorized']}`",
        f"Training authorized: `{metrics['training_authorized']}`",
        f"Decoder CE authorized: `{metrics['decoder_ce_authorized']}`",
        "",
        "Zero caps in this stage:",
        "",
        "- repositories walked: `0`",
        "- commits read per repo: `0`",
        "- diff bodies read: `0`",
        "- patch bodies emitted: `0`",
        "- training rows emitted: `0`",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
