#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10853
NAME = "stage10853_fresh_residual_root_admission_and_packet_builder"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "fresh_residual_root_admission_and_packet_builder.json"
ADMITTED_JSONL = OUT_DIR / "admitted_roots.jsonl"
BLOCKED_JSONL = OUT_DIR / "blocked_roots.jsonl"
SUMMARY = ROOT / "runs" / "summaries" / f"{NAME}.json"

PY_MANIFEST = ARTIFACTS / "stage10851_fresh_python_verifier_transition_root_builder" / "fresh_python_verifier_transition_roots.jsonl"
RUST_MANIFEST = ARTIFACTS / "stage10852_fresh_rust_ef_evidence_root_builder" / "fresh_rust_ef_evidence_roots.jsonl"
PROBE_AUDIT = ARTIFACTS / "stage10848_residual_family_rebalanced_probe_audit" / "residual_family_rebalanced_probe_audit.json"
SCORING_AUDIT = ARTIFACTS / "stage10849_current_runtime_scoring_policy_audit" / "current_runtime_scoring_policy_audit.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


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
    python_rows = load_jsonl(PY_MANIFEST)
    rust_rows = load_jsonl(RUST_MANIFEST)
    probe_audit = load_json(PROBE_AUDIT)
    scoring_audit = load_json(SCORING_AUDIT)

    admitted: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []

    for row in python_rows:
        admitted_now = (
            row["lane"] == "queue_aligned_context_pack"
            and row["anti_cheat_status"] == "completed"
            and row["gold_status"] == "completed"
        )
        rec = dict(row)
        rec["admission_scope"] = "train_support_only" if admitted_now else "blocked_pending_geometry_upgrade"
        rec["residual_family"] = "python_verifier_outcome"
        rec["headline_eligible"] = False
        if admitted_now:
            admitted.append(rec)
        else:
            blocked.append(rec)

    for row in rust_rows:
        admitted_now = row["readiness"] == "train_support_admitted"
        rec = dict(row)
        rec["admission_scope"] = "train_support_only" if admitted_now else "blocked_pending_anchor_or_review"
        rec["residual_family"] = "rust_evidence_citation"
        rec["headline_eligible"] = False
        if admitted_now:
            admitted.append(rec)
        else:
            blocked.append(rec)

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "fresh_residual_root_admission_boundary_established",
        "headline_findings": [
            "Three roots are admissible now, all train-support only: one queue-aligned Python verifier root plus Linux Rust and candle-datasets Rust.",
            "The Rust support lane is broader than the previous manifest claimed, but the admitted roots still do not directly resolve the strict residual blockers.",
            "Current scorer and probe audits still do not justify another promotion-style package from these admitted roots alone.",
        ],
        "authoritative_inputs": {
            "python_manifest": rel(PY_MANIFEST),
            "rust_manifest": rel(RUST_MANIFEST),
            "probe_audit": rel(PROBE_AUDIT),
            "scoring_audit": rel(SCORING_AUDIT),
        },
        "counts": {
            "admitted_root_count": len(admitted),
            "blocked_root_count": len(blocked),
            "admitted_python": sum(1 for row in admitted if row["language_family"] == "python"),
            "admitted_rust": sum(1 for row in admitted if row["language_family"] == "rust"),
        },
        "admission_policy": [
            "admit only reviewed or explicitly train-support packetized roots",
            "do not elevate any admitted root to headline same-surface evidence",
            "do not build a new promotion packet until at least one richer Python verifier-transition root and one second non-tokenizers Rust evidence root clear admission",
        ],
        "admitted_roots": admitted,
        "blocked_roots": blocked,
        "next_best_step": "Use the three admitted roots as support inventory, then focus the next builder on converting one geometry-upgrade Python root and one additional Rust heldout root into admitted residual roots.",
        "frontier_context": {
            "strict_status": probe_audit["evaluation_readout"]["strict_status"],
            "best_scoring_policy": scoring_audit["best_policy"],
        },
    }

    write_jsonl(ADMITTED_JSONL, admitted)
    write_jsonl(BLOCKED_JSONL, blocked)
    write_json(OUT_JSON, payload)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": payload["decision"],
            "admitted_root_count": len(admitted),
            "blocked_root_count": len(blocked),
            "artifact": rel(OUT_JSON),
        },
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
