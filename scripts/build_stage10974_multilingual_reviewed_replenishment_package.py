#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10974
NAME = "stage10974_multilingual_reviewed_replenishment_package"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "multilingual_reviewed_replenishment_package.json"
SUPPORT_ROWS_JSONL = OUT_DIR / "train_support_rows.jsonl"
CANDIDATE_ROWS_JSONL = OUT_DIR / "strict_candidate_rows.jsonl"
ALL_ROWS_JSONL = OUT_DIR / "bundle_rows.jsonl"

PC_SUPPORT = ARTIFACTS / "stage10970_immediate_evidence_replenishment_bundle" / "train_support_rows.jsonl"
PC_CANDIDATES = ARTIFACTS / "stage10970_immediate_evidence_replenishment_bundle" / "strict_candidate_rows.jsonl"
PC_SUMMARY = ARTIFACTS / "stage10970_immediate_evidence_replenishment_bundle" / "immediate_evidence_replenishment_bundle.json"
PC_AUDIT = ARTIFACTS / "stage10971_immediate_evidence_replenishment_audit" / "immediate_evidence_replenishment_audit.json"

RUST_SUPPORT = ARTIFACTS / "stage10972_rust_reviewed_evidence_bundle" / "train_support_rows.jsonl"
RUST_CANDIDATES = ARTIFACTS / "stage10972_rust_reviewed_evidence_bundle" / "strict_candidate_rows.jsonl"
RUST_SUMMARY = ARTIFACTS / "stage10972_rust_reviewed_evidence_bundle" / "rust_reviewed_evidence_bundle.json"
RUST_AUDIT = ARTIFACTS / "stage10973_rust_reviewed_evidence_audit" / "rust_reviewed_evidence_audit.json"
WEB_GAP = ARTIFACTS / "stage10418_pure_web_verifier_anchor_gap_audit" / "pure_web_verifier_anchor_gap_audit.json"
RUST_NEXT_BATCH = ARTIFACTS / "stage10956_multilingual_evidence_next_batch_package" / "multilingual_evidence_next_batch_package.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    pc_support = load_jsonl(PC_SUPPORT)
    pc_candidates = load_jsonl(PC_CANDIDATES)
    rust_support = load_jsonl(RUST_SUPPORT)
    rust_candidates = load_jsonl(RUST_CANDIDATES)
    support_rows = pc_support + rust_support
    candidate_rows = pc_candidates + rust_candidates
    all_rows = support_rows + candidate_rows

    pc_audit = load_json(PC_AUDIT)
    rust_audit = load_json(RUST_AUDIT)
    web_gap = load_json(WEB_GAP)
    rust_next = load_json(RUST_NEXT_BATCH)

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(all_rows) and bool(pc_audit.get("passed")) and bool(rust_audit.get("passed")),
        "decision": "multilingual_reviewed_replenishment_package_ready_for_next_support_stage",
        "claim_scope": [
            "Combine the newly audited Python/C++ and Rust reviewed replenishment bundles into one multilingual support source for the next v2.7 probe or package stage.",
            "Make the remaining web and fresh-Rust-source blockers explicit so the next multilingual claim does not silently overstate coverage.",
        ],
        "source_artifacts": {
            "python_cpp_summary": rel(PC_SUMMARY),
            "python_cpp_audit": rel(PC_AUDIT),
            "rust_summary": rel(RUST_SUMMARY),
            "rust_audit": rel(RUST_AUDIT),
            "web_gap": rel(WEB_GAP),
            "next_batch_package": rel(RUST_NEXT_BATCH),
        },
        "metrics": {
            "support_rows": len(support_rows),
            "candidate_rows": len(candidate_rows),
            "all_rows": len(all_rows),
            "support_by_language": dict(sorted(Counter(str(row.get("language_family") or "unknown") for row in support_rows).items())),
            "candidate_by_language": dict(sorted(Counter(str(row.get("language_family") or "unknown") for row in candidate_rows).items())),
            "gold_values_candidate_rows": dict(sorted(Counter(str((row.get("standalone_projection_source") or {}).get("gold_value") or "unknown") for row in candidate_rows).items())),
        },
        "audits": {
            "python_cpp_passed": pc_audit.get("passed"),
            "rust_passed": rust_audit.get("passed"),
        },
        "headline_findings": [
            "The next multilingual support source now has audited reviewed replenishment data for Python, C/C++, and Rust.",
            "Python/C++ immediate replenishment contributes verifier-and-test-constraint positives plus a candidate-surface counterfamily control.",
            "Rust reviewed replenishment contributes symptom-or-call-path positives plus a candidate-surface control, all with passing anti-cheat audits.",
            "Web is still blocked for headline expansion until a pure-web selected-test family exists; this package does not solve that lane.",
        ],
        "remaining_blockers": [
            "No new pure-web selected-test/verifier-anchored replenishment family is available yet.",
            "Fresh Rust scaffolds like linux::rust and candle-datasets still contain TODO materialization placeholders and are not scoreable.",
            "This package improves support supply, not headline heldout size; the next promotion-stage run still needs an explicit same-manifest or fresh-heldout contract.",
        ],
        "next_best_step": "Use this package as the source for the next multilingual support/probe stage, while keeping web off the promotable claim path and treating linux/candle-datasets Rust scaffolds as future source material rather than current eval rows.",
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "support_rows_jsonl": rel(SUPPORT_ROWS_JSONL),
            "candidate_rows_jsonl": rel(CANDIDATE_ROWS_JSONL),
            "bundle_rows_jsonl": rel(ALL_ROWS_JSONL),
        },
    }

    write_json(SUMMARY_JSON, summary)
    write_jsonl(SUPPORT_ROWS_JSONL, support_rows)
    write_jsonl(CANDIDATE_ROWS_JSONL, candidate_rows)
    write_jsonl(ALL_ROWS_JSONL, all_rows)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
