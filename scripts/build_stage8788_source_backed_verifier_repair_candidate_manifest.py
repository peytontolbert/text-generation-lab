#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from source_backed_verifier_repair_builder import AUTHORITY_CLOSED, build_card, build_source_backed_rows, read_jsonl, write_jsonl

STAGE = 8788
NAME = "stage8788_source_backed_verifier_repair_candidate_manifest"
NEUTRAL = ROOT / "runs/local/artifacts/stage8643_verifier_repair_neutral_manifest/verifier_repair_neutral_manifest.jsonl"
LINEAGE = ROOT / "configs/software_maintainer/source_inventory_lineage_registry_stage8663.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "source_backed_verifier_repair_candidate_manifest.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SOURCE_BACKED_VERIFIER_REPAIR_CANDIDATE_MANIFEST_STAGE8788.md"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    test = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/test_source_backed_verifier_repair_builder.py"], cwd=ROOT, text=True, capture_output=True, check=False)
    rows = build_source_backed_rows(read_jsonl(NEUTRAL), LINEAGE)
    write_jsonl(MANIFEST, rows)
    card = build_card(rows)
    card_path = OUT_DIR / "candidate_manifest_card.json"
    card_path.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    failures: list[str] = []
    if test.returncode != 0:
        failures.append("unit_tests_failed")
    if card["rows"] != 648:
        failures.append("row_count_not_648")
    if len(set(card["actions"].values())) != 1:
        failures.append("actions_not_balanced")
    if card["gate_status"]["complete_gate_status_rows"] != card["rows"]:
        failures.append("incomplete_gate_status_rows")
    if card["authority_rows"]:
        failures.append("authority_rows_present")
    if card["training_loss_rows"]:
        failures.append("training_loss_rows_present")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {**AUTHORITY_CLOSED, "authority_rows": 0, "rows": card["rows"], "actions": card["actions"], "splits": card["splits"], "languages": card["languages"], "gate_status_complete_rows": card["gate_status"]["complete_gate_status_rows"], "training_loss_rows": card["training_loss_rows"], "failures": failures},
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "card": str(card_path.relative_to(ROOT)), "builder": "scripts/source_backed_verifier_repair_builder.py"},
        "decision": "Source-backed verifier-repair candidate manifest built as no-training candidate rows under gate_status_contract." if not failures else "Source-backed verifier-repair candidate manifest failed.",
        "next_best_step": "Run source-backed verifier-repair candidate audit before compiler-ready materialization.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage8788 Source-Backed Verifier Repair Candidate Manifest", "", f"Passed: `{summary['passed']}`", "", f"Rows: `{card['rows']}`", "", "Rows are candidate-only, source-backed, gate-status complete, and no-authority. No verifier/runtime execution or training is authorized.", ""]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
