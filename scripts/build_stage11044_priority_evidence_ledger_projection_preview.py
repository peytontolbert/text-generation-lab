#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path("/data/agentkernel-seq2seq-text-lab")
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11044
NAME = "stage11044_priority_evidence_ledger_projection_preview"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "priority_evidence_ledger_projection_preview.json"
PREVIEW_JSONL = OUT_DIR / "projected_evidence_ledgers.jsonl"

ROOT_CARDS = ARTIFACTS / "stage11042_priority_residual_root_materialization_packet" / "priority_root_cards.jsonl"
PACKET_ROWS = ARTIFACTS / "stage11042_priority_residual_root_materialization_packet" / "priority_packet_rows.jsonl"
EVENTS = ARTIFACTS / "stage10516_long_context_root_state_compiler" / "compiled_typed_events.jsonl"


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


def parse_json(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    root_cards = {str(row.get("root_id") or ""): row for row in load_jsonl(ROOT_CARDS)}
    packet_rows = load_jsonl(PACKET_ROWS)

    retrieval_events: dict[str, dict[str, Any]] = {}
    for event in load_jsonl(EVENTS):
        root_id = str(event.get("root_id") or "")
        if root_id not in root_cards:
            continue
        if str(event.get("event_type") or "") in {"SEARCH_RESULT", "FILE_READ", "COMMAND_RESULT"}:
            retrieval_events[root_id] = event

    preview_rows: list[dict[str, Any]] = []
    missing_roots: list[str] = []

    for row in packet_rows:
        if str(row.get("target_subtype") or "") != "decisive_evidence":
            continue
        if (row.get("scoreability") or {}).get("scoreable_now") is True:
            continue

        root_id = str(row.get("root_id") or "")
        event = retrieval_events.get(root_id)
        if event is None:
            missing_roots.append(root_id)
            continue

        event_items = parse_json(event.get("content")) or []
        gold_ids = set(str(item) for item in (row.get("target_text_parsed") or []))
        projected = []
        for item in event_items:
            if not isinstance(item, dict):
                continue
            chunk_id = str(item.get("chunk_id") or "")
            projected.append(
                {
                    "chunk_id": chunk_id,
                    "path": item.get("path"),
                    "role": item.get("role"),
                    "score": item.get("score"),
                    "support_reasons": item.get("support_reasons") or [],
                    "is_gold_target": chunk_id in gold_ids,
                }
            )

        preview_rows.append(
            {
                "root_id": root_id,
                "repo_family": row.get("repo_family"),
                "language_family": row.get("language_family"),
                "promotion_lane": row.get("promotion_lane"),
                "row_id": row.get("row_id"),
                "query_text": row.get("query_text"),
                "verification_targets": row.get("verification_targets") or [],
                "expected_changed_files": row.get("expected_changed_files") or [],
                "gold_evidence_ids": sorted(gold_ids),
                "projected_evidence_candidates": projected,
                "projection_status": "preview_only_not_yet_bounded_choice",
                "next_conversion_requirements": [
                    "Choose a bounded candidate subset that keeps candidate_change_surface plausible.",
                    "Hide raw gold chunk IDs behind opaque option labels before scoring.",
                    "Preserve role/path/support-reason evidence so a maintainer can justify the answer.",
                ],
            }
        )

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": True,
        "decision": "priority_evidence_ledger_projection_preview_ready",
        "claim_scope": [
            "Project the five blocked decisive-evidence targets from stage11042 into visible evidence-ledger previews.",
            "Bridge opaque chunk IDs into path/role/support-reason evidence so the next bounded-choice conversion can stay honest.",
        ],
        "headline_findings": [
            f"Projected visible evidence ledgers for {len(preview_rows)} blocked decisive-evidence rows from the stage11042 packet.",
            "Each preview preserves the raw gold chunk membership while surfacing path, role, score, and support-reason metadata needed for maintainer-visible options.",
            "These previews are not yet scoreable rows; they are the anti-cheat bridge needed before converting the C/C++ and Python blocked rows into honest bounded evidence tasks.",
        ],
        "metrics": {
            "preview_count": len(preview_rows),
            "missing_retrieval_event_roots": len(missing_roots),
            "by_language": {
                language: sum(1 for row in preview_rows if str(row.get("language_family") or "") == language)
                for language in sorted({str(row.get("language_family") or "") for row in preview_rows})
            },
            "by_lane": {
                lane: sum(1 for row in preview_rows if str(row.get("promotion_lane") or "") == lane)
                for lane in sorted({str(row.get("promotion_lane") or "") for row in preview_rows})
            },
        },
        "next_best_step": [
            "Convert the three C/C++ previews into bounded evidence-citation candidates with opaque labels and visible path/role evidence.",
            "Use the two Python previews only if they preserve verifier-ledger semantics rather than collapsing back to changed-surface priors.",
            "Keep the previews out of training/eval until explicit anti-cheat review confirms the bounded candidate subsets remain answerable and non-leaky.",
        ],
        "source_artifacts": {
            "root_cards": rel(ROOT_CARDS),
            "packet_rows": rel(PACKET_ROWS),
            "events": rel(EVENTS),
        },
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "projected_ledgers_jsonl": rel(PREVIEW_JSONL),
        },
        "missing_roots": missing_roots,
    }

    write_json(SUMMARY_JSON, summary)
    write_jsonl(PREVIEW_JSONL, preview_rows)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
