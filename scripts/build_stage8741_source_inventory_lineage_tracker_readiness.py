#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

from source_inventory_lineage_tracker import lineage_manifest


ROOT = Path(__file__).resolve().parents[1]
STAGE = 8741
NAME = "stage8741_source_inventory_lineage_tracker_readiness"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / NAME
SUMMARY = ROOT / "runs" / "summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SOURCE_INVENTORY_LINEAGE_TRACKER_READINESS_STAGE8741.md"

AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "training_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "denoise_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_body_authorized": False,
    "gemma_authorized": False,
    "promotion_ready": False,
}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {"source_uri": "/arxiv/repositories/example/file.py", "content": "def f(): pass", "split": "train", "license_status": "license_file_present", "security_policy_present": True, "transform_chain": ["repo_scan", "symbol_extract"]},
        {"source_uri": "/arxiv/datasets/locked/example.parquet", "content": "locked", "split": "locked_eval", "locked_eval": True, "license_status": "readme_present_license_unknown", "security_policy_present": False},
        {"source_uri": "/arxiv/repositories/unknown/file.py", "content": "x = 1", "split": "train", "license_status": "unknown", "security_policy_present": True},
    ]
    manifest = lineage_manifest(rows)
    audit = manifest["audit"]
    sample_path = OUT_DIR / "source_inventory_lineage_tracker_sample_card.json"
    manifest_path = OUT_DIR / "source_inventory_lineage_cards.jsonl"
    sample_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest_path.write_text("".join(json.dumps(card, sort_keys=True) + "\n" for card in manifest["cards"]), encoding="utf-8")
    passed = (
        audit["passed"]
        and audit["rows"] == 3
        and audit["train_eligible_rows"] == 1
        and audit["locked_eval_rows"] == 1
        and not audit["failures"]
    )
    summary = {
        "stage": STAGE,
        "name": NAME,
        "stage_name": NAME,
        "passed": passed,
        "authority": AUTHORITY_CLOSED,
        "artifacts": {"sample_card": str(sample_path.relative_to(ROOT)), "manifest": str(manifest_path.relative_to(ROOT))},
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "rows": audit["rows"],
            "train_eligible_rows": audit["train_eligible_rows"],
            "locked_eval_rows": audit["locked_eval_rows"],
            "duplicate_lineage_hashes": len(audit["duplicate_lineage_hashes"]),
            "failures": len(audit["failures"]),
        },
        "decision": "Recovered reusable source inventory lineage tracker. Future mined rows must carry source_id, content_hash, transform_chain, split eligibility, and lineage_hash before entering curriculum builders.",
        "next_best_step": "Attach source inventory lineage tracker to central graph, then recover source_provenance_license_security_filter.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8741 Source Inventory Lineage Tracker Readiness",
        "",
        f"Passed: `{passed}`",
        "",
        "Recovered reusable source lineage tracker for source_id, content_hash, transform_chain, split eligibility, and lineage_hash.",
        "",
        "Authority remains closed. Locked-eval and unreviewed sources cannot become train-eligible.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
