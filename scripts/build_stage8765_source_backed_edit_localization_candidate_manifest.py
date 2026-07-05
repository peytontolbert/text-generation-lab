#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

from source_backed_edit_localization_builder import AUTHORITY_CLOSED, build_card, build_source_backed_rows, read_jsonl, write_jsonl

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8765
NAME = "stage8765_source_backed_edit_localization_candidate_manifest"
NEUTRAL = ROOT / "runs/local/artifacts/stage8636_edit_localization_neutral_manifest/edit_localization_neutral_manifest.jsonl"
LINEAGE = ROOT / "configs/software_maintainer/source_inventory_lineage_registry_stage8663.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
OUT = OUT_DIR / "source_backed_edit_localization_candidate_manifest.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SOURCE_BACKED_EDIT_LOCALIZATION_CANDIDATE_MANIFEST_STAGE8765.md"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = build_source_backed_rows(read_jsonl(NEUTRAL), LINEAGE)
    write_jsonl(OUT, rows)
    manifest_card = build_card(rows)
    (OUT_DIR / "candidate_manifest_card.json").write_text(json.dumps(manifest_card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    failures: list[str] = []
    target_counts = set(manifest_card["targets"].values())
    if not rows:
        failures.append("no rows built")
    if len(target_counts) != 1:
        failures.append("target counts are not balanced")
    if manifest_card["authority_rows"] != 0:
        failures.append("authority rows present")
    if manifest_card["training_loss_rows"] != 0:
        failures.append("training loss rows present in candidate manifest")
    if manifest_card["gate_status"]["complete_gate_status_rows"] != len(rows):
        failures.append("incomplete gate_status rows")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": manifest_card["authority_rows"],
            "rows": len(rows),
            "targets": manifest_card["targets"],
            "splits": manifest_card["splits"],
            "languages": manifest_card["languages"],
            "complete_gate_status_rows": manifest_card["gate_status"]["complete_gate_status_rows"],
            "training_loss_rows": manifest_card["training_loss_rows"],
            "failures": failures,
        },
        "artifacts": {
            "manifest": str(OUT.relative_to(ROOT)),
            "manifest_card": str((OUT_DIR / "candidate_manifest_card.json").relative_to(ROOT)),
            "neutral_source": str(NEUTRAL.relative_to(ROOT)),
            "lineage_registry": str(LINEAGE.relative_to(ROOT)),
        },
        "decision": "Built a source-backed edit-localization candidate manifest with opaque IDs, lineage controls, complete gate_status cards, and no trainable losses." if not failures else "Source-backed edit-localization candidate manifest failed readiness checks.",
        "next_best_step": "Audit source-backed edit-localization candidates for contamination, schema drift, junk/OOD routing, and shortcut baselines before compiler-ready materialization.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8765 Source-Backed Edit Localization Candidate Manifest",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        f"Rows: `{len(rows)}`",
        f"Targets: `{manifest_card['targets']}`",
        "",
        "Rows are candidate-only: no losses, no decoder CE, no denoise CE, no runtime reward, no authority.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
