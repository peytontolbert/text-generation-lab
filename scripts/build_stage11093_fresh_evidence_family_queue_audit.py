#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path("/data/agentkernel-seq2seq-text-lab")
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11093
NAME = "stage11093_fresh_evidence_family_queue_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "fresh_evidence_family_queue_audit.json"

QUEUE_SUMMARY = ARTIFACTS / "stage11092_fresh_evidence_family_queue" / "fresh_evidence_family_queue.json"
QUEUE_ROWS = ARTIFACTS / "stage11092_fresh_evidence_family_queue" / "queue_rows.jsonl"
FAMILY_ATLAS = ARTIFACTS / "stage11092_fresh_evidence_family_queue" / "family_atlas.jsonl"

EXHAUSTED_REPO_FAMILIES = {
    "repository_library",
    "parametergolf",
    "tokenizers",
    "candle",
    "agentkernel",
    "code_assist",
    "agentkernel-seq2seq-text-lab",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def main() -> None:
    queue_summary = load_json(QUEUE_SUMMARY)
    queue_rows = load_jsonl(QUEUE_ROWS)
    family_rows = load_jsonl(FAMILY_ATLAS)

    exhausted_hits = [
        str(row.get("repo_family") or "")
        for row in queue_rows
        if str(row.get("repo_family") or "") in EXHAUSTED_REPO_FAMILIES
    ]
    missing_verifier_targets = [
        str(row.get("root_id") or "")
        for row in queue_rows
        if not list(row.get("verification_targets") or [])
    ]
    missing_decisive_or_verifier = [
        str(row.get("root_id") or "")
        for row in queue_rows
        if not (
            "decisive_evidence" in list(row.get("available_target_subtypes") or [])
            or "verifier_outcome" in list(row.get("available_target_subtypes") or [])
        )
    ]

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not exhausted_hits and not missing_verifier_targets and not missing_decisive_or_verifier,
        "claim_scope": [
            "Audit that the fresh-family evidence queue excludes exhausted repo families and keeps explicit verifier-target signal.",
            "Confirm the queue is suitable as the next supply-side path for promotable evidence-lane work rather than another same-family replay loop.",
        ],
        "source_artifacts": {
            "queue_summary": rel(QUEUE_SUMMARY),
            "queue_rows": rel(QUEUE_ROWS),
            "family_atlas": rel(FAMILY_ATLAS),
        },
        "metrics": {
            "queued_roots": len(queue_rows),
            "queued_by_language": dict(sorted(Counter(str(row.get("language_family") or "") for row in queue_rows).items())),
            "queued_by_repo_family": dict(sorted(Counter(str(row.get("repo_family") or "") for row in queue_rows).items())),
            "family_status_counts": dict(sorted(Counter(str(row.get("status") or "") for row in family_rows).items())),
            "exhausted_family_hits": len(exhausted_hits),
            "missing_verifier_target_rows": len(missing_verifier_targets),
            "missing_decisive_or_verifier_rows": len(missing_decisive_or_verifier),
        },
        "findings": [
            "The queue is only useful if it excludes the already exhausted residual families by construction.",
            "Verifier-target signal and decisive/verifier subtype availability are the minimum requirements for honest next-stage evidence materialization.",
            "This queue should feed the next fresh-family materialization packet rather than another scorer probe on current families.",
        ],
        "blocking_issues": {
            "exhausted_family_hits": exhausted_hits,
            "missing_verifier_targets": missing_verifier_targets,
            "missing_decisive_or_verifier": missing_decisive_or_verifier,
        },
        "package_snapshot": queue_summary.get("metrics"),
        "next_best_step": "Use the queued roots to build the next multilingual fresh-family materialization packet with explicit visible ledgers and heldout split assignment.",
    }

    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
