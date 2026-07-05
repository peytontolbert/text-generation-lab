#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

from source_provenance_license_security_filter import filter_card


ROOT = Path(__file__).resolve().parents[1]
STAGE = 8743
NAME = "stage8743_source_provenance_license_security_filter_readiness"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / NAME
SUMMARY = ROOT / "runs" / "summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SOURCE_PROVENANCE_LICENSE_SECURITY_FILTER_READINESS_STAGE8743.md"

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
        {"source_id": "src_ok", "lineage_hash": "abc", "license_status": "license_file_present", "security_policy_present": True, "allowed_import_source": True, "split": "train"},
        {"source_id": "src_secret", "lineage_hash": "def", "license_status": "license_file_present", "security_policy_present": True, "allowed_import_source": True, "split": "train", "content_preview": "api_key=123"},
        {"source_id": "src_license", "lineage_hash": "ghi", "license_status": "unknown", "security_policy_present": True, "allowed_import_source": True, "split": "train"},
        {"source_id": "src_security", "lineage_hash": "jkl", "license_status": "license_file_present", "security_policy_present": False, "allowed_import_source": True, "split": "train"},
        {"source_id": "src_locked", "lineage_hash": "mno", "license_status": "license_file_present", "security_policy_present": True, "allowed_import_source": True, "requested_split": "train", "split_eligibility": {"locked_eval": True}},
    ]
    card = filter_card(rows)
    sample_path = OUT_DIR / "source_provenance_license_security_filter_sample_card.json"
    decisions_path = OUT_DIR / "source_provenance_filter_decisions.jsonl"
    sample_path.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    decisions_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in card["decisions"]), encoding="utf-8")
    passed = (
        card["rows"] == 5
        and card["train_allowed_rows"] == 1
        and card["blocked_rows"] == 2
        and card["review_rows"] == 2
        and card["unsafe_decisions"] == 0
    )
    summary = {
        "stage": STAGE,
        "name": NAME,
        "stage_name": NAME,
        "passed": passed,
        "authority": AUTHORITY_CLOSED,
        "artifacts": {"sample_card": str(sample_path.relative_to(ROOT)), "decisions": str(decisions_path.relative_to(ROOT))},
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "rows": card["rows"],
            "train_allowed_rows": card["train_allowed_rows"],
            "blocked_rows": card["blocked_rows"],
            "review_rows": card["review_rows"],
            "unsafe_decisions": card["unsafe_decisions"],
            "routes": card["route_counts"],
        },
        "decision": "Recovered source provenance/license/security filter. It blocks missing lineage, secrets/PII, locked-eval train requests, and disallowed import sources; license/security gaps route to review.",
        "next_best_step": "Attach source provenance/license/security filter to central graph, then recover contamination_leakage_detector.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8743 Source Provenance License Security Filter Readiness",
        "",
        f"Passed: `{passed}`",
        "",
        "Recovered source provenance/license/security filter for curriculum admission.",
        "",
        "Authority remains closed. Clean sources may be structured-train candidates only; decoder/runtime/source/body authority remains closed.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
