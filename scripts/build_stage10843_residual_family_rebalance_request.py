#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10843
NAME = "stage10843_residual_family_rebalance_request"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "residual_family_rebalance_request.json"

AUDIT_JSON = ARTIFACTS / "stage10842_residual_family_distribution_audit" / "residual_family_distribution_audit.json"
PY_READY = ARTIFACTS / "stage10837_hf_local_repaired_support_readiness" / "hf_local_repaired_support_readiness.json"
RUST_READY = ARTIFACTS / "stage10838_linux_rust_support_readiness" / "linux_rust_support_readiness.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    audit = load_json(AUDIT_JSON)
    py_ready = load_json(PY_READY)
    rust_ready = load_json(RUST_READY)

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "residual_family_rebalance_requested",
        "claim_scope": [
            "Translate the current residual-family audit into the next honest data-shape work item.",
            "Replace generic preservation sweeps with a targeted rebuild for evidence_citation and verifier_outcome.",
        ],
        "authoritative_inputs": {
            "distribution_audit": rel(AUDIT_JSON),
            "python_support_readiness": rel(PY_READY),
            "rust_support_readiness": rel(RUST_READY),
        },
        "residual_targets": {
            "python_verifier_outcome": {
                "current_ready_support": py_ready["current_lane_alignment"]["repaired_packet_bundle_id"],
                "required_new_shape": [
                    "many multi-option verifier rows with B/C/G-style targets",
                    "test snippet plus changed-code-path evidence",
                    "transition semantics such as FAIL_TO_PASS, PASS_TO_PASS, NOT_EXERCISED, INSUFFICIENT_EVIDENCE",
                    "no one-option verifier rows in promotable residual packets",
                ],
                "requested_scale_floor": {
                    "train_rows": 30,
                    "validation_rows": 8,
                    "strict_rows": 8,
                },
            },
            "rust_evidence_citation": {
                "current_ready_support": rust_ready["current_lane_alignment"]["adjudicated_bundle_id"],
                "required_new_shape": [
                    "explicit B/C/D/E/F role coverage in train",
                    "distinct source spans for surface, nearby context, symptom/call-path, verifier constraint, and any background role",
                    "avoid duplicate or near-duplicate text under different visible evidence roles unless role reasoning is the point of the row",
                    "fresh non-tokenizers anchored roots beyond linux train-support",
                ],
                "requested_scale_floor": {
                    "train_rows_per_label": 20,
                    "fresh_roots": 2,
                },
            },
        },
        "trainer_recommendations": [
            "Add task-balanced or residual-family-balanced sampling rather than pure cyclic row order.",
            "Downweight or exempt residual-family rows from preservation KL in at least one diagnostic run.",
            "Keep letter labels as presentation only; train semantic candidate and transition targets internally where possible.",
        ],
        "promotion_boundary": [
            "Do not promote another broad support probe unless it improves fresh residual-family heldout or the frozen 24-row strict frontier.",
            "Use the current 24-row frontier as canary only; the next real movement target is residual-family geometry.",
        ],
        "next_best_step": "Build a new evidence_citation plus verifier_outcome rebalance support package rather than another generic multilingual preservation package.",
    }

    write_json(OUT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
