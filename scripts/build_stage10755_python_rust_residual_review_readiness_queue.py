#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10755
NAME = "stage10755_python_rust_residual_review_readiness_queue"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_JSON = OUT_DIR / "python_rust_residual_review_readiness_queue.json"
QUEUE_JSONL = OUT_DIR / "residual_review_queue.jsonl"
RUNBOOK_JSONL = OUT_DIR / "residual_review_runbook.jsonl"
RUN_SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

PYTHON_PACKET_AUDIT = ROOT / "runs/local/artifacts/stage10493_python_verifier_fresh_review_packet_builder/python_verifier_fresh_review_packet_builder.json"
PYTHON_TARGET_STATUS = ROOT / "runs/local/artifacts/stage10493_python_verifier_fresh_review_packet_builder/python_verifier_review_target_status.jsonl"
PYTHON_QUALIFIED_ROWS = ROOT / "runs/local/artifacts/stage10493_python_verifier_fresh_review_packet_builder/python_verifier_reviewed_support_rows.jsonl"
RUST_SCAFFOLD_SUMMARY = ROOT / "runs/local/artifacts/stage10674_rust_fresh_review_packet_scaffolds/rust_fresh_review_packet_scaffolds.json"
RUST_SCAFFOLD_DIR = ROOT / "runs/local/artifacts/stage10674_rust_fresh_review_packet_scaffolds/review_packets"
MULTILINGUAL_QUEUE = ROOT / "runs/local/artifacts/stage10752_multilingual_bulk_root_materialization_queue/multilingual_bulk_root_materialization_queue.json"


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def main() -> None:
    python_audit = load_json(PYTHON_PACKET_AUDIT)
    python_targets = load_jsonl(PYTHON_TARGET_STATUS)
    python_rows = load_jsonl(PYTHON_QUALIFIED_ROWS)
    rust_summary = load_json(RUST_SCAFFOLD_SUMMARY)
    multilingual_queue = load_json(MULTILINGUAL_QUEUE)

    queue_rows: list[dict[str, Any]] = []
    runbook_rows: list[dict[str, Any]] = []

    qualified_python = [row for row in python_targets if bool(row.get("immediately_qualified_for_reviewed_verifier_packet"))]
    for idx, row in enumerate(qualified_python, start=1):
        queue_rows.append(
            {
                "global_queue_order": idx,
                "language_family": "python",
                "lane_priority": 1,
                "work_type": "immediately_executable_reviewed_verifier_support",
                "candidate_id": str(row["episode_id"]),
                "bundle_id": str(row["bundle_id"]),
                "repo_id": str(row["repo_id"]),
                "source_artifact": display(PYTHON_TARGET_STATUS),
                "qualified_support_row_count": sum(1 for support in python_rows if str(support.get("source_bundle_id") or "") == str(row["bundle_id"])),
                "anti_cheat_gates": [
                    "3+ plausible selected-test options remain visible in reviewed verifier geometry",
                    "selected-test anchor not exposed verbatim before options in future bounded projections",
                    "same root remains disjoint from MirrorMind strict family",
                    "any training use must remain train-support only until fresh heldout verifier roots exist",
                ],
                "next_action": "use this root as the primary richer Python verifier support lane for future package refreshes",
                "readiness": "immediately_qualified",
            }
        )

    deferred_python = [row for row in python_targets if not bool(row.get("immediately_qualified_for_reviewed_verifier_packet"))]
    for row in deferred_python:
        queue_rows.append(
            {
                "global_queue_order": len(queue_rows) + 1,
                "language_family": "python",
                "lane_priority": 2,
                "work_type": "needs_review_packet_upgrade",
                "candidate_id": str(row["episode_id"]),
                "bundle_id": str(row["bundle_id"]),
                "repo_id": str(row["repo_id"]),
                "source_artifact": display(PYTHON_TARGET_STATUS),
                "gaps": list(row.get("gaps") or []),
                "anti_cheat_gates": [
                    "do not count as richer verifier support until gold adjudication and executable verifier rows exist",
                    "do not use single-test reviewed geometry as if it solved B-vs-C verifier ambiguity",
                ],
                "next_action": "upgrade or rebuild the packet before using it as primary Python verifier residual support",
                "readiness": "deferred",
            }
        )

    rust_targets = list(rust_summary.get("scaffold_targets") or [])
    for target in rust_targets:
        slug = target.replace("::", "__")
        packet_dir = RUST_SCAFFOLD_DIR / slug
        queue_rows.append(
            {
                "global_queue_order": len(queue_rows) + 1,
                "language_family": "rust",
                "lane_priority": 3,
                "work_type": "needs_real_materialization",
                "candidate_id": target,
                "bundle_id": f"stage10674::{target}",
                "repo_id": target.split("::", 1)[0] if "::" in target else target,
                "source_artifact": display(packet_dir / "fresh_rust_bundle_preview.json"),
                "anti_cheat_gates": [
                    "replace all placeholder evidence with real source-derived spans",
                    "attach selected test or verifier anchor before any scoring or training promotion",
                    "retain candidate_change_surface as a tempting negative without making it the gold",
                    "ensure symptom_or_call_path_analogue and verifier_and_test_constraint are semantically distinct from candidate_change_surface",
                ],
                "next_action": "materialize real graph spans and verifier/test anchors, then re-run anti-cheat and gold adjudication",
                "readiness": "scaffold_only",
            }
        )

    runbook_rows.append(
        {
            "language_family": "python",
            "current_status": "one_immediately_qualified_richer_verifier_root",
            "queue_items": sum(1 for row in queue_rows if row["language_family"] == "python"),
            "recommended_use": "Use only the immediately qualified context_pack root as richer reviewed verifier support. Treat hf_local and agentkernel as upgrade work, not as solved supply.",
            "headline_guard": "Do not claim Python residual recovery from packet count alone; only one root is immediately qualified under current reviewed assets.",
        }
    )
    runbook_rows.append(
        {
            "language_family": "rust",
            "current_status": "scaffold_only_no_promotable_residual_packet",
            "queue_items": sum(1 for row in queue_rows if row["language_family"] == "rust"),
            "recommended_use": "Treat all current Rust residual queue items as packet-materialization work. None are promotable until real evidence and verifier anchors replace placeholders.",
            "headline_guard": "Do not describe Rust fresh-root residual support as execution-ready yet.",
        }
    )

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "python_rust_residual_review_readiness_queue_ready",
        "claim_scope": [
            "Turn the current Python verifier and Rust citation residual lanes into an honest review-readiness queue.",
            "Distinguish immediately qualified reviewed Python roots from Rust scaffold-only packet work so future package refreshes stop treating both lanes as equally ready.",
            "This is a residual supply and anti-cheat readiness artifact, not a new frontier score claim.",
        ],
        "source_artifacts": {
            "python_packet_audit": display(PYTHON_PACKET_AUDIT),
            "python_target_status": display(PYTHON_TARGET_STATUS),
            "python_qualified_rows": display(PYTHON_QUALIFIED_ROWS),
            "rust_scaffold_summary": display(RUST_SCAFFOLD_SUMMARY),
            "multilingual_bulk_queue": display(MULTILINGUAL_QUEUE),
        },
        "headline_findings": [
            "Python has exactly one immediately qualified richer reviewed verifier root under current assets.",
            "Rust has scaffold packets but still lacks a promotable fresh residual packet because its evidence and verifier anchors are placeholders.",
            "The multilingual bulk queue should therefore treat Python as a selective reviewed-support lane and Rust as a materialization lane until real spans are attached.",
        ],
        "queue_counts": {
            "python_immediately_qualified": len(qualified_python),
            "python_deferred": len(deferred_python),
            "rust_scaffold_only": len(rust_targets),
            "multilingual_queue_items_python": int((multilingual_queue.get("queue_counts_by_language") or {}).get("python", 0)),
            "multilingual_queue_items_rust": int((multilingual_queue.get("queue_counts_by_language") or {}).get("rust", 0)),
        },
        "next_best_step": "Use this readiness queue to refresh future support packages: admit only the qualified Python verifier lane now, and keep Rust on real materialization work until its scaffold packets are fully sourced.",
        "outputs": {
            "summary": display(SUMMARY_JSON),
            "queue": display(QUEUE_JSONL),
            "runbook": display(RUNBOOK_JSONL),
        },
    }

    write_json(SUMMARY_JSON, summary)
    write_jsonl(QUEUE_JSONL, queue_rows)
    write_jsonl(RUNBOOK_JSONL, runbook_rows)
    write_json(
        RUN_SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": summary["decision"],
            "summary": display(SUMMARY_JSON),
            "queue": display(QUEUE_JSONL),
        },
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
